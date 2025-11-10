from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from lxml import etree

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def export_json(payloads: List[Dict[str, Any]], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    ensure_dir(out_path.parent)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payloads, f, ensure_ascii=False, indent=2)
    return out_path

def export_csv(df: pd.DataFrame, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    ensure_dir(out_path.parent)
    df.to_csv(out_path, index=False)
    return out_path

def export_excel(df: pd.DataFrame, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    ensure_dir(out_path.parent)
    df.to_excel(out_path, index=False)
    return out_path

def export_html(df: pd.DataFrame, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    ensure_dir(out_path.parent)
    html = df.to_html(index=False)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path

def export_xml(payloads: List[Dict[str, Any]], out_path: str | Path) -> Path:
    """
    Basic XML export of the JSON payloads.
    """
    out_path = Path(out_path)
    ensure_dir(out_path.parent)

    root = etree.Element("GoogleTrendsResults")
    for p in payloads:
        item = etree.SubElement(root, "Result")
        for key, val in p.items():
            node = etree.SubElement(item, key)
            if isinstance(val, (dict, list)):
                node.text = json.dumps(val, ensure_ascii=False)
            else:
                node.text = str(val)

    xml_bytes = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8")
    with open(out_path, "wb") as f:
        f.write(xml_bytes)
    return out_path