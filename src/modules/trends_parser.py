from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import pandas as pd
from pytrends.request import TrendReq

from .data_cleaner import (
    df_reset_and_fill,
    timeline_to_list,
    region_to_list,
    related_topics_to_list,
    related_queries_to_list,
)

@dataclass
class TrendsOptions:
    hl: str = "en-US"
    tz: int = 0
    geo: str = ""  # e.g., "US", "PK", "GB"
    timeframe: str = "today 12-m"  # e.g., "now 7-d", "today 12-m", "2023-01-01 2023-12-31"
    gprop: str = ""  # "", "images", "news", "youtube", "froogle"
    category: int = 0
    sleep: float = 1.0

@dataclass
class TrendsClient:
    opts: TrendsOptions = field(default_factory=TrendsOptions)

    def _from_url(self, url: str) -> Tuple[List[str], TrendsOptions]:
        """
        Parse a Google Trends URL and derive search terms and options.
        Supports URLs like: https://trends.google.com/trends/explore?date=now%207-d&geo=US&q=web%20scraping
        """
        parsed = urlparse(url)
        qs = {k: v[0] for k, v in parse_qs(parsed.query).items() if v}
        terms: List[str] = []
        if "q" in qs and qs["q"]:
            # q may be comma-separated or contain queries split by commas
            parts = [p.strip() for p in qs["q"].split(",") if p.strip()]
            terms.extend(parts)

        opts = TrendsOptions(
            hl=qs.get("hl", self.opts.hl),
            tz=int(qs.get("tz", self.opts.tz)) if re.match(r"^-?\d+$", qs.get("tz", "")) else self.opts.tz,
            geo=qs.get("geo", self.opts.geo),
            timeframe=qs.get("date", self.opts.timeframe),
            gprop=qs.get("gprop", self.opts.gprop),
            category=int(qs.get("cat", self.opts.category)) if re.match(r"^\d+$", qs.get("cat", "")) else self.opts.category,
            sleep=self.opts.sleep,
        )
        return terms or [qs.get("q", "")], opts

    def _build(self, py: TrendReq, kw_list: List[str], opts: TrendsOptions) -> None:
        py.build_payload(
            kw_list=kw_list,
            cat=opts.category,
            timeframe=opts.timeframe,
            geo=opts.geo,
            gprop=opts.gprop,
        )

    def fetch(self, input_url_or_term: str, override: Optional[TrendsOptions] = None) -> Dict[str, Any]:
        """
        Fetch data from Google Trends for a term or a Trends URL.
        Returns a dictionary aligned with the README's expected output schema.
        """
        opts = override or self.opts
        terms = [input_url_or_term]
        if "trends.google" in input_url_or_term:
            terms, parsed_opts = self._from_url(input_url_or_term)
            # override parsed with explicit overrides where provided
            for f in ("hl", "tz", "geo", "timeframe", "gprop", "category", "sleep"):
                v = getattr(opts, f)
                if v:
                    setattr(parsed_opts, f, v)
            opts = parsed_opts

        kw_list = [t for t in terms if t]
        if not kw_list:
            raise ValueError("No valid search term(s) parsed from input.")

        py = TrendReq(hl=opts.hl, tz=opts.tz, retries=2, backoff_factor=opts.sleep)

        self._build(py, kw_list, opts)

        # Timeline
        iot_df = df_reset_and_fill(py.interest_over_time())

        # Regions
        subregion_df = df_reset_and_fill(py.interest_by_region(resolution="REGION"))
        if "geoCode" not in subregion_df.columns and not subregion_df.empty:
            # Attempt to preserve ISO codes if present in index names (not always available)
            subregion_df["geoCode"] = None

        city_df = df_reset_and_fill(py.interest_by_region(resolution="CITY"))
        if "geoCode" not in city_df.columns and not city_df.empty:
            city_df["geoCode"] = None

        # Related topics / queries
        rt = py.related_topics()
        rq = py.related_queries()

        related_topics = related_topics_to_list(rt)
        related_queries = related_queries_to_list(rq)

        result: Dict[str, Any] = {
            "inputUrlOrTerm": input_url_or_term,
            "searchTerm": ", ".join(kw_list),
            "options": {
                "hl": opts.hl,
                "tz": opts.tz,
                "geo": opts.geo,
                "timeframe": opts.timeframe,
                "gprop": opts.gprop,
                "category": opts.category,
            },
            "interestOverTime_timelineData": timeline_to_list(iot_df, [c for c in iot_df.columns if c != "date"]),
            "interestBySubregion": region_to_list(subregion_df),
            "interestByCity": region_to_list(city_df),
            "relatedTopics_top": related_topics["top"],
            "relatedTopics_rising": related_topics["rising"],
            "relatedQueries_top": related_queries["top"],
            "relatedQueries_rising": related_queries["rising"],
        }
        return result

    @staticmethod
    def to_rows_for_tabular(payloads: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Flatten payloads into a simple tabular dataframe (one row per input),
        capturing a few key summary metrics for CSV/Excel export.
        """
        rows: List[Dict[str, Any]] = []
        for p in payloads:
            timeline = p.get("interestOverTime_timelineData", []) or []
            avg_value = 0
            if timeline:
                all_vals = [v for item in timeline for v in item.get("value", [])]
                if all_vals:
                    avg_value = sum(all_vals) / max(len(all_vals), 1)

            top_query = next(iter(p.get("relatedQueries_top", [])), {})
            rising_query = next(iter(p.get("relatedQueries_rising", [])), {})

            rows.append(
                {
                    "input": p.get("inputUrlOrTerm", ""),
                    "searchTerm": p.get("searchTerm", ""),
                    "geo": (p.get("options") or {}).get("geo", ""),
                    "timeframe": (p.get("options") or {}).get("timeframe", ""),
                    "avgInterest": round(avg_value, 2),
                    "topRelatedQuery": top_query.get("query", ""),
                    "topRelatedQueryValue": top_query.get("value", ""),
                    "risingRelatedQuery": rising_query.get("query", ""),
                    "risingRelatedQueryValue": rising_query.get("value", ""),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def parse_input_file(path: str) -> List[Tuple[str, TrendsOptions]]:
        """
        Parse a JSON file supporting either:
        - ["term1", "term2"]
        - [{"input": "term", "options": {...}}, ...]
        - {"inputs": [...], "options": {...}}  # broadcast options
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        def opts_from_dict(d: Dict[str, Any]) -> TrendsOptions:
            return TrendsOptions(
                hl=d.get("hl", "en-US"),
                tz=int(d.get("tz", 0)),
                geo=d.get("geo", ""),
                timeframe=d.get("timeframe", "today 12-m"),
                gprop=d.get("gprop", ""),
                category=int(d.get("category", 0)),
                sleep=float(d.get("sleep", 1.0)),
            )

        results: List[Tuple[str, TrendsOptions]] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    results.append((item, TrendsOptions()))
                elif isinstance(item, dict):
                    results.append((item.get("input", ""), opts_from_dict(item.get("options", {}))))
        elif isinstance(data, dict):
            broadcast = opts_from_dict(data.get("options", {}))
            inputs = data.get("inputs", [])
            if isinstance(inputs, list):
                for it in inputs:
                    if isinstance(it, str):
                        results.append((it, broadcast))
                    elif isinstance(it, dict):
                        # merge specific options over broadcast
                        specific = opts_from_dict(it.get("options", {}))
                        merged = TrendsOptions(
                            hl=specific.hl or broadcast.hl,
                            tz=specific.tz if specific.tz is not None else broadcast.tz,
                            geo=specific.geo or broadcast.geo,
                            timeframe=specific.timeframe or broadcast.timeframe,
                            gprop=specific.gprop or broadcast.gprop,
                            category=specific.category or broadcast.category,
                            sleep=specific.sleep or broadcast.sleep,
                        )
                        results.append((it.get("input", ""), merged))
        else:
            raise ValueError("Unsupported input file structure.")
        return results