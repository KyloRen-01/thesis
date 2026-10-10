from __future__ import annotations
import re
from typing import Dict, List, Optional
import pandas as pd
from transformers import XLMRobertaTokenizer, XLMRobertaForTokenClassification, pipeline
from tqdm import tqdm

# ---------------------------------------------------------------------
# Constants & Regex
# ---------------------------------------------------------------------
REGION_NUM_RE = re.compile(r"\bregion\s+(\d{1,2}|[ivx]{1,4})\b", re.I)
PAREN_NAME_RE = re.compile(r"\(([^)]+region)\)", re.I)

ROMANS = {
    1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii", 9: "ix", 10: "x",
    11: "xi", 12: "xii", 13: "xiii", 14: "xiv", 15: "xv", 16: "xvi", 17: "xvii", 18: "xviii"
}

ISLAND_GROUPS = {"luzon", "visayas", "mindanao"}

BLOCKLIST = {
    "philippine", "philippine sea", "west philippine sea",
    "northern luzon", "southern luzon", "eastern visayas",
    "western visayas", "central visayas",
    "philippine area of responsibility", "area of responsibility"
}

ALIASES_RAW = {
    "metro manila": "National Capital Region (NCR)",
    "ncr": "National Capital Region (NCR)",
    "manila metro": "National Capital Region (NCR)",
    "maynila": "National Capital Region (NCR)",
    "car": "Cordillera Administrative Region (CAR)",
    "barmm": "Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)",
    "armm": "Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)",
    "soccsksargen": "SOCCSKSARGEN Region",
    "region 12": "SOCCSKSARGEN Region",
    "region 11": "Davao Region",
    "region 4a": "CALABARZON",
    "calabarzon": "CALABARZON",
    "region 4b": "MIMAROPA",
    "mimaropa": "MIMAROPA",
    "region 10": "Northern Mindanao"
}

POI_TERMS = {
    "road", "rd", "street", "st", "ave", "avenue", "blvd", "highway", "hwy",
    "bridge", "overpass", "underpass", "rotunda", "roundabout",
    "market", "terminal", "airport", "pier", "port", "wharf", "harbor",
    "school", "church", "chapel", "cemetery", "hospital", "clinic",
    "mall", "plaza", "park", "grounds", "field", "gym", "court",
    "river", "creek", "canal", "subdivision", "subd", "village", "vlge",
    "phase", "blk", "block", "barangay hall", "brgy hall",
    "brgy", "barangay", "volcano", "mount", "mountain"
}

DIRECTIONS = {
    "northern", "southern", "eastern", "western", "north", "south", "east", "west",
    "hilaga", "hilagang", "timog", "timogang", "silangan", "silangang",
    "kanluran", "kanlurang", "amihan", "habagat", "habagatan"
}

VOLCANO_OVERRIDES = {
    "bulkang taal": {"canonical_name": "Taal Volcano", "province": "Batangas"},
    "taal volcano": {"canonical_name": "Taal Volcano", "province": "Batangas"},
    "bulkang mayon": {"canonical_name": "Mayon Volcano", "province": "Albay"},
    "mayon volcano": {"canonical_name": "Mayon Volcano", "province": "Albay"},
    "bulkang bulusan": {"canonical_name": "Bulusan Volcano", "province": "Sorsogon"},
    "bulusan volcano": {"canonical_name": "Bulusan Volcano", "province": "Sorsogon"},
    "bulkang kanlaon": {"canonical_name": "Kanlaon Volcano", "province": "Negros Occidental"},
    "kanlaon volcano": {"canonical_name": "Kanlaon Volcano", "province": "Negros Occidental"},
    "bulkang pinatubo": {"canonical_name": "Mount Pinatubo", "province": "Zambales"},
    "mount pinatubo": {"canonical_name": "Mount Pinatubo", "province": "Zambales"},
    "bulkang hibok-hibok": {"canonical_name": "Mount Hibok-Hibok", "province": "Camiguin"},
    "hibok-hibok volcano": {"canonical_name": "Mount Hibok-Hibok", "province": "Camiguin"},
}

