#!/usr/bin/env python3
"""CBETA Taishō Tripiṭaka XML → passages.

Each XML is one sutra (e.g. T01n0001 = 長阿含經). Body is TEI <p> blocks.
We split each sutra into paragraph-level passages.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
CBETA = ROOT / "raw" / "buddhist" / "cbeta-xml" / "T"
CORPUS = ROOT / "corpus" / "buddhist"

NS = {"tei": "http://www.tei-c.org/ns/1.0", "cb": "http://www.cbeta.org/ns/1.0"}

# CBETA Taishō volume → broad category
VOL_CATEGORY = {
    # 1-2: 阿含部 (Agama)
    **{f"T{i:02d}": ("agama", "scripture", 100, "canonical_scripture") for i in range(1, 3)},
    # 3: 本緣部 (Jataka)
    "T03": ("jataka", "scripture", 95, "canonical_scripture"),
    "T04": ("jataka", "scripture", 95, "canonical_scripture"),
    # 5-8: 般若部 (Prajnaparamita)
    **{f"T{i:02d}": ("prajna", "scripture", 100, "canonical_scripture") for i in range(5, 9)},
    # 9-10: 法華部・華嚴部 (Lotus / Avatamsaka)
    "T09": ("lotus_huayan", "scripture", 100, "canonical_scripture"),
    "T10": ("lotus_huayan", "scripture", 100, "canonical_scripture"),
    # 11-12: 寶積部・涅槃部
    "T11": ("ratnakuta", "scripture", 100, "canonical_scripture"),
    "T12": ("nirvana", "scripture", 100, "canonical_scripture"),
    # 13: 大集部
    "T13": ("mahasamnipata", "scripture", 100, "canonical_scripture"),
    # 14-17: 經集部 (Sutra Collection)
    **{f"T{i:02d}": ("sutra_misc", "scripture", 95, "canonical_scripture") for i in range(14, 18)},
    # 18-21: 密教部 (Esoteric / Tantra)
    **{f"T{i:02d}": ("esoteric", "ritual", 80, "official_liturgy_ritual") for i in range(18, 22)},
    # 22-24: 律部 (Vinaya)
    **{f"T{i:02d}": ("vinaya", "vinaya", 90, "official_core_doctrine") for i in range(22, 25)},
    # 25-29: 釋經論部 (Sutra Commentary)
    **{f"T{i:02d}": ("sutra_commentary", "commentary", 70, "authoritative_commentary") for i in range(25, 30)},
    # 30-32: 中觀・瑜伽 (Madhyamaka / Yogacara)
    **{f"T{i:02d}": ("madhyamaka_yogacara", "commentary", 70, "authoritative_commentary") for i in range(30, 33)},
    # 33-39: 經疏部 (Sutra exegesis)
    **{f"T{i:02d}": ("exegesis", "commentary", 70, "authoritative_commentary") for i in range(33, 40)},
    # 40-43: 律疏部・論疏部
    **{f"T{i:02d}": ("commentary", "commentary", 70, "authoritative_commentary") for i in range(40, 44)},
    # 44-48: 諸宗部 (Schools)
    **{f"T{i:02d}": ("school", "commentary", 60, "school_treatise") for i in range(44, 49)},
    # 49-52: 史傳部 (History/Biography)
    **{f"T{i:02d}": ("history", "commentary", 50, "school_treatise") for i in range(49, 53)},
    # 53-54: 事彙部 (Encyclopedic)
    "T53": ("encyclopedic", "commentary", 40, "local_practice"),
    "T54": ("encyclopedic", "commentary", 40, "local_practice"),
    # 55: 目錄部 (Catalogs)
    "T55": ("catalog", "commentary", 30, "educational_summary"),
}


def parse_one(xml_path: Path) -> dict | None:
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return None
    root = tree.getroot()
    title_el = root.find(".//tei:titleStmt/tei:title[@level='m']", NS)
    title = title_el.text.strip() if title_el is not None and title_el.text else xml_path.stem
    author_el = root.find(".//tei:titleStmt/tei:author", NS)
    author = author_el.text.strip() if author_el is not None and author_el.text else ""
    body = root.find(".//tei:text/tei:body", NS)
    if body is None:
        return None
    paragraphs = []
    for p in body.findall(".//tei:p", NS):
        txt = "".join(p.itertext()).strip()
        # Remove footnote markers / line break artifacts
        txt = re.sub(r"\s+", " ", txt).strip()
        if not txt or len(txt) < 2:
            continue
        paragraphs.append(txt)
    return {"title": title, "author": author, "paragraphs": paragraphs}


def main():
    if not CBETA.exists():
        raise SystemExit(f"CBETA not found at {CBETA}")
    CORPUS.mkdir(parents=True, exist_ok=True)
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")

    n_files = 0
    n_passages = 0
    for vol_dir in sorted(CBETA.iterdir()):
        if not vol_dir.is_dir():
            continue
        vol_name = vol_dir.name
        category, kind, auth, label = VOL_CATEGORY.get(vol_name,
            ("misc", "scripture", 80, "canonical_scripture"))
        for xml_file in sorted(vol_dir.glob("*.xml")):
            if True:
                n_files += 1
                parsed = parse_one(xml_file)
                if not parsed or not parsed["paragraphs"]:
                    continue
                # source_id = T01n0001 → bud.maha.cbeta.t.t01n0001
                stem = xml_file.stem.lower()
                m = re.match(r"t(\d+)n(\d+)([a-z]?)$", stem)
                t_no = int(m.group(2)) if m else 0
                source_id = f"bud.maha.cbeta.t.{stem}"
                tradition = "mahayana" if kind in ("scripture","commentary","ritual") else "theravada" if "agama" in category else "common"
                if category == "agama":
                    tradition = "theravada-parallel"
                sources_w.write({
                    "source_id": source_id,
                    "religion": "buddhist",
                    "tradition": tradition,
                    "school": category,
                    "source_kind": kind,
                    "authority_level": auth,
                    "authority_label": label,
                    "title": f"CBETA T No.{t_no} 《{parsed['title']}》",
                    "subtitle": f"Taishō Vol. {vol_name}",
                    "author_body": parsed["author"],
                    "edition": "CBETA XML P5 (2025)",
                    "language": "lzh",
                    "script": "hant",
                    "source_url": f"https://cbetaonline.dila.edu.tw/{stem.upper()}",
                    "license": "CC-BY-NC for non-commercial use with header intact",
                    "license_notes": "CBETA distribution; original public domain Taishō text.",
                    "valid_from": "",
                    "valid_to": "",
                    "text_hash": "",
                })
                for i, para in enumerate(parsed["paragraphs"]):
                    pid = f"{source_id}.{i:05d}"
                    passages_w.write({
                        "passage_id": pid,
                        "source_id": source_id,
                        "canonical_ref": f"{stem.upper()}-p{i+1}",
                        "parent_ref": stem.upper(),
                        "ref_sort": i,
                        "language": "lzh",
                        "script": "hant",
                        "text": para,
                        "normalized_text": normalize_text(para),
                        "heading": parsed["title"] if i == 0 else "",
                        "tags_json": json.dumps([category, vol_name], ensure_ascii=False),
                        "text_hash": text_hash(para),
                    })
                    n_passages += 1
        print(f"  {vol_name}: cumulative files={n_files}, passages={n_passages}")
    sources_w.close()
    passages_w.close()
    print(f"\n[cbeta] files: {n_files}, passages: {n_passages}")


if __name__ == "__main__":
    main()
