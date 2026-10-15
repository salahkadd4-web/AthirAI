"""Extract the recipes of Piesse, *The Art of Perfumery* (1857, public domain) into a CSV.

Recipes are blocks of consecutive lines shaped like `Otto of rose,   1 drachm.`.
Ditto marks (") repeat words or the unit of the line above. The title is the closest
heading above the block (`JASMINE.--`, `BOUQUET DU ROI.`).

Writes processed/piesse_formulas.csv, one row per ingredient line, with the quantity
converted to an approximate volume in ml and its share of the recipe (pct_approx).

Usage:
  python scripts/data/extract_piesse_formulas.py [datasets_dir]
"""
import csv
import re
import sys
from fractions import Fraction
from pathlib import Path

# Approximate British apothecary / imperial measures in ml (weights counted as 1 g = 1 ml).
UNIT_ML = {
    "gallon": 4546.0, "quart": 1136.5, "pint": 568.3, "oz": 28.41, "ounce": 28.41,
    "cwt": 50802.0, "drachm": 3.55, "dr": 3.55, "drop": 0.05, "lb": 453.6, "grain": 0.0648, "scruple": 1.296,
}
UNITS = "|".join(sorted([u + "s?" for u in UNIT_ML] + ['"'], key=len, reverse=True))
DITTO = r'["“”]'
LINE_RE = re.compile(
    rf"^\s*(?P<name>(?:{DITTO}|[A-Za-z(]).*?),?\s{{2,}}(?P<qty>\d+(?:\s*\d/\d)?|\d/\d|{DITTO})\s*(?P<unit>{UNITS})?\s*\.?\s*$"
)
GROUP_RE = re.compile(rf"^\s*(?P<name>(?:{DITTO}|[A-Za-z(])[^}}]*?),?\s*\}}(?P<rest>.*)$")
GROUP_QTY_RE = re.compile(rf"(?P<qty>\d+(?:\s*\d/\d)?|\d/\d)\s*(?P<unit>{UNITS})?\s*\.?\s*$")
ORIGIN_PREFIX_RE = re.compile(r"^\s*[A-Z]{3,}(?: [A-Z]+)*,\s{2,}")
CONNECTORS = {"of", "de", "du", "des", "la", "le"}
TITLE_RE = re.compile(r"^\s*([A-Z][A-Z0-9' &,.\-]{2,60}?)\.(?:--|\s*$)")


def parse_qty(q: str):
    q = q.strip()
    if re.fullmatch(DITTO, q):
        return None
    total = Fraction(0)
    for part in q.split():
        total += Fraction(part)
    return float(total)


def norm_unit(u: str) -> str:
    u = (u or "").lower().rstrip("s") if u and not re.fullmatch(DITTO, u) else u
    return {"ounce": "oz", "dr": "drachm"}.get(u, u)


def resolve_name(raw: str, prev: str) -> str:
    """Replace ditto marks by the matching words of the previous ingredient name."""
    tokens = raw.replace(",", " ").split()
    if not any(re.fullmatch(DITTO + "+", t) for t in tokens):
        return " ".join(tokens)
    if not prev:
        return " ".join(t for t in tokens if not re.fullmatch(DITTO + "+", t))
    lead = 0
    while lead < len(tokens) and re.fullmatch(DITTO + "+", tokens[lead]):
        lead += 1
    trail = 0
    while trail < len(tokens) - lead and re.fullmatch(DITTO + "+", tokens[len(tokens) - 1 - trail]):
        trail += 1
    middle = tokens[lead:len(tokens) - trail]
    prev_words = prev.split()
    suffix = prev_words[len(prev_words) - trail:] if trail else []
    prefix = []
    if lead:
        # A leading ditto repeats the head of the previous name, up to its last connector
        # ("Extract of", "Esprit de"), or everything but its last word.
        head = prev_words[:len(prev_words) - trail]
        cut = max((i for i, w in enumerate(head) if w.lower() in CONNECTORS), default=len(head) - 2)
        prefix = head[:cut + 1]
    return " ".join(prefix + middle + suffix)


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "datasets"
    lines = open(root / "books" / "piesse_art_of_perfumery_1857.txt", encoding="utf-8").read().splitlines()

    rows, block, title = [], [], ""
    formula_id = 0

    def flush():
        nonlocal block, formula_id
        with_unit = sum(1 for r in block if r["quantity"] is not None and r["unit"] in UNIT_ML)
        if len(block) >= 2 and with_unit >= 2 and with_unit >= 0.6 * len(block):
            formula_id += 1
            total = sum(r["quantity_ml_approx"] or 0 for r in block)
            for r in block:
                r["formula_id"] = f"PIESSE-{formula_id:03d}"
                r["title"] = title
                ml = r["quantity_ml_approx"]
                r["pct_approx"] = round(100 * ml / total, 2) if ml and total else ""
                r["quantity_ml_approx"] = round(ml, 3) if ml else ""
            rows.extend(block)
        block = []

    prev_name, prev_unit, prev_qty = "", "", None
    group = []  # lines joined by a brace: `Extract of jasmine, } of each, 1/2 pint.`

    def add(no, raw, name, qty_raw, unit_raw):
        nonlocal prev_unit, prev_qty
        if re.search(r"\d", re.sub(r"\(.*?\)|\d+\s*(?:over proof|o\.p\.)", "", name)):
            return  # "Caraway, 25 [lb] 16 oz.": extraction-yield tables; "60 over proof" spirit is kept
        qty = parse_qty(qty_raw) if qty_raw else None
        qty = prev_qty if qty is None else qty
        unit = norm_unit(unit_raw)
        if not unit or re.fullmatch(DITTO, unit):
            unit = prev_unit
        ml = qty * UNIT_ML[unit] if qty is not None and unit in UNIT_ML else None
        block.append({"line": no, "ingredient_raw": raw, "ingredient": name,
                      "quantity": qty, "unit": unit, "quantity_ml_approx": ml})
        prev_unit, prev_qty = unit, qty

    def close_group():
        shared = next((g for g in group if g["qty"]), None)
        for g in group:
            add(g["line"], g["raw"], g["name"], shared["qty"] if shared else None, shared["unit"] if shared else None)
        group.clear()

    for no, line in enumerate(lines, 1):
        if "yield" in line:
            line = ""  # extraction-yield tables ("10 yield about 1 oz."), not recipes
        line = ORIGIN_PREFIX_RE.sub("", line)  # "TURKEY,   Esprit de rose, ..." (Bouquet of all nations)
        g = GROUP_RE.match(line) if "_{" not in line else None
        if g:
            name = resolve_name(g.group("name"), prev_name)
            q = GROUP_QTY_RE.search(g.group("rest"))
            group.append({"line": no, "raw": line.strip(), "name": name,
                          "qty": q.group("qty") if q else None, "unit": q.group("unit") if q else None})
            prev_name = name
            continue
        if group:
            close_group()
        m = LINE_RE.match(line)
        if m:
            name = resolve_name(m.group("name"), prev_name)
            add(no, line.strip(), name, m.group("qty"), m.group("unit"))
            prev_name = name
            continue
        nxt = lines[no] if no < len(lines) else ""
        if line.strip() == "" and block and (LINE_RE.match(nxt) or GROUP_RE.match(nxt)):
            continue  # blank line inside a recipe
        flush()
        prev_name, prev_unit, prev_qty = "", "", None
        t = TITLE_RE.match(line)
        if t:
            title = t.group(1).strip().rstrip(",")
    flush()

    out = root / "processed" / "piesse_formulas.csv"
    out.parent.mkdir(exist_ok=True)
    fields = ["formula_id", "title", "line", "ingredient", "quantity", "unit", "quantity_ml_approx", "pct_approx", "ingredient_raw"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{formula_id} recettes, {len(rows)} lignes d'ingredients -> {out}")


if __name__ == "__main__":
    main()