# ---------------------------------------------------------------------
# Text Preprocessing
# ---------------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).lower().strip())

def _split_camel(s: str) -> str:
    s = re.sub(r"([A-Za-z])(\d)", r"\1 \2", s)
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    s = re.sub(r"(\d)([A-Za-z])", r"\1 \2", s)
    return s

def normalize_hashtags_in_text(text: str) -> str:
    def _repl(m):
        tag = m.group(1).replace("_", " ").replace("-", " ")
        tag = _split_camel(tag)
        return tag
    return re.sub(r"#([A-Za-z0-9_\-]+)", _repl, text)

def _preprocess_for_ner(text: str) -> str:
    text = normalize_hashtags_in_text(text)
    return re.sub(r"\d{1,3}\.\d+°?\s*[NSEWnsew]", " ", text)

def extract_region_hints(text: str) -> List[str]:
    hints = [_norm(f"region {m.group(1)}") for m in REGION_NUM_RE.finditer(text)]
    hints += [_norm(m.group(1)) for m in PAREN_NAME_RE.finditer(text)]
    return list(dict.fromkeys(hints))  # dedupe

# ---------------------------------------------------------------------
# PSGC Helpers
# ---------------------------------------------------------------------
def _ensure_name_column(df: pd.DataFrame, candidates: List[str]) -> pd.DataFrame:
    for c in candidates:
        if c in df.columns:
            df["name"] = df[c]
            return df
    for col in df.columns:
        if col.lower().endswith("desc"):
            df["name"] = df[col]
            return df
    raise ValueError("Could not infer name column.")

def load_psgc_data(region_csv, province_csv, city_csv, brgy_csv, encoding=None):
    df_region = _ensure_name_column(pd.read_csv(region_csv, encoding=encoding), ["regDesc"])
    df_province = _ensure_name_column(pd.read_csv(province_csv, encoding=encoding), ["provDesc"])
    df_citymun = _ensure_name_column(pd.read_csv(city_csv, encoding=encoding), ["citymunDesc"])
    df_brgy = _ensure_name_column(pd.read_csv(brgy_csv, encoding=encoding), ["brgyDesc"])
    return df_region, df_province, df_citymun, df_brgy

def _get_code_col(df: pd.DataFrame, key: str) -> str:
    for col in df.columns:
        c = col.lower()
        if key in c and "code" in c:
            return col
    raise KeyError(f"Could not find code column for key {key}")

def _extract_paren_name(name: str) -> Optional[str]:
    m = re.search(r"\(([^)]+)\)", str(name) or "")
    return m.group(1) if m else None

def _core_norm(s: str) -> str:
    return _norm(re.sub(r"\s*\(.*?\)\s*", " ", str(s)))

def prepare_psgc(df_region, df_province, df_citymun, df_brgy, aliases_raw: Optional[Dict[str, str]] = None) -> Dict:
    df_region["name_norm"] = df_region["name"].map(_norm)
    for _df in (df_province, df_citymun, df_brgy):
        _df["name_norm"] = _df["name"].map(_norm)
        _df["name_core_norm"] = _df["name"].map(_core_norm)

    REG_CODE_COL = _get_code_col(df_region, "reg")
    PROV_CODE_COL = _get_code_col(df_province, "prov")
    CITYMUN_CODE_COL = _get_code_col(df_citymun, "citymun")
    BRGY_CODE_COL = _get_code_col(df_brgy, "brgy")
    BRGY_CITY_COL = _get_code_col(df_brgy, "citymun")

    aliases_raw = aliases_raw or ALIASES_RAW
    ALIASES = {_norm(k): _norm(v) for k, v in aliases_raw.items()}

    region_alias_map = {}
    for _, row in df_region.iterrows():
        official = row["name"]
        official_norm = _norm(official)
        paren_norm = _norm(_extract_paren_name(official) or "")
        region_alias_map[official_norm] = official_norm
        if paren_norm:
            region_alias_map[paren_norm] = official_norm

        code_digits = re.search(r"(\d+)", str(row.get(REG_CODE_COL, "")))
        if code_digits:
            n = int(code_digits.group(1)[:2])
            if 1 <= n <= 20:
                region_alias_map[_norm(f"region {n}")] = official_norm
                roman = ROMANS.get(n)
                if roman:
                    region_alias_map[_norm(f"region {roman}")] = official_norm

    for k, v in ALIASES.items():
        if v in region_alias_map.values():
            region_alias_map[k] = v

    return {
        "df_region": df_region,
        "df_province": df_province,
        "df_citymun": df_citymun,
        "df_brgy": df_brgy,
        "REG_CODE_COL": REG_CODE_COL,
        "PROV_CODE_COL": PROV_CODE_COL,
        "CITYMUN_CODE_COL": CITYMUN_CODE_COL,
        "BRGY_CODE_COL": BRGY_CODE_COL,
        "BRGY_CITY_COL": BRGY_CITY_COL,
        "region_alias_map": region_alias_map,
        "ALIASES": ALIASES,
    }

