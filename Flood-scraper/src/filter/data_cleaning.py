#!/usr/bin/env python3
"""Clean Facebook and X flood-scraper CSV files.

This follows the senior disaster scraper's cleaning approach while preserving
the flood scraper's media fields. The raw ``text`` is kept, and the cleaned
version is written to ``text_content``.
"""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import html
import logging
import re
import unicodedata as ud
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

try:
    from rapidfuzz import fuzz
except ImportError:  # Keep the cleaner usable before optional dependencies install.
    class _FallbackFuzz:
        @staticmethod
        def ratio(left: str, right: str) -> float:
            return SequenceMatcher(None, left, right).ratio() * 100

    fuzz = _FallbackFuzz()


BASE_DIR = Path(__file__).resolve().parents[2]
PH_TIME = timezone(timedelta(hours=8))
URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", flags=re.IGNORECASE)
HTML_PATTERN = re.compile(r"<[^>]+>")
BOILERPLATE_PATTERN = re.compile(
    r"\b(?:shared a post|see more|see less|commented|replied)\b",
    flags=re.IGNORECASE,
)
RT_PATTERN = re.compile(r"^\s*RT\s+@\w+\s*:\s*", flags=re.IGNORECASE)


def remove_emojis_and_control_chars(text: str) -> str:
    """Remove emoji/symbol characters without deleting ordinary text."""

    cleaned: list[str] = []
    for char in text:
        category = ud.category(char)
        codepoint = ord(char)
        is_emoji_range = (
            0x1F000 <= codepoint <= 0x1FAFF
            or 0x2600 <= codepoint <= 0x27BF
            or 0xFE00 <= codepoint <= 0xFE0F
        )
        if is_emoji_range or category == "So":
            continue
        if category.startswith("C") and char not in {"\n", "\r", "\t"}:
            continue
        cleaned.append(char)
    return "".join(cleaned)


