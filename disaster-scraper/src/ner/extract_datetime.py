"""
📅 Datetime Extraction using XLM-RoBERTa NER
--------------------------------------------
Extracts DATE and TIME entities from text using 'programmersilvanus/ner-xlmr',
normalizes them into ISO 8601, and prioritizes:
    1️⃣ Model-detected DAT/TIM in text_content
    2️⃣ post_timestamp
    3️⃣ scraped_timestamp
    4️⃣ Fallback: current time

Usage:
    df = extract_datetime(df)
"""

import re
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from transformers import pipeline
from dateutil import parser


# ======================================================
# 🔧 Helpers
# ======================================================
def _preprocess_for_ner(text: str) -> str:
    """Light cleanup before feeding to NER."""
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_tagalog_time(text: str) -> str:
    """Convert Tagalog or mixed Tagalog-English time expressions into English-friendly form."""
    text = str(text).lower().strip()

    replacements = {
        r"alas[- ]?(\d{1,2})(:?(\d{2}))?\s*ng\s*umaga": r"\1:\3 am",
        r"alas[- ]?(\d{1,2})(:?(\d{2}))?\s*ng\s*hapon": r"\1:\3 pm",
        r"alas[- ]?(\d{1,2})(:?(\d{2}))?\s*ng\s*gabi": r"\1:\3 pm",
        r"alas[- ]?(\d{1,2})(:?(\d{2}))?\s*ng\s*tanghali": r"\1:\3 pm",
        r"alas[- ]?12\s*ng\s*umaga": "12:00 pm",
    }
    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text)

    # Translate Tagalog months to English
    month_map = {
        "enero": "january", "pebrero": "february", "marso": "march", "abril": "april",
        "mayo": "may", "hunyo": "june", "hulyo": "july", "agosto": "august",
        "setyembre": "september", "oktubre": "october", "nobyembre": "november", "disyembre": "december"
    }
    for tl, en in month_map.items():
        text = re.sub(rf"\b{tl}\b", en, text)

    return text


def _clean_datetime_fragment(t: str) -> str:
    """Clean and normalize noisy date/time fragments from NER."""
    t = re.sub(r"[\(\)\[\],.;]", " ", t)  # remove brackets/punctuation
    t = re.sub(r"([0-9]{1,2})([A-Za-z]{3})", r"\1 \2", t)  # 24jul25 → 24 jul 25
    t = re.sub(r"([A-Za-z]{3,9})([0-9]{1,2})", r"\1 \2", t)  # july22 → july 22
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _normalize_date(text: str):
    """Try to parse extracted date string into ISO format."""
    try:
        if not text:
            return None
        norm_text = _normalize_tagalog_time(text)
        norm_text = _clean_datetime_fragment(norm_text)
        norm_text = re.sub(r"(\d)\s*([ap])\.?m\.?", r"\1 \2m", norm_text)
        dt = parser.parse(norm_text, fuzzy=True)
        return dt.isoformat()
    except Exception:
        return None


def _is_valid_str(val):
    """Check if a string is non-empty and not a placeholder like 'Unknown'."""
    if not val or pd.isna(val):
        return False
    val = str(val).strip().lower()
    return val not in {"none", "nan", "unknown", "null", ""}


