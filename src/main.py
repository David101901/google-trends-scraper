from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from modules.trends_parser import TrendsClient, TrendsOptions
from modules.exporter import (
    export_json,
    export_csv,
    export_excel,
    export_html,
    export_xml,
)
from utils.logger import get_logger

def load_settings(config_path: Path) -> Dict[str, Any]:
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Google Trends Scraper - extract trends by keyword, URL, region, and timeframe."
    )
    p.add_argument("--input", "-i", help="Search term or full Google Trends URL.", default="")
    p.add_argument("--input-file", "-f", help="Path to JSON file with batch inputs.", default="")
    p.add_argument("--geo", help="Region code (e.g., US, PK).", default="")
    p.add_argument("--timeframe", help="Time window (e.g., 'now 7-d', 'today 12-m', '2024-01-01 2024-12-31').", default="")
    p.add_argument("--hl", help="Language code (e.g., en-US).", default="")
    p.add_argument("--tz", help="Timezone offset integer.", default="")
    p.add_argument("--gprop", help="Property: '', images, news, youtube, froogle.", default="")
    p.add_argument("--category", type=int, help="Google Trends category (int).", default=0)
    p.add_argument(
        "--formats",
        help="Comma-separated export formats (json,csv,excel,xml,html).",
        default="",
    )
    p.add_argument("--export-dir", help="Output directory (default from settings.json).", default="")
    p.add_argument("--log-level", help="Logging level.", default="INFO")
    return p.parse_args()

def build_options(args: argparse.Namespace, defaults: Dict[str, Any]) -> TrendsOptions:
    return TrendsOptions(
        hl=args.hl or defaults.get("hl", "en-US"),
        tz=int(args.tz or defaults.get("tz", 0)),
        geo=args.geo or defaults.get("geo", ""),
        timeframe=args.timeframe or defaults.get("timeframe", "today 12-m"),
        gprop=args.gprop or defaults.get("gprop", ""),
        category=int(args.category or defaults.get("category", 0)),
        sleep=float(defaults.get("sleep", 1.0)),
    )

def decide_formats(args: argparse.Namespace, defaults: Dict[str, Any]) -> List[str]:
    if args.formats:
        return [fmt.strip().lower() for fmt in args.formats.split(",") if fmt.strip()]
    return [f.lower() for f in defaults.get("default_formats", ["json", "csv"])]

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    config_path = root / "src" / "config" / "settings.json"
    settings = load_settings(config_path)

    args = parse_args()
    log = get_logger("trends", level=args.log_level)

    if not args.input and not args.input_file:
        log.error("Please provide --input or --input-file.")
        return 2

    export_dir = Path(args.export_dir or settings.get("export_dir", "data/exports"))
    export_dir.mkdir(parents=True, exist_ok=True)

    opts = build_options(args, settings)
    formats = decide_formats(args, settings)

    client = TrendsClient(opts=opts)

    payloads: List[Dict[str, Any]] = []

    try:
        if args.input_file:
            items = client.parse_input_file(args.input_file)
            for term, specific_opts in items:
                if not term:
                    log.warning("Skipping an entry with empty 'input'.")
                    continue
                log.info(f"Fetching trends for: {term}")
                payloads.append(client.fetch(term, override=specific_opts))
        else:
            log.info(f"Fetching trends for: {args.input}")
            payloads.append(client.fetch(args.input, override=opts))
    except Exception as e:
        log.exception(f"Failed to fetch data: {e}")
        return 1

    # Export
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = export_dir / f"google_trends_{ts}"

    # JSON export (full fidelity)
    if "json" in formats:
        out = export_json(payloads, f"{base}.json")
        log.info(f"Wrote JSON: {out}")

    # Tabular view for CSV/Excel/HTML
    df = TrendsClient.to_rows_for_tabular(payloads)
    if not df.empty:
        if "csv" in formats:
            out = export_csv(df, f"{base}.csv")
            log.info(f"Wrote CSV: {out}")
        if "excel" in formats:
            out = export_excel(df, f"{base}.xlsx")
            log.info(f"Wrote Excel: {out}")
        if "html" in formats:
            out = export_html(df, f"{base}.html")
            log.info(f"Wrote HTML: {out}")
    else:
        log.warning("No tabular data available for CSV/Excel/HTML export.")

    if "xml" in formats:
        out = export_xml(payloads, f"{base}.xml")
        log.info(f"Wrote XML: {out}")

    log.info("Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main())