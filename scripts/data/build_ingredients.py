"""Build the unified fragrance-ingredient table, one row per material, keyed by CAS number.

Sources (all under datasets/):
  pyrfume goodscents   odor descriptors and text, odor strength, smelling dilution, substantivity (h)
  pyrfume leffingwell  odor descriptors and text
  pyrfume arctander    odor text (natural and synthetic materials, 1960)
  pyrfume ifra_2019    IFRA ingredient glossary: ingredients used by the industry, 3 descriptors
  pyrfume abraham_2012 measured odor detection thresholds
  perfumenuke          note tier, typical and max % in concentrate, impact, longevity
  FINAL.csv            molecular weight, SMILES, odor descriptors (by PubChem CID)
  processed/ifra_standards.csv   IFRA restriction / prohibition, category 4 limit
  eu_regulation/...csv           EU fragrance allergens (Reg. 2023/1545)

Molecules known only by PubChem CID are matched to a CAS through the CID columns of
GoodScents and Arctander. Materials without any CAS keep an id `CID:<n>` or `NAME:<slug>`.

Run extract_ifra_limits.py first. Writes processed/ingredients.csv.

Usage:
  python scripts/data/build_ingredients.py [datasets_dir]
"""
import ast
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

CAS_RE = re.compile(r"\b(\d{2,7})-(\d{2})-(\d)\b")


def valid_cas(cas: str) -> bool:
    m = CAS_RE.fullmatch(cas)
    if not m:
        return False
    digits = (m.group(1) + m.group(2))[::-1]
    return sum((i + 1) * int(d) for i, d in enumerate(digits)) % 10 == int(m.group(3))


def cas_list(text: str):
    return [c for c in dict.fromkeys(m.group(0) for m in CAS_RE.finditer(text or "")) if valid_cas(c)]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def read_csv(path: Path):
    csv.field_size_limit(10**9)
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def terms(values):
    out = []
    for v in values:
        v = " ".join(str(v).lower().replace("_", " ").split())
        if v and v not in out:
            out.append(v)
    return out


class Table:
    """Accumulates fields per ingredient id, keeping the first value set for each field."""

    def __init__(self):
        self.rows = defaultdict(lambda: {"descriptors": Counter(), "sources": [], "other_cas": []})
        self.cid_to_id = {}

    def key(self, cas=None, cid=None, name=None):
        if cas:
            return cas
        if cid and str(cid) in self.cid_to_id:
            return self.cid_to_id[str(cid)]
        if cid:
            return f"CID:{cid}"
        return f"NAME:{slug(name)}" if name else None

    def set(self, key, source, **fields):
        row = self.rows[key]
        if source not in row["sources"]:
            row["sources"].append(source)
        if not row.get("cas") and valid_cas(key):
            row["cas"] = key
        for k, v in fields.items():
            if v not in (None, "", []) and row.get(k) in (None, "", []):
                row[k] = v
        return row

    def add_descriptors(self, key, values):
        self.rows[key]["descriptors"].update(terms(values))

    def merge_without_cas(self):
        """Fold rows lacking a CAS into the CAS row with the same SMILES or the same name."""
        by_smiles, by_name = {}, {}
        for k, r in self.rows.items():
            if r.get("cas"):
                if r.get("smiles"):
                    by_smiles.setdefault(r["smiles"], k)
                if r.get("name"):
                    by_name.setdefault(r["name"].lower(), k)
        merged = 0
        for k in [k for k, r in self.rows.items() if not r.get("cas")]:
            r = self.rows[k]
            target = by_smiles.get(r.get("smiles") or "") or by_name.get((r.get("name") or "").lower())
            if not target:
                continue
            dst = self.rows[target]
            for f, v in r.items():
                if f == "descriptors":
                    dst["descriptors"].update(v)
                elif f in ("sources", "other_cas"):
                    dst[f].extend(x for x in v if x not in dst[f])
                elif v not in (None, "", []) and dst.get(f) in (None, "", []):
                    dst[f] = v
            del self.rows[k]
            merged += 1
        return merged


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "datasets"
    pyr = root / "pyrfume"
    t = Table()

    # --- CID <-> CAS links -------------------------------------------------------------
    opl = read_csv(pyr / "goodscents" / "data_rw_opl.csv")
    arct = read_csv(pyr / "arctander_1960" / "arctander.csv")
    for r in opl:
        for cas in cas_list(r["CAS Number"])[:1]:
            if r["CID"]:
                t.cid_to_id.setdefault(r["CID"], cas)
    for r in arct:
        for cas in cas_list(r["CAS"])[:1]:
            for cid in (r.get("new_CID"), r.get("CID")):
                if cid and cid.isdigit():
                    t.cid_to_id.setdefault(cid, cas)
    for r in read_csv(pyr / "goodscents" / "stimuli.csv"):
        for cas in cas_list(r["Stimulus"])[:1]:
            if r["CID"].isdigit():
                t.cid_to_id.setdefault(r["CID"], cas)
    for r in read_csv(pyr / "leffingwell" / "stimuli.csv"):
        for cas in cas_list(r["cas"])[:1]:
            if r["CID"].isdigit():  # negative CIDs are Pyrfume placeholders
                t.cid_to_id.setdefault(r["CID"], cas)

    # --- perfumenuke: curated perfumer data (highest priority for names) -----------------
    pn = json.load(open(root / "perfumenuke" / "data" / "materials.json", encoding="utf-8"))
    for m in pn["materials"]:
        cas = (cas_list(m.get("cas", "")) or [None])[0]
        if m.get("is_solvent"):
            continue
        k = t.key(cas=cas, name=m["name"])
        t.set(k, "perfumenuke", cas=cas, name=m["name"],
              note_tier={"TOP": "tête", "HEART": "cœur", "BASE": "fond"}.get(m.get("note"), ""),
              pn_longevity_hours=m.get("longevity"), pn_impact=m.get("impact"),
              typical_pct_in_concentrate=round(100 * m["avg_in_concentrate"], 4) if m.get("avg_in_concentrate") is not None else "",
              max_pct_in_concentrate=round(100 * m["max_in_concentrate"], 4) if m.get("max_in_concentrate") is not None else "",
              is_natural="oui" if m.get("is_natural") else ("non" if m.get("is_natural") is False else ""),
              odor_description=m.get("scent", ""))
        t.add_descriptors(k, m.get("tags", []))

    # --- IFRA glossary 2019 -----------------------------------------------------------
    for r in read_csv(pyr / "ifra_2019" / "ifra-fragrance-ingredient-glossary---oct-2019.csv"):
        cases = cas_list(r["CAS number"])
        k = t.key(cas=cases[0] if cases else None, name=r["Principal name"])
        desc = [r["Primary descriptor"], r["Descriptor 2"], r["Descriptor 3"]]
        row = t.set(k, "ifra_glossary_2019", cas=cases[0] if cases else None, name=r["Principal name"],
                    ifra_glossary_descriptors="; ".join(terms(desc)), in_ifra_glossary_2019="oui")
        row["other_cas"].extend(c for c in cases[1:] if c not in row["other_cas"])
        t.add_descriptors(k, desc)

    # --- GoodScents ---------------------------------------------------------------------
    opl_common = {r["TGSC OPL ID"]: r["Common Name"] for r in read_csv(pyr / "goodscents" / "opl.csv")}
    tgsc = {}
    for r in opl:
        cases = cas_list(r["CAS Number"])
        if r["TGSC ID"] not in tgsc:
            tgsc[r["TGSC ID"]] = (cases[0] if cases else None, r)
    odor_by_id = defaultdict(list)
    for r in read_csv(pyr / "goodscents" / "data_rw_odor.csv"):
        odor_by_id[r["TGSC ID"]].append(r)
    for tid, recs in odor_by_id.items():
        cas, o = tgsc.get(tid, (None, {}))
        name = opl_common.get(o.get("TGSC OPL ID", "")) or o.get("Name", "")
        k = t.key(cas=cas, cid=o.get("CID") or None, name=name or f"tgsc-{tid}")
        subst = [float(r["Substantivity (Hours)"]) for r in recs if r["Substantivity (Hours)"]]
        row = t.set(k, "goodscents", cas=cas, name=name, cid=o.get("CID"),
                    molecular_weight=o.get("Molecular Weight"), fema_number=o.get("FEMA Number"),
                    odor_strength=next((r["Strength"] for r in recs if r["Strength"]), ""),
                    smelling_dilution_pct=next((r["Recommended Max Concentration %"] for r in recs if r["Recommended Max Concentration %"]), ""),
                    substantivity_hours=statistics.median(subst) if subst else "",
                    odor_description=next((r["Description"] for r in recs if r["Description"]), ""))
        row["other_cas"].extend(c for c in cas_list(o.get("Other CAS Number", "")) if c not in row["other_cas"])
        for r in recs:
            try:
                t.add_descriptors(k, ast.literal_eval(r["Tags"]))
            except (ValueError, SyntaxError):
                pass

    # --- Leffingwell --------------------------------------------------------------------
    for r in read_csv(pyr / "leffingwell" / "leffingwell_data.csv"):
        cas = (cas_list(r["cas"]) or [None])[0]
        k = t.key(cas=cas, name=r["chemical_name"])
        t.set(k, "leffingwell", cas=cas, name=r["chemical_name"], smiles=r["smiles"], odor_description=r["odor_data"])
        try:
            t.add_descriptors(k, ast.literal_eval(r["odor_labels_filtered"]))
        except (ValueError, SyntaxError):
            pass

    # --- Arctander ----------------------------------------------------------------------
    labels = {r["Stimulus"]: r["Labels"] for r in read_csv(pyr / "arctander_1960" / "behavior_1_sparse.csv")}
    stimuli = {r["CAS"]: r["Stimulus"] for r in read_csv(pyr / "arctander_1960" / "stimuli.csv")}
    for r in arct:
        cas = (cas_list(r["CAS"]) or [None])[0]
        cid = r.get("new_CID") or r.get("CID")
        k = t.key(cas=cas, cid=cid if cid and cid.isdigit() else None, name=r["ChemicalName"].title())
        t.set(k, "arctander_1960", cas=cas, name=r["ChemicalName"].title(), smiles=r["SMILES"],
              molecular_weight=r["MW"], odor_description=r["Description"])
        t.add_descriptors(k, (labels.get(stimuli.get(r["CAS"], ""), "") or "").split(";"))

    # --- FINAL.csv (by PubChem CID) -----------------------------------------------------
    final = read_csv(root / "FINAL.csv")
    flags = list(final[0])[15:]
    for r in final:
        k = t.key(cid=r["CID"], name=r["name"])
        t.set(k, "final_csv", cid=r["CID"], name=r["name"], smiles=r["representative_smiles"],
              molecular_weight=r["molecular_weight"])
        t.add_descriptors(k, [f for f in flags if r[f] == "1" and f != "odorless"])

    # --- Abraham 2012 odor detection thresholds (log 1/ODT, ODT in ppm) --------------------
    for r in read_csv(pyr / "abraham_2012" / "behavior.csv"):
        try:
            ppm = 10 ** (-float(r["Log (1/ODT)"]))
        except ValueError:
            continue
        k = t.key(cid=r["Stimulus"])
        if k in t.rows:
            t.set(k, "abraham_2012", odor_threshold_ppm=f"{ppm:.4g}")

    merged = t.merge_without_cas()

    # --- Regulatory: IFRA standards and EU allergens ------------------------------------
    for r in read_csv(root / "processed" / "ifra_standards.csv"):
        cases = cas_list(r["cas"])
        k = t.key(cas=cases[0] if cases else None, name=r["name"])
        if k not in t.rows:  # restricted material missing from the odor sources
            t.set(k, "ifra_standards", cas=cases[0] if cases else None, name=r["name"])
        for cas in cases:
            if cas in t.rows:
                row = t.rows[cas]
                row["name"] = row.get("name") or r["name"]
                row["ifra_standard_ids"] = "; ".join(filter(None, [row.get("ifra_standard_ids", ""), r["standard_id"]]))
                row["ifra_status"] = row.get("ifra_status") or r["status"]
                row["ifra_cat4_max_pct"] = row.get("ifra_cat4_max_pct") or r["cat_4"]
    for r in read_csv(root / "eu_regulation" / "eu_fragrance_allergens_2023_1545.csv"):
        for cas in cas_list(r["cas"]):
            if cas in t.rows:
                t.rows[cas]["eu_allergen_ref"] = t.rows[cas].get("eu_allergen_ref") or r["annex_iii_ref"]

    # --- Write ----------------------------------------------------------------------------
    fields = ["ingredient_id", "cas", "other_cas", "name", "cid", "smiles", "molecular_weight", "fema_number",
              "is_natural", "odor_descriptors", "odor_description", "ifra_glossary_descriptors",
              "note_tier", "substantivity_hours", "pn_longevity_hours", "odor_strength", "pn_impact",
              "smelling_dilution_pct", "odor_threshold_ppm", "typical_pct_in_concentrate",
              "max_pct_in_concentrate", "ifra_status", "ifra_cat4_max_pct", "ifra_standard_ids",
              "eu_allergen_ref", "in_ifra_glossary_2019", "sources"]
    out_rows = []
    for k, row in t.rows.items():
        row["ingredient_id"] = k
        row["odor_descriptors"] = "; ".join(d for d, _ in row["descriptors"].most_common())
        row["other_cas"] = " ".join(c for c in row["other_cas"] if c != row.get("cas"))
        row["sources"] = "; ".join(row["sources"])
        if row.get("substantivity_hours") != "" and row.get("substantivity_hours") is not None:
            row["substantivity_hours"] = f"{row['substantivity_hours']:g}"
        out_rows.append({f: row.get(f, "") or "" for f in fields})
    out_rows.sort(key=lambda r: (r["cas"] == "", r["name"].lower()))

    out = root / "processed" / "ingredients.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    n = len(out_rows)
    cnt = lambda f: sum(1 for r in out_rows if r[f])
    print(f"{n} ingredients -> {out} ({merged} lignes sans CAS fusionnees par SMILES ou nom)")
    print(f"  avec CAS {cnt('cas')} | descripteurs {cnt('odor_descriptors')} | description {cnt('odor_description')}")
    print(f"  etage {cnt('note_tier')} | tenacite {cnt('substantivity_hours')} | intensite {cnt('odor_strength')} | seuil {cnt('odor_threshold_ppm')}")
    print(f"  glossaire IFRA {cnt('in_ifra_glossary_2019')} | norme IFRA {cnt('ifra_status')} | allergene UE {cnt('eu_allergen_ref')}")
    print("  sources:", Counter(s for r in out_rows for s in r["sources"].split("; ")).most_common())


if __name__ == "__main__":
    main()