# ======================================================
# 🧩 Core Extraction Logic
# ======================================================
def extract_datetime(df_data: pd.DataFrame) -> pd.DataFrame:
    """
    Extract 'DAT' and 'TIM' entities using XLM-RoBERTa NER,
    then normalize them to ISO 8601 with priority:
    1️⃣ text_content
    2️⃣ post_timestamp
    3️⃣ scraped_timestamp
    4️⃣ fallback_now
    """
    global _NER_PIPELINE
    try:
        _NER_PIPELINE
    except NameError:
        _NER_PIPELINE = None

    # Load NER model once
    if _NER_PIPELINE is None:
        print("🔹 Loading XLM-RoBERTa NER model for DATE/TIME extraction...")
        _NER_PIPELINE = pipeline(
            "token-classification",
            model="programmersilvanus/ner-xlmr",
            aggregation_strategy="simple"
        )
        print("🧠 Model loaded:", _NER_PIPELINE.model.name_or_path)
    else:
        print("🧠 Using cached XLM-RoBERTa DATE/TIME model.")

    TEXT_COL = "text_content" if "text_content" in df_data.columns else "text"

    raw_mentions, normalized_dates, primary_iso, priority_used = [], [], [], []
    fallback_count = 0
    detected_count = 0
    total_rows = len(df_data)

    for _, row in tqdm(df_data.iterrows(), total=total_rows, desc="📅 Phase 2: datetime (model)"):
        text = _preprocess_for_ner(row.get(TEXT_COL, ""))
        ents = _NER_PIPELINE(text)

        temporal_ents = [ent.get("word", "").strip() for ent in ents if ent.get("entity_group") in {"DAT", "TIM"}]

        # Clean fragments & remove duplicates
        valid_parts = []
        for t in temporal_ents:
            cleaned = _clean_datetime_fragment(t)
            if re.search(r"\d", cleaned) or re.search(r"(am|pm|aug|jul|jun|sep|oct|nov|dec|july|august|friday|saturday|sunday|monday|tuesday|wednesday|thursday)", cleaned, re.I):
                if cleaned and cleaned not in valid_parts:
                    valid_parts.append(cleaned)

        parsed_dt = None
        parsed_candidates = []

        if valid_parts:
            # Remove repeated weekday-only mentions
            valid_parts = [v for v in valid_parts if not re.fullmatch(r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", v, re.I)]

            # Separate date vs. time tokens
            date_tokens = [t for t in valid_parts if re.search(
                r"\d{4}|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|enero|pebrero|marso|abril|mayo|hunyo|hulyo|agosto|setyembre|oktubre|nobyembre|disyembre)\b",
                t, re.I)]
            time_tokens = [t for t in valid_parts if re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", t, re.I)]

            # Merge split fragments like '11:21am,24' + 'jul25)'
            merged_candidates = []
            if len(valid_parts) >= 2:
                for i in range(len(valid_parts) - 1):
                    merged = f"{valid_parts[i]} {valid_parts[i+1]}"
                    if re.search(r"\d{1,2}(:\d{2})?\s*(am|pm)", merged, re.I) and re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})", merged, re.I):
                        merged_candidates.append(merged)
            valid_parts.extend(merged_candidates)

            # Try pairing each date with a time (or none)
            if date_tokens:
                for d in date_tokens:
                    for t in time_tokens if time_tokens else [""]:
                        try:
                            candidate_str = f"{d} {t}".strip()
                            parsed_iso = _normalize_date(candidate_str)
                            if parsed_iso:
                                parsed_candidates.append(parsed_iso)
                        except Exception:
                            continue

            # Also attempt parsing merged fragments directly
            for candidate in valid_parts:
                parsed_iso = _normalize_date(candidate)
                if parsed_iso and parsed_iso not in parsed_candidates:
                    parsed_candidates.append(parsed_iso)

            # Select best (keep first valid in text order, not earliest date)
            if parsed_candidates:
                try:
                    # Keep the first valid parsed ISO string (maintaining detection order)
                    first_valid = next((p for p in parsed_candidates if p), None)
                    if first_valid:
                        parsed_dt = datetime.fromisoformat(first_valid)
                except Exception:
                    parsed_dt = None

        if temporal_ents:
            detected_count += 1

        # Priority selection
        primary, used = None, None

        if parsed_dt:
            primary = parsed_dt.isoformat()
            used = "model_extracted_datetime"
        elif _is_valid_str(row.get("post_timestamp")):
            try:
                primary = parser.parse(str(row["post_timestamp"]), fuzzy=True).isoformat()
                used = "post_timestamp"
            except Exception:
                pass
        elif _is_valid_str(row.get("scraped_timestamp")):
            try:
                primary = parser.parse(str(row["scraped_timestamp"]), fuzzy=True).isoformat()
                used = "scraped_timestamp"
            except Exception:
                pass
        else:
            primary = datetime.now().isoformat()
            used = "fallback_now"
            fallback_count += 1

        raw_mentions.append(temporal_ents)
        normalized_dates.append(parsed_candidates)
        primary_iso.append(primary)
        priority_used.append(used)

    df_data["time_mentions_raw"] = raw_mentions
    df_data["time_parsed"] = normalized_dates
    df_data["event_time_primary_iso"] = primary_iso
    df_data["event_time_source"] = priority_used

    def _format_event_time(iso_str):
        if not iso_str:
            return None
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%B %d, %Y %H:%M:%S")
        except Exception:
            return iso_str

    df_data["event_time_primary"] = df_data["event_time_primary_iso"].apply(_format_event_time)

    success = total_rows - fallback_count
    print(f"📅 Datetime extraction complete: {success}/{total_rows} posts parsed "
          f"({fallback_count} fallback defaults, {detected_count} with DAT/TIM entities).")

    return df_data
