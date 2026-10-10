"""
🌋 Disaster Type Classification
--------------------------------------------
Classifies each post into one of several disaster categories
using a hybrid approach:
  • Zero-shot classification with XLM-RoBERTa (XNLI)
  • Keyword-based heuristic boosting

Usage:
    df = classify_disaster(df)
"""

import re
import json
import time
import torch
import pandas as pd
from tqdm import tqdm
from transformers import pipeline

# ======================================================
# ⚙️  Setup
# ======================================================
DISASTER_LABELS = [
    "other (not a natural disaster or emergency, unrelated to calamities)",
    "rainfall / flood (rainfall, heavy rain, monsoon, thunderstorm, baha, flood, lunop, overflow, storm surge)",
    "landslide (pagguho ng lupa, soil collapse, mudslide)",
    "earthquake (lindol, shaking, seismic activity)",
    "tsunami (sea wave after earthquake)",
    "fire (sunog, blaze, wildfire, burning)",
    "volcanic eruption (eruption, bulkan, ashfall, lava flow)",
    "typhoon (bagyo, tropical storm, cyclone, landfall)"
]

KEYWORDS = {
    "rainfall / flood": [
        "rain", "rains", "rainfall", "rainshower", "rain showers", "heavy rain",
        "downpour", "monsoon", "habagat", "amihan", "lpa", "itcz",
        "weather system", "weather update", "weather advisory", "weather alert",
        "rainfall warning","orange rainfall","yellow rainfall","red rainfall",
        "orange warning","yellow warning","red warning",
        "rainfall alert","rainfall advisory","rainfall watch",
        "thunderstorm","thunderstorms","thunderstorm watch","thunderstorm advisory",
        "thunderstorm warning","thunderstorm information",
        "kulog","kidlat","lightning","storm surge","coastal surge","daluyong",
        "gusty","baha","lunop","pagbaha","paglunop","flood","flooding",
        "overflow","pag-apaw","apaw","pagapaw","inundation"
    ],
    "landslide": ["landslide","pagguho","mudslide","nahulog","slope","erosion"],
    "earthquake": ["lindol","linog","pagyanig","nangurog","magnitude","aftershock","epicenter"],
    "tsunami": ["tsunami","daluyong","tidal wave","sea surge"],
    "fire": ["sunog","nasunog","apoy","fire","blaze","wildfire","sumiklab"],
    "volcanic eruption": [
        "volcano","volcanic","eruption","ashfall","ash cloud","ash plume",
        "lava","lahar","crater","pyroclastic","phreatic","phreatomagmatic",
        "sulfur dioxide","so2","mayon","taal","pinatubo","kanlaon","bulusan",
        "hibok-hibok","hibok hibok","banahaw","banahao","ragang","didicas",
        "babuyan claro","smith volcano","camiguin","apo","matutum","bulkan","bulkang"
    ],
    "typhoon": ["typhoon","bagyo", "bagyong", "unos","tropical","cyclone","storm","landfall"]
}

PRIORITY = [
    "tsunami","volcanic eruption","earthquake","landslide",
    "typhoon","rainfall / flood","fire","other"
]

# ======================================================
# 🧠 Helpers
# ======================================================
def find_keywords(text):
    """Detect disaster-related keywords (handles plural/s/ing/ed)."""
    lower = text.lower()
    found = {}
    for label, kws in KEYWORDS.items():
        hits = []
        for kw in kws:
            pattern = rf"\b{re.escape(kw)}(s|es|ing|ed)?\b"
            if re.search(pattern, lower):
                hits.append(kw)
        if hits:
            found[label] = hits
    return found


