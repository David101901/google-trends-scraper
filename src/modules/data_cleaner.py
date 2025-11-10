from __future__ import annotations

from typing import Dict, Any, List, Optional
import pandas as pd

def df_reset_and_fill(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    out = out.reset_index()
    out = out.fillna(0)
    return out

def timeline_to_list(df: pd.DataFrame, value_cols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Convert interest_over_time DataFrame to the expected JSON-like list.
    """
    if df.empty:
        return []
    df = df.copy()
    # pytrends timeline has a 'isPartial' column; drop it for values
    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])
    if value_cols is None:
        value_cols = [c for c in df.columns if c != "date"]
    rows: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        values = [int(r[c]) if pd.notna(r[c]) else 0 for c in value_cols]
        rows.append(
            {
                "time": int(pd.Timestamp(r["date"]).timestamp()),
                "formattedTime": pd.Timestamp(r["date"]).strftime("%b %d, %Y"),
                "value": values,
                "formattedValue": [str(v) for v in values],
            }
        )
    return rows

def region_to_list(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert interest_by_region DataFrame to list of dicts like:
    { geoCode, geoName, value: [..], formattedValue: [".."] }
    """
    if df.empty:
        return []
    df = df.copy()
    # Index holds region name; columns are query terms
    df = df.reset_index()
    name_field = df.columns[0]
    value_cols = [c for c in df.columns if c != name_field]
    out: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        values = [int(r[c]) if pd.notna(r[c]) else 0 for c in value_cols]
        out.append(
            {
                "geoCode": r.get("geoCode", None),
                "geoName": str(r[name_field]),
                "value": values,
                "formattedValue": [str(v) for v in values],
            }
        )
    return out

def related_topics_to_list(related_topics: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convert related_topics dict to top/rising arrays.
    Structure from pytrends: { '<term>': {'top': df, 'rising': df}, ...}
    We merge across terms and keep top scores.
    """
    top: List[Dict[str, Any]] = []
    rising: List[Dict[str, Any]] = []

    for term, buckets in (related_topics or {}).items():
        for bucket_name in ["top", "rising"]:
            df = buckets.get(bucket_name)
            if isinstance(df, pd.DataFrame) and not df.empty:
                df = df.copy().fillna("")
                for _, row in df.iterrows():
                    item = {
                        "topic": {
                            "title": str(row.get("topic_title", row.get("title", ""))),
                            "type": str(row.get("topic_type", row.get("type", ""))),
                        },
                        "value": int(row.get("value", 0)),
                        "term": term,
                    }
                    if bucket_name == "top":
                        top.append(item)
                    else:
                        rising.append(item)
    # Keep unique by topic title + type + term; keep highest value
    def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        best: Dict[str, Dict[str, Any]] = {}
        for it in items:
            key = f'{it["term"]}|{it["topic"]["title"]}|{it["topic"]["type"]}'
            if key not in best or it["value"] > best[key]["value"]:
                best[key] = it
        return sorted(best.values(), key=lambda x: x["value"], reverse=True)

    return {"top": dedupe(top), "rising": dedupe(rising)}

def related_queries_to_list(related_queries: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convert related_queries dict to top/rising arrays.
    """
    top: List[Dict[str, Any]] = []
    rising: List[Dict[str, Any]] = []

    for term, buckets in (related_queries or {}).items():
        for bucket_name in ["top", "rising"]:
            df = buckets.get(bucket_name)
            if isinstance(df, pd.DataFrame) and not df.empty:
                df = df.copy().fillna("")
                for _, row in df.iterrows():
                    item = {
                        "query": str(row.get("query", "")),
                        "value": int(row.get("value", 0)),
                        "formattedValue": str(row.get("formattedValue", "")) or str(row.get("value", "")),
                        "term": term,
                    }
                    if bucket_name == "top":
                        top.append(item)
                    else:
                        rising.append(item)

    def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        best: Dict[str, Dict[str, Any]] = {}
        for it in items:
            key = f'{it["term"]}|{it["query"]}'
            if key not in best or it["value"] > best[key]["value"]:
                best[key] = it
        return sorted(best.values(), key=lambda x: x["value"], reverse=True)

    return {"top": dedupe(top), "rising": dedupe(rising)}