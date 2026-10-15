"""Extract IFRA Standards (PDF) into structured CSV files.

Reads every PDF listed in ifra_standards_index.csv, converts it to text with
`pdftotext -raw` (poppler) and writes:

  processed/ifra_limits.csv          one row per standard and product category (long format)
  processed/ifra_standards.csv       one row per standard, one column per category (wide format)
  processed/ifra_categories.csv      short description of the 18 IFRA product categories

Usage:
  python scripts/data/extract_ifra_limits.py [datasets_dir]
"""
import csv
import re
import subprocess
import sys
from pathlib import Path

CATEGORIES = [
    ("1", "Produits pour les lèvres"),
    ("2", "Déodorants et anti-transpirants (aisselles)"),
    ("3", "Produits pour les yeux, le visage masculin, peau rasée"),
    ("4", "Parfumerie fine hydroalcoolique (eau de parfum, eau de toilette, parfum corporel)"),
    ("5A", "Crèmes et lotions pour le corps"),
    ("5B", "Crèmes pour le visage"),
    ("5C", "Crèmes pour les mains"),
    ("5D", "Crèmes, huiles et lingettes pour bébé"),
    ("6", "Bain de bouche, dentifrice"),
    ("7A", "Produits capillaires rincés, colorations"),
    ("7B", "Produits capillaires sans rinçage"),
    ("8", "Produits intimes et lingettes pour bébé"),
    ("9", "Produits rincés pour le corps (savon, gel douche, shampooing)"),
    ("10A", "Produits ménagers (hors aérosols)"),
    ("10B", "Désodorisants d'intérieur en aérosol"),
    ("11A", "Contact cutané minimal (supports non tissés), sans exposition UV"),
    ("11B", "Contact cutané minimal, avec exposition UV"),
    ("12", "Sans contact cutané (bougies, diffuseurs non spray)"),
]
CAT_IDS = [c for c, _ in CATEGORIES]

CAS_RE = re.compile(r"\b\d{2,7}-\d{2}-\d\b")
CAT_RE = re.compile(r"Category\s+(\d{1,2}[A-D]?)\s+(.+?)(?=\s+Category\s|\s*$)")


def pdf_text(path: Path) -> str:
    # -raw keeps the reading order of the two-column category table; -layout can shift
    # values between columns when a page break splits the table.
    out = subprocess.run(["pdftotext", "-raw", str(path), "-"], capture_output=True)
    return out.stdout.decode("utf-8", "replace")


def parse_limit(raw: str):
    """Return (limit_pct, limit_text). limit_pct is the number as printed, None when not numeric."""
    raw = " ".join(raw.split())
    m = re.match(r"^([\d.]+)\s*%", raw)
    if m:
        return m.group(1).rstrip("."), raw
    if raw.lower().startswith("no restriction"):
        return None, "No Restriction"
    return None, raw


def parse_standard(text: str):
    rec = re.search(r"RECOMMENDATION:\s+([A-Z]+)", text)
    cas_block = re.search(r"CAS-No\.?:(.*?)(?:The scope|Synonyms:|History:)", text, re.S)
    limits = {}
    for line in text.splitlines():
        for cat, val in CAT_RE.findall(line):
            if cat in CAT_IDS and cat not in limits:
                limits[cat] = parse_limit(val)
    notebox = re.search(r"Note box\s*\n(.*?)(?:\n\s*\n[A-Z ]{6,}:|\Z)", text, re.S)
    return {
        "recommendation": rec.group(1) if rec else "",
        "cas_in_pdf": " ".join(dict.fromkeys(CAS_RE.findall(cas_block.group(1)))) if cas_block else "",
        "limits": limits,
        "notebox": " ".join(notebox.group(1).split())[:1000] if notebox else "",
    }


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "datasets"
    index = list(csv.DictReader(open(root / "ifra_standards" / "ifra_standards_index.csv", encoding="utf-8")))
    out_dir = root / "processed"
    out_dir.mkdir(exist_ok=True)

    long_rows, wide_rows = [], []
    for std in index:
        parsed = parse_standard(pdf_text(root / "ifra_standards" / "pdf" / f"{std['standard_id']}.pdf"))
        cas = parsed["cas_in_pdf"] or std["cas"]
        status = parsed["recommendation"] or {"R": "RESTRICTION", "P": "PROHIBITION", "S": "SPECIFICATION"}.get(std["type"], "")
        base = {"standard_id": std["standard_id"], "name": std["name"], "cas": cas,
                "status": status, "amendment": std["amendment"], "publication": std["date"]}
        wide = dict(base)
        for cat in CAT_IDS:
            pct, txt = parsed["limits"].get(cat, (None, ""))
            if status == "PROHIBITION":
                pct, txt = "0", "Prohibited"
            wide[f"cat_{cat}"] = txt if pct is None else pct
            if txt:
                long_rows.append({**base, "category": cat, "limit_pct": "" if pct is None else pct, "limit_text": txt})
        wide["notebox"] = parsed["notebox"]
        wide_rows.append(wide)

    with open(out_dir / "ifra_limits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(long_rows[0]))
        w.writeheader()
        w.writerows(long_rows)
    with open(out_dir / "ifra_standards.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(wide_rows[0]))
        w.writeheader()
        w.writerows(wide_rows)
    with open(out_dir / "ifra_categories.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "description_fr"])
        w.writerows(CATEGORIES)

    by_status = {}
    for r in wide_rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    restricted = [r for r in wide_rows if r["status"] == "RESTRICTION"]
    complete = sum(all(r[f"cat_{c}"] != "" for c in CAT_IDS) for r in restricted)
    print(f"{len(wide_rows)} normes {by_status} | restrictions avec les 18 categories : {complete}/{len(restricted)}")
    print(f"{len(long_rows)} lignes dans ifra_limits.csv")


if __name__ == "__main__":
    main()
