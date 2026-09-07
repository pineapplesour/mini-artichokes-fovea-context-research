#!/usr/bin/env python3
"""Vatican II 16 documents + Code of Canon Law (1983) + CCC Compendium from vatican.va.

All on www.vatican.va (same domain). Run AFTER ccc_vatican.py finishes.
"""
from __future__ import annotations
import asyncio, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.polite_client import PoliteClient
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "christian" / "catholic" / "vatican"
CORPUS = ROOT / "corpus" / "christian"

# Vatican II 16 documents (4 constitutions, 9 decrees, 3 declarations)
VATICAN_II = [
    # (source_id, title, slug under archive/hist_councils/ii_vatican_council/documents/)
    ("christian.catholic.vat2.dei-verbum",          "Dei Verbum (Dogmatic Constitution on Divine Revelation)",      "vat-ii_const_19651118_dei-verbum_en.html"),
    ("christian.catholic.vat2.lumen-gentium",       "Lumen Gentium (Dogmatic Constitution on the Church)",          "vat-ii_const_19641121_lumen-gentium_en.html"),
    ("christian.catholic.vat2.sacrosanctum-concilium","Sacrosanctum Concilium (Constitution on the Sacred Liturgy)","vat-ii_const_19631204_sacrosanctum-concilium_en.html"),
    ("christian.catholic.vat2.gaudium-et-spes",     "Gaudium et Spes (Pastoral Constitution on the Church in the Modern World)","vat-ii_const_19651207_gaudium-et-spes_en.html"),
    ("christian.catholic.vat2.ad-gentes",           "Ad Gentes (Decree on the Church's Missionary Activity)",        "vat-ii_decree_19651207_ad-gentes_en.html"),
    ("christian.catholic.vat2.apostolicam-actuositatem","Apostolicam Actuositatem (Decree on Apostolate of the Laity)","vat-ii_decree_19651118_apostolicam-actuositatem_en.html"),
    ("christian.catholic.vat2.christus-dominus",    "Christus Dominus (Decree on Bishops' Pastoral Office)",          "vat-ii_decree_19651028_christus-dominus_en.html"),
    ("christian.catholic.vat2.inter-mirifica",      "Inter Mirifica (Decree on Means of Social Communication)",       "vat-ii_decree_19631204_inter-mirifica_en.html"),
    ("christian.catholic.vat2.optatam-totius",      "Optatam Totius (Decree on Training of Priests)",                 "vat-ii_decree_19651028_optatam-totius_en.html"),
    ("christian.catholic.vat2.orientalium-ecclesiarum","Orientalium Ecclesiarum (Decree on Eastern Catholic Churches)","vat-ii_decree_19641121_orientalium-ecclesiarum_en.html"),
    ("christian.catholic.vat2.perfectae-caritatis", "Perfectae Caritatis (Decree on Religious Life)",                  "vat-ii_decree_19651028_perfectae-caritatis_en.html"),
    ("christian.catholic.vat2.presbyterorum-ordinis","Presbyterorum Ordinis (Decree on Ministry of Priests)",          "vat-ii_decree_19651207_presbyterorum-ordinis_en.html"),
    ("christian.catholic.vat2.unitatis-redintegratio","Unitatis Redintegratio (Decree on Ecumenism)",                  "vat-ii_decree_19641121_unitatis-redintegratio_en.html"),
    ("christian.catholic.vat2.dignitatis-humanae",  "Dignitatis Humanae (Declaration on Religious Freedom)",           "vat-ii_decl_19651207_dignitatis-humanae_en.html"),
    ("christian.catholic.vat2.gravissimum-educationis","Gravissimum Educationis (Declaration on Christian Education)","vat-ii_decl_19651028_gravissimum-educationis_en.html"),
    ("christian.catholic.vat2.nostra-aetate",       "Nostra Aetate (Declaration on Non-Christian Religions)",          "vat-ii_decl_19651028_nostra-aetate_en.html"),
]
VAT2_BASE = "https://www.vatican.va/archive/hist_councils/ii_vatican_council/documents/"