def pick_label(text, res, threshold=0.25, confidence_gap=0.08):
    """
    Combines zero-shot model results and keyword logic with adaptive weighting.
    """
    text = str(text or "").strip().lower()
    found_kw = find_keywords(text)
    base = lambda l: l.split(" (")[0].lower()
    base_scores = {base(k): v for k, v in zip(res["labels"], res["scores"])}

    # Keyword-enhanced weighting
    if found_kw:
        weighted = []
        for lbl, kws in found_kw.items():
            kw_bonus = 0.02 * len(kws)  # small bonus per keyword hit
            score = base_scores.get(lbl, 0) + kw_bonus
            weighted.append((lbl, score, len(kws)))

        weighted.sort(key=lambda x: (-x[1], -x[2], PRIORITY.index(x[0])))
        best_label = weighted[0][0]
        return best_label, base_scores, found_kw

    # Model-only logic
    sorted_labels = sorted(base_scores.items(), key=lambda x: x[1], reverse=True)
    top_label, top_score = sorted_labels[0]
    second_score = sorted_labels[1][1] if len(sorted_labels) > 1 else 0.0

    if (top_score - second_score) < confidence_gap or top_score < 0.8:
        return "other", base_scores, found_kw

    active = [l for l, s in base_scores.items() if s >= threshold]
    if not active:
        return "other", base_scores, found_kw

    top = sorted(active, key=lambda l: (-base_scores[l], PRIORITY.index(l)))
    return top[0], base_scores, found_kw


# ======================================================
# 🚀 Main classification function
# ======================================================
def classify_disaster(df_data: pd.DataFrame) -> pd.DataFrame:
    """Classify disaster type per post using zero-shot + keyword logic."""
    global _ZSC_PIPELINE
    try:
        _ZSC_PIPELINE
    except NameError:
        _ZSC_PIPELINE = None

    # 1️⃣ Load model only once
    if _ZSC_PIPELINE is None:
        print("🔹 Loading XLM-RoBERTa model for zero-shot disaster classification...")
        _ZSC_PIPELINE = pipeline(
            "zero-shot-classification",
            model="joeddav/xlm-roberta-large-xnli",
            device=0 if torch.cuda.is_available() else -1
        )
        print("🧠 Model loaded:", _ZSC_PIPELINE.model.name_or_path)
    else:
        print("🧠 Using cached disaster classification model.")

    # 2️⃣ Detect correct text column
    if "text_content" in df_data.columns:
        TEXT_COL = "text_content"
    elif "text" in df_data.columns:
        TEXT_COL = "text"
    else:
        raise KeyError("❌ Neither 'text_content' nor 'text' column found in DataFrame.")

    print(f"🗂️ Using '{TEXT_COL}' as text column for classification.")

    texts = df_data[TEXT_COL].astype(str).tolist()
    BATCH_SIZE = 16
    results = []

    print("⚙️ Running zero-shot + keyword classification (GPU batches)...")
    start_time = time.time()

    # 3️⃣ Batch inference
    for i in tqdm(range(0, len(texts), BATCH_SIZE)):
        batch = texts[i:i + BATCH_SIZE]
        batch_results = _ZSC_PIPELINE(
            batch,
            candidate_labels=DISASTER_LABELS,
            multi_label=True,
            truncation=True
        )
        results.extend(batch_results)

    print(f"\n✅ Model inference complete in {(time.time() - start_time)/60:.2f} min\n")

    # 4️⃣ Post-process predictions
    disaster_type, disaster_scores, disaster_keywords = [], [], []
    for text, res in tqdm(zip(texts, results), total=len(texts), desc="Post-processing predictions"):
        try:
            label, scores, found = pick_label(text, res)
            disaster_type.append(label)
            disaster_scores.append(json.dumps(scores, ensure_ascii=False))
            disaster_keywords.append(", ".join([f"{k}:{'|'.join(v)}" for k, v in found.items()]))
        except Exception as e:
            disaster_type.append("other")
            disaster_scores.append("{}")
            disaster_keywords.append("")
            print(f"⚠️ Error processing text: {e}")

    # 5️⃣ Append to DataFrame
    df_data["disaster_type"] = disaster_type
    # df_data["disaster_scores"] = disaster_scores
    # df_data["disaster_detected_keywords"] = disaster_keywords

    print("\n📊 Disaster Type Counts:")
    print(df_data["disaster_type"].value_counts())

    print(f"\n✅ Disaster classification complete in {(time.time() - start_time)/60:.2f} min")
    
    # 6️⃣ Drop rows where disaster_type == "other"
    df_data = df_data[df_data["disaster_type"] != "other"].copy()

    return df_data


if __name__ == "__main__":
    print("✅ disaster_classifier.py ready — import classify_disaster(df) in your pipeline.")
