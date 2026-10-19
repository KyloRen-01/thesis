#!/usr/bin/env python3
"""Initialize persistent manual-login sessions for Facebook and X."""

from __future__ import annotations

import argparse
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FACEBOOK_PROFILE = BASE_DIR / ".facebook_dummy_chrome_profile"
DEFAULT_X_PROFILE = BASE_DIR / ".x_dummy_chrome_profile"


def create_driver(profile_dir: Path, chromedriver_path: str | None) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    profile_dir.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir.resolve()}")
    service = Service(chromedriver_path) if chromedriver_path else Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(45)
    return driver


def initialize_session(
    label: str,
    login_url: str,
    profile_dir: Path,
    chromedriver_path: str | None,
) -> None:
    print(f"\nOpening {label} login in:")
    print(f"  {profile_dir.resolve()}")
    print(f"Log in manually to the dummy {label} account in the browser window.")

    driver = create_driver(profile_dir, chromedriver_path)
    try:
        driver.get(login_url)
        input(f"After {label} is fully logged in, press Enter here to save the session: ")
        print(f"{label} session profile saved.")
    finally:
        driver.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manually log in to Facebook and X and save their browser sessions."
    )
    parser.add_argument(
        "--facebook-profile-dir",
        type=Path,
        default=DEFAULT_FACEBOOK_PROFILE,
    )
    parser.add_argument(
        "--x-profile-dir",
        type=Path,
        default=DEFAULT_X_PROFILE,
    )
    parser.add_argument("--chromedriver", help="Optional path to chromedriver.exe.")
    parser.add_argument(
        "--skip-facebook",
        action="store_true",
        help="Do not open Facebook; initialize only the X session.",
    )
    parser.add_argument(
        "--skip-x",
        action="store_true",
        help="Do not open X; initialize only the Facebook session.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.skip_facebook and args.skip_x:
        raise SystemExit("Choose at least one session to initialize.")

    if not args.skip_facebook:
        initialize_session(
            "Facebook",
            "https://www.facebook.com/login/",
            args.facebook_profile_dir,
            args.chromedriver,
        )
    if not args.skip_x:
        initialize_session(
            "X",
            "https://x.com/i/flow/login",
            args.x_profile_dir,
            args.chromedriver,
        )
    print("\nBoth social-media sessions were initialized successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
