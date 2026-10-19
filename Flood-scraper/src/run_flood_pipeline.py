#!/usr/bin/env python3
"""Run the Flood-scraper collection and cleaning stages in sequence."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FACEBOOK_PROFILE = BASE_DIR / ".facebook_dummy_chrome_profile"
DEFAULT_X_PROFILE = BASE_DIR / ".x_dummy_chrome_profile"


def non_empty_csvs(folder: Path) -> list[Path]:
    """Return all non-empty CSV files in a raw-data folder."""

    return sorted(
        (path for path in folder.glob("*.csv") if path.stat().st_size > 0),
        key=lambda path: path.stat().st_mtime,
    )


def run_step(label: str, script: str, arguments: list[str]) -> None:
    command = [sys.executable, str(BASE_DIR / script), *arguments]
    print(f"\n=== {label} ===")
    print(" ".join(command))
    completed = subprocess.run(command, cwd=BASE_DIR)
    if completed.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Facebook and X, then clean both sources into one CSV."
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Log in to both platforms before scraping; use this on the first run.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show Chrome during normal scraping runs.",
    )
    parser.add_argument(
        "--hours-page",
        type=int,
        help="Facebook page-feed cutoff in hours.",
    )
    parser.add_argument(
        "--hours-user",
        type=int,
        help="X user-timeline cutoff in hours.",
    )
    parser.add_argument(
        "--hours-search",
        type=int,
        help="Search-feed cutoff in hours for both platforms.",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=90,
        help="Minimum cleaned text length; use 0 to keep short posts.",
    )
    parser.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Keep exact and near-duplicate cleaned posts.",
    )
    parser.add_argument(
        "--include-history",
        action="store_true",
        help="Include all existing raw Facebook and X CSVs in the cleaned output.",
    )
    parser.add_argument(
        "--facebook-profile-dir",
        type=Path,
        default=DEFAULT_FACEBOOK_PROFILE,
        help="Chrome profile for the Facebook dummy account.",
    )
    parser.add_argument(
        "--x-profile-dir",
        type=Path,
        default=DEFAULT_X_PROFILE,
        help="Chrome profile for the X dummy account.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    facebook_args: list[str] = []
    twitter_args: list[str] = []

    facebook_args.extend(["--profile-dir", str(args.facebook_profile_dir)])
    twitter_args.extend(["--profile-dir", str(args.x_profile_dir)])

    if args.login:
        facebook_args.append("--login")
        twitter_args.append("--login")
    elif args.headed:
        facebook_args.append("--headed")
        twitter_args.append("--headed")

    if args.hours_page is not None:
        facebook_args.extend(["--hours-page", str(args.hours_page)])
    if args.hours_user is not None:
        twitter_args.extend(["--hours-user", str(args.hours_user)])
    if args.hours_search is not None:
        facebook_args.extend(["--hours-search", str(args.hours_search)])
        twitter_args.extend(["--hours-search", str(args.hours_search)])

    run_step("Facebook scrape", "src/scraper/fb_flood_scraper.py", facebook_args)
    run_step("X scrape", "src/scraper/twitter_flood_scraper.py", twitter_args)

    cleaning_args = ["--min-length", str(args.min_length)]
    if args.keep_duplicates:
        cleaning_args.append("--keep-duplicates")
    if args.include_history:
        raw_paths = non_empty_csvs(BASE_DIR / "data" / "raw" / "facebook")
        raw_paths += non_empty_csvs(BASE_DIR / "data" / "raw" / "twitter")
        if not raw_paths:
            raise SystemExit("No non-empty raw CSV files were found for history merge.")

        cleaning_args.extend(
            ["--input", *(str(path.relative_to(BASE_DIR)) for path in raw_paths)]
        )
        cleaning_args.extend(
            ["--output", str(Path("data") / "merged" / "merged_flood_data.csv")]
        )
    run_step("Combined cleaning", "src/filter/data_cleaning.py", cleaning_args)

    print("\nPipeline completed: Facebook scrape -> X scrape -> combined cleaned CSV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