# Code of Canon Law (1983) — index page
CIC_INDEX = "https://www.vatican.va/archive/cod-iuris-canonici/cic_index_en.html"
CIC_BASE  = "https://www.vatican.va/archive/cod-iuris-canonici/eng/documents/"


# CCC Compendium — single landing page
COMP_INDEX = "https://www.vatican.va/archive/compendium_ccc/documents/archive_2005_compendium-ccc_en.html"


def parse_vat2_document(html: str) -> str:
    from bs4 import BeautifulSoup
    s = BeautifulSoup(html, "html.parser")
    for x in s.find_all(["script","style","header","footer"]): x.decompose()
    body = s.body or s
    txt = body.get_text("\n", strip=True)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=RAW)
    sw = JsonlWriter(CORPUS / "sources.jsonl")
    pw = JsonlWriter(CORPUS / "passages.jsonl")

    try:
        # Vatican II
        for source_id, title, slug in VATICAN_II:
            url = VAT2_BASE + slug
            cache = RAW / "vat2" / slug
            html = await client.get(url, cache_path=cache, expect_min_size=2000)
            if not html:
                print(f"  ! vat2 fail {slug}")
                continue
            text = parse_vat2_document(html)
            sw.write({
                "source_id": source_id, "religion":"christian",
                "tradition":"catholic", "school":"vatican-ii",
                "source_kind":"official_doctrine",
                "authority_level":90, "authority_label":"official_core_doctrine",
                "title": title, "subtitle":"Second Vatican Council document",
                "author_body":"Second Vatican Council (1962-65)",
                "edition":"vatican.va",
                "language":"en","script":"latn",
                "source_url": url,
                "license":"Vatican copyright (educational use OK)",
                "license_notes":"Vatican Copyright Office Standard.",
                "valid_from":"1962","valid_to":"","text_hash":"",
            })
            # Split into ~6000-char chunks at \n\n boundaries
            paras = re.split(r"\n\s*\n", text)
            buf=[]; cur_len=0; idx=0
            for p in paras:
                if cur_len + len(p) > 6000 and buf:
                    body = "\n\n".join(buf).strip()
                    pid = f"{source_id}.{idx:03d}"
                    pw.write({
                        "passage_id":pid,"source_id":source_id,
                        "canonical_ref": f"{title} §{idx+1}",
                        "parent_ref": title[:60], "ref_sort": idx,
                        "language":"en","script":"latn",
                        "text":body,"normalized_text":normalize_text(body),
                        "heading":"" if idx>0 else title,
                        "tags_json":json.dumps(["vatican-ii"], ensure_ascii=False),
                        "text_hash": text_hash(body),
                    })
                    idx+=1; buf=[p]; cur_len=len(p)
                else:
                    buf.append(p); cur_len += len(p)
            if buf:
                body = "\n\n".join(buf).strip()
                pid = f"{source_id}.{idx:03d}"
                pw.write({
                    "passage_id":pid,"source_id":source_id,
                    "canonical_ref": f"{title} §{idx+1}",
                    "parent_ref": title[:60], "ref_sort": idx,
                    "language":"en","script":"latn",
                    "text":body,"normalized_text":normalize_text(body),
                    "heading":"" if idx>0 else title,
                    "tags_json":json.dumps(["vatican-ii"], ensure_ascii=False),
                    "text_hash": text_hash(body),
                })
            print(f"  vat2 {source_id}: ok")

        # Code of Canon Law - fetch index
        cic_idx = await client.get(CIC_INDEX, cache_path=RAW / "cic" / "_index.html", expect_min_size=1000)
        if cic_idx:
            from bs4 import BeautifulSoup
            s = BeautifulSoup(cic_idx, "html.parser")
            book_links = []
            for a in s.find_all("a", href=True):
                h = a["href"]
                if "documents/" in h or h.endswith(".html"):
                    if "cic" in h.lower() or "_book" in h.lower() or "_can" in h.lower() or "_index" not in h.lower():
                        book_links.append(h)
            print(f"  cic candidate links: {len(set(book_links))}")
            sw.write({
                "source_id":"christian.catholic.cic-1983.en",
                "religion":"christian", "tradition":"catholic", "school":"latin",
                "source_kind":"canon_law", "authority_level":90,
                "authority_label":"official_core_doctrine",
                "title":"Code of Canon Law (1983) — Latin Church",
                "subtitle":"vatican.va English edition",
                "author_body":"John Paul II, Holy See",
                "edition":"vatican.va archive",
                "language":"en","script":"latn",
                "source_url": CIC_INDEX,
                "license":"Vatican copyright (educational use OK)",
                "license_notes":"Vatican Copyright Office Standard.",
                "valid_from":"1983","valid_to":"","text_hash":"",
            })
            seen = set()
            for h in book_links:
                if h in seen: continue
                seen.add(h)
                if not h.startswith("http"):
                    if h.startswith("/"):
                        url = "https://www.vatican.va" + h
                    else:
                        url = CIC_INDEX.rsplit("/", 1)[0] + "/" + h
                else:
                    url = h
                cache = RAW / "cic" / h.split("/")[-1]
                html = await client.get(url, cache_path=cache, referer=CIC_INDEX, expect_min_size=1000)
                if not html: continue
                text = parse_vat2_document(html)
                # Split by canon number markers
                # Canons are §nnnn pattern
                # Quick: just split on Can.nn  
                parts = re.split(r"\n(?=Can\.\s*\d{1,4})", text)
                for i, p in enumerate(parts):
                    body = p.strip()
                    if len(body) < 30: continue
                    m = re.match(r"Can\.\s*(\d{1,4})", body)
                    n = int(m.group(1)) if m else (10000 + i)
                    pid = f"christian.catholic.cic-1983.en.{n:04d}.{i:03d}"
                    pw.write({
                        "passage_id":pid,"source_id":"christian.catholic.cic-1983.en",
                        "canonical_ref": f"CIC Can. {n}" if m else f"CIC §{i}",
                        "parent_ref":"CIC 1983",
                        "ref_sort": n,
                        "language":"en","script":"latn",
                        "text":body[:8000],"normalized_text":normalize_text(body[:8000]),
                        "heading":"","tags_json":json.dumps(["canon-law"], ensure_ascii=False),
                        "text_hash": text_hash(body[:8000]),
                    })
            print(f"  cic done.")

        # CCC Compendium - one landing page
        comp_html = await client.get(COMP_INDEX, cache_path=RAW / "compendium" / "index.html", expect_min_size=2000)
        if comp_html:
            text = parse_vat2_document(comp_html)
            sw.write({
                "source_id":"christian.catholic.ccc-compendium.en",
                "religion":"christian","tradition":"catholic","school":"",
                "source_kind":"catechism","authority_level":85,
                "authority_label":"official_core_doctrine",
                "title":"CCC Compendium (2005)",
                "subtitle":"Compendium of the Catechism of the Catholic Church",
                "author_body":"Holy See",
                "edition":"vatican.va",
                "language":"en","script":"latn",
                "source_url": COMP_INDEX,
                "license":"Vatican copyright","license_notes":"Vatican Copyright Office Standard.",
                "valid_from":"2005","valid_to":"","text_hash":"",
            })
            paras = re.split(r"\n\s*\n", text)
            buf=[]; cur_len=0; idx=0
            for p in paras:
                if cur_len+len(p)>6000 and buf:
                    body = "\n\n".join(buf).strip()
                    pid = f"christian.catholic.ccc-compendium.en.{idx:03d}"
                    pw.write({
                        "passage_id":pid,"source_id":"christian.catholic.ccc-compendium.en",
                        "canonical_ref": f"CCC Compendium §{idx+1}",
                        "parent_ref":"CCC Compendium","ref_sort":idx,
                        "language":"en","script":"latn",
                        "text":body,"normalized_text":normalize_text(body),
                        "heading":"","tags_json":"[]","text_hash":text_hash(body),
                    })
                    idx+=1; buf=[p]; cur_len=len(p)
                else:
                    buf.append(p); cur_len+=len(p)

    finally:
        sw.close(); pw.close()
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
