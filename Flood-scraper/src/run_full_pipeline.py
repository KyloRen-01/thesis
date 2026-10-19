"""Compatibility entry point for the complete Flood-scraper pipeline."""

import sys

from run_flood_pipeline import main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["--headed", "--include-history", "--min-length", "0"])
    raise SystemExit(main())