# ---------------------------------------------------------------------
# NER Initialization
# ---------------------------------------------------------------------
def load_xlmr_ner(device: int = -1):
    model_name = "Davlan/xlm-roberta-base-ner-hrl"
    print(f"🔧 Loading NER model: {model_name}")
    tok = XLMRobertaTokenizer.from_pretrained(model_name)
    mdl = XLMRobertaForTokenClassification.from_pretrained(model_name)
    print(f"✅ Model loaded successfully: {mdl.name_or_path}")
    return pipeline("ner", model=mdl, tokenizer=tok, device=device, aggregation_strategy="simple")

def extract_entities_xlmr(text: str, ner_pipeline) -> List[str]:
    pre = _preprocess_for_ner(str(text) if text else "")
    ents = ner_pipeline(pre)
    # print("🔍 NER entities:", ents)


    spans = [_norm(ent.get("word", "")) for ent in ents if ent.get("entity_group") in {"LOC", "GPE"}]
    spans.extend(extract_region_hints(pre))

    # --- Dynamic fix for truncated toponyms ---
    corrected = []
    for s in spans:
      
        pattern = rf"\b{s}\w+\b"
        m = re.search(re.escape(pattern), pre, flags=re.I)
        if m and m.group(0).lower() != s:
            corrected.append(_norm(m.group(0)))  
        else:
            corrected.append(s)


    # Deduplicate while preserving order
    seen, out = set(), []
    for s in corrected:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def normalize_direction_island(e: str) -> Optional[str]:
    parts = (e or "").split()
    if len(parts) == 2 and parts[0] in DIRECTIONS and parts[1] in ISLAND_GROUPS:
        return parts[1]
    return None