def clean_text(text: object, *, min_length: int = 90) -> str:
    """Normalize one post using the senior cleaner's rules."""

    value = "" if text is None else str(text)
    if value.strip().lower() in {"", "nan", "none", "null"}:
        return ""

    value = ud.normalize("NFKC", value)
    value = URL_PATTERN.sub(" ", value)
    value = HTML_PATTERN.sub(" ", html.unescape(value))
    value = remove_emojis_and_control_chars(value)
    value = RT_PATTERN.sub("", value)
    value = BOILERPLATE_PATTERN.sub(" ", value)
    value = re.sub(r"[-=*_]{3,}", " ", value)
    value = re.sub(r"(?:\.\s*){3,}", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()

    if not re.search(r"[\w\d]", value, flags=re.UNICODE):
        return ""
    if re.fullmatch(r"[0-9\s:/.-]{6,}", value):
        return ""
    if min_length > 0 and len(value) < min_length:
        return ""
    return value


def _has_image(row: pd.Series) -> bool:
    """Prefer a duplicate row that retains a downloaded image."""

    for column in ("image_path", "image_url"):
        if column in row and pd.notna(row[column]) and str(row[column]).strip():
            return True
    return False


def drop_near_duplicates(
    dataframe: pd.DataFrame,
    *,
    text_column: str = "text_content",
    prefix_length: int = 300,
    prefix_threshold: float = 97,
    full_threshold: float = 90,
) -> pd.DataFrame:
    """Remove senior-style tail/comment duplicates while preserving media."""

    kept_indices: list[int] = []
    seen: list[tuple[str, str, int, bool]] = []

    for index, raw_text in enumerate(dataframe[text_column].fillna("").astype(str)):
        normalized = " ".join(raw_text.split()).strip().lower()
        prefix = normalized[:prefix_length]
        current_has_image = _has_image(dataframe.iloc[index])
        duplicate = None

        for candidate in seen:
            seen_prefix, seen_text, seen_index, seen_has_image = candidate
            if fuzz.ratio(prefix, seen_prefix) >= prefix_threshold and fuzz.ratio(
                normalized, seen_text
            ) >= full_threshold:
                duplicate = candidate
                break

        if duplicate is None:
            seen.append((prefix, normalized, index, current_has_image))
            kept_indices.append(index)
            continue

        _, previous_text, previous_index, previous_has_image = duplicate
        replace_previous = (
            current_has_image and not previous_has_image
        ) or (
            current_has_image == previous_has_image
            and len(normalized) < len(previous_text)
        )
        if replace_previous:
            seen.remove(duplicate)
            seen.append((prefix, normalized, index, current_has_image))
            kept_indices.remove(previous_index)
            kept_indices.append(index)

    return dataframe.iloc[kept_indices].reset_index(drop=True)


def clean_dataframe(
    input_data: pd.DataFrame | str | Path,
    *,
    min_length: int = 90,
    remove_duplicates: bool = True,
) -> pd.DataFrame:
    """Clean one CSV/DataFrame while preserving scrape and image metadata."""

    if isinstance(input_data, (str, Path)):
        dataframe = pd.read_csv(input_data, encoding="utf-8-sig")
    else:
        dataframe = input_data.copy()

    if "text" in dataframe.columns:
        source_text = dataframe["text"]
    elif "text_content" in dataframe.columns:
        source_text = dataframe["text_content"]
    else:
        raise KeyError("Input data must contain a 'text' or 'text_content' column.")

    dataframe["text_content"] = source_text.fillna("").apply(
        lambda value: clean_text(value, min_length=min_length)
    )
    dataframe = dataframe[dataframe["text_content"].str.strip().astype(bool)].copy()

    if remove_duplicates and not dataframe.empty:
        dataframe = dataframe.drop_duplicates(subset=["text_content"], keep="first")
        dataframe = drop_near_duplicates(dataframe)

    return dataframe.reset_index(drop=True)


def _latest_csv(folder: Path, pattern: str) -> Path:
    files = [path for path in folder.glob(pattern) if path.stat().st_size > 0]
    if not files:
        raise FileNotFoundError(f"No non-empty CSV matching {pattern} in {folder}")
    return max(files, key=lambda path: path.stat().st_mtime)


def default_inputs() -> list[Path]:
    """Find the newest Facebook and X raw CSVs when inputs are omitted."""

    return [
        _latest_csv(BASE_DIR / "data" / "raw" / "facebook", "fb_raw_floodData_*.csv"),
        _latest_csv(BASE_DIR / "data" / "raw" / "twitter", "twitter_raw_floodData_*.csv"),
    ]


def choose_output_path(requested_path: Path | None) -> Path:
    timestamp = datetime.now(PH_TIME).strftime("%m-%d-%Y_%H%M%S")
    default_path = BASE_DIR / "data" / "processed" / f"cleaned_flood_posts_{timestamp}.csv"

    if requested_path is None:
        return default_path
    if requested_path.exists():
        suffix = requested_path.suffix or ".csv"
        return requested_path.with_name(f"{requested_path.stem}_{timestamp}{suffix}")
    return requested_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean Facebook and X flood CSV files.")
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        help="One or more raw CSV files. Omit to use the newest Facebook and X CSVs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV path. Omit to create data/processed/cleaned_flood_posts_<timestamp>.csv.",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=90,
        help="Minimum cleaned text length; use 0 to keep short non-empty posts.",
    )
    parser.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Do not remove exact or near-duplicate cleaned text.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    input_paths = args.input or default_inputs()
    output_path = choose_output_path(args.output)

    frames = [pd.read_csv(path, encoding="utf-8-sig") for path in input_paths]
    raw_data = pd.concat(frames, ignore_index=True)
    cleaned_data = clean_dataframe(
        raw_data,
        min_length=args.min_length,
        remove_duplicates=not args.keep_duplicates,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_data.to_csv(output_path, index=False, encoding="utf-8-sig")
    logging.info(
        "Cleaned %s raw rows to %s rows -> %s",
        len(raw_data),
        len(cleaned_data),
        output_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