def strip_poi_terms(s: str) -> str:
    txt = _norm(s)
    txt = re.sub(r"[^a-z0-9\s\-]", " ", txt)
    for phrase in sorted([p for p in POI_TERMS if " " in p], key=len, reverse=True):
        txt = re.sub(rf"\b{re.escape(phrase)}\b", " ", txt)
    for word in [p for p in POI_TERMS if " " not in p]:
        txt = re.sub(rf"\b{re.escape(word)}\b", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()

# ---------------------------------------------------------------------
# Main PSGC Matcher
# ---------------------------------------------------------------------
def match_psgc(entity: str, psgc: Dict, context_city_code: Optional[str] = None) -> Dict:
    raw = str(entity)
    e = _norm(raw)

    df_region, df_province, df_citymun, df_brgy = (
        psgc["df_region"], psgc["df_province"], psgc["df_citymun"], psgc["df_brgy"]
    )
    REG_CODE_COL = psgc["REG_CODE_COL"]
    PROV_CODE_COL = psgc["PROV_CODE_COL"]
    CITYMUN_CODE_COL = psgc["CITYMUN_CODE_COL"]
    BRGY_CODE_COL = psgc["BRGY_CODE_COL"]
    region_alias_map = psgc["region_alias_map"]
    ALIASES = psgc["ALIASES"]

    COUNTRY_TERMS = {
        "ph", "ph.", "pilipinas", "philippine", "philippines",
        "philippine area of responsibility", "par",
    }
    if any(term in e for term in COUNTRY_TERMS):
        return {"entity": raw, "level": "country", "code": None, "matched_name": "Philippines"}

    norm_island = normalize_direction_island(e)
    if norm_island:
        return {"entity": raw, "level": "island_group", "code": None, "matched_name": norm_island.title()}

    if e in ISLAND_GROUPS:
        return {"entity": raw, "level": "island_group", "code": None, "matched_name": raw}

    if e in BLOCKLIST:
        return {"entity": raw, "level": None, "code": None, "matched_name": None}

    if e in region_alias_map:
        target_norm = region_alias_map[e]
        hit = df_region[df_region["name_norm"] == target_norm]
        if not hit.empty:
            r = hit.iloc[0]
            return {"entity": raw, "level": "region", "code": r[REG_CODE_COL], "matched_name": r["name"]}

    if e in ALIASES:
        alias_norm = ALIASES[e]
        for df_, col, lvl in [
            (df_region, REG_CODE_COL, "region"),
            (df_province, PROV_CODE_COL, "province"),
            (df_citymun, CITYMUN_CODE_COL, "citymun"),
            (df_brgy, BRGY_CODE_COL, "barangay"),
        ]:
            cols = ["name_norm"]
            if "name_core_norm" in df_.columns:
                cols.append("name_core_norm")
            hit = df_[df_[cols].apply(lambda r: alias_norm in r.values, axis=1)]
            if not hit.empty:
                r = hit.iloc[0]
                return {"entity": raw, "level": lvl, "code": r[col], "matched_name": r["name"]}

    # “City of X” or “X City” patterns
    m = re.match(r"^city of\s+(.+)$", e)
    if m:
        base = _norm(m.group(1))
        hit = df_citymun[
            (df_citymun["name_norm"].str.contains(base)) |
            (df_citymun["name_core_norm"].str.contains(base))
        ]
        if not hit.empty:
            r = hit.iloc[0]
            return {"entity": raw, "level": "citymun", "code": r[CITYMUN_CODE_COL], "matched_name": r["name"]}

    if e.endswith(" city"):
        base = e.replace(" city", "").strip()
        hit = df_citymun[
            (df_citymun["name_norm"].str.contains(base)) |
            (df_citymun["name_core_norm"].str.contains(base))
        ]
        if not hit.empty:
            r = hit.iloc[0]
            return {"entity": raw, "level": "citymun", "code": r[CITYMUN_CODE_COL], "matched_name": r["name"]}

    for df_, col, lvl in [
        (df_province, PROV_CODE_COL, "province"),
        (df_citymun, CITYMUN_CODE_COL, "citymun"),
        (df_brgy, BRGY_CODE_COL, "barangay"),
    ]:
        cols = [c for c in ["name_norm", "name_core_norm"] if c in df_.columns]
        hit = df_[df_[cols].apply(lambda r: e in r.values, axis=1)]
        if not hit.empty:
            r = hit.iloc[0]
            return {"entity": raw, "level": lvl, "code": r[col], "matched_name": r["name"]}

    e_clean = strip_poi_terms(e)
    if e_clean and e_clean != e:
        for df_, col, lvl in [
            (df_citymun, CITYMUN_CODE_COL, "citymun"),
            (df_brgy, BRGY_CODE_COL, "barangay"),
        ]:
            cols = [c for c in ["name_norm", "name_core_norm"] if c in df_.columns]
            hit = df_[df_[cols].apply(lambda r: e_clean in r.values, axis=1)]
            if not hit.empty:
                r = hit.iloc[0]
                return {"entity": raw, "level": lvl, "code": r[col], "matched_name": r["name"]}

    return {"entity": raw, "level": None, "code": None, "matched_name": None}

# ---------------------------------------------------------------------
# Batch Extraction
# ---------------------------------------------------------------------
def _clean_matches(matches: Optional[List[Dict]]) -> List[Dict]:
    seen, cleaned = set(), []
    for m in matches or []:
        if not m:
            continue
        if m.get("level") is None and m.get("code") is None:
            continue
        key = (m.get("level"), m.get("code"))
        if key not in seen:
            seen.add(key)
            cleaned.append(m)
    return cleaned

def extract_locations(df_data: pd.DataFrame, text_col: str, psgc: Dict, ner_pipeline,
                      drop_empty=True, show_progress=True,
                      location_raw="location_raw", location="location"):
    if text_col not in df_data.columns:
        raise KeyError(f"Column '{text_col}' not found in DataFrame.")

    iterator = tqdm(df_data.itertuples(index=False, name=None), total=len(df_data), desc="Extracting locations") if show_progress else df_data.itertuples(index=False, name=None)

    all_matches = []
    col_idx = list(df_data.columns).index(text_col)

    for row in iterator:
        text = str(row[col_idx]) if row[col_idx] else ""
        ents = extract_entities_xlmr(text, ner_pipeline)

        # 🌋 --- Volcano location override fix (robust) ---
        corrected_ents = []
        volcano_fixes = 0  # ✅ initialize counter inside each loop

        for ent in ents:
            key = ent.lower().strip()

            # --- 1️⃣ Normalize punctuation and spacing ---
            key = re.sub(r"[.,\-_/]+", " ", key)  # e.g. "mt.taal" → "mt taal"
            key = re.sub(r"\s+", " ", key).strip()

            # --- 2️⃣ Handle concatenated forms like "mayonvolcano" or "bulkangkanlaon" ---
            if "volcano" not in key and re.search(r"(mayon|taal|bulusan|kanlaon|pinatubo|hibok)", key):
                key = re.sub(r"(mayon|taal|bulusan|kanlaon|pinatubo|hibok)(volcano)?", r"\1 volcano", key)

            # --- 3️⃣ Try to match any volcano override substring ---
            matched = None
            for v_key, info in VOLCANO_OVERRIDES.items():
                pattern = r"\b" + re.escape(v_key) + r"\b"
                if re.search(pattern, key):
                    matched = info
                    break

            if matched:
                corrected_ents.append(matched["province"])
                volcano_fixes += 1
            else:
                corrected_ents.append(ent)

        if volcano_fixes > 0:
            print(f"🌋 Applied {volcano_fixes} volcano override(s) for text: {text[:80]}...")

        # Continue normal PSGC matching
        rough = [match_psgc(ent, psgc) for ent in corrected_ents]
        context_city_code = next((m["code"] for m in rough if m.get("level") == "citymun" and m.get("code")), None)
        matches = [match_psgc(ent, psgc, context_city_code) for ent in corrected_ents]

        all_matches.append(_clean_matches(matches))

    out = df_data.copy()
    out[location_raw] = all_matches
    out[location] = out[location_raw].apply(lambda x: "; ".join(f"{m.get('matched_name')} ({m.get('level')})" for m in x if m.get("matched_name")) if x else "")
    if drop_empty:
        out = out[out[location_raw].apply(lambda x: len(x) > 0)].reset_index(drop=True)

    return out

# ---------------------------------------------------------------------
# Wrapper for pipeline use
# ---------------------------------------------------------------------
def extract_location(df_data: pd.DataFrame, text_col: str = "text") -> pd.DataFrame:
    global _NER_PIPELINE, _PSGC_CACHE
    try:
        _NER_PIPELINE
    except NameError:
        _NER_PIPELINE = None
    try:
        _PSGC_CACHE
    except NameError:
        _PSGC_CACHE = None

    if _PSGC_CACHE is None:
        print("📥 Loading PSGC reference tables...")
        df_region, df_province, df_citymun, df_brgy = load_psgc_data(
            "data/lookup/refregion.csv",
            "data/lookup/refprovince.csv",
            "data/lookup/refcitymun.csv",
            "data/lookup/refbrgy.csv",
        )
        _PSGC_CACHE = prepare_psgc(df_region, df_province, df_citymun, df_brgy)

    if _NER_PIPELINE is None:
        _NER_PIPELINE = load_xlmr_ner(device=-1)

    return extract_locations(df_data, text_col, _PSGC_CACHE, _NER_PIPELINE)

if __name__ == "__main__":
    print("✅ extract_location.py ready — import extract_location(df) in your pipeline.")
