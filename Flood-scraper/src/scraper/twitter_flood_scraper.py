#!/usr/bin/env python3
"""Collect flood-related X posts and save them as a new timestamped CSV."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlsplit

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from dotenv import load_dotenv
except ImportError:  # Optional at runtime; environment variables still work.
    load_dotenv = None

try:
    from .twitter_scraping_config import KEYWORDS, PH_LOCATIONS, TWITTER
except ImportError:
    from twitter_scraping_config import KEYWORDS, PH_LOCATIONS, TWITTER

try:
    from .media_utils import download_images, extract_image_urls
except ImportError:
    from media_utils import download_images, extract_image_urls


BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw" / "twitter"
IMAGE_DIR = RAW_DIR / "images"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PH_TIME = timezone(timedelta(hours=8))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DEFAULT_PROFILE_DIR = BASE_DIR / ".x_chrome_profile"
CSV_COLUMNS = [
    "source",
    "query_page",
    "text",
    "post_timestamp",
    "scraped_timestamp",
    "user",
    "post_url",
    "image_url",
    "image_path",
]

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def init_driver(
    *,
    headless: bool = True,
    chromedriver_path: str | None = None,
    profile_dir: Path | str | None = DEFAULT_PROFILE_DIR,
) -> webdriver.Chrome:
    """Create a Chrome session with cookies persisted between runs."""

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    if profile_dir:
        profile_path = Path(profile_dir).expanduser().resolve()
        profile_path.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_path}")

    driver_path = chromedriver_path or os.getenv("CHROMEDRIVER_PATH")
    service = Service(driver_path) if driver_path else Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(45)
    return driver


def get_x_credentials() -> tuple[str, str, str]:
    """Read X credentials from the environment, prompting only when needed."""

    username = os.getenv("X_USERNAME", "").strip().lstrip("@")
    email = os.getenv("X_EMAIL", "").strip()
    password = os.getenv("X_PASSWORD", "")
    if not username:
        username = input("X username (without @): ").strip().lstrip("@")
    if not email:
        email = input("X email: ").strip()
    if not password:
        password = getpass.getpass("X password (input is hidden): ")
    if not username or not email or not password:
        raise RuntimeError("X login requires X_USERNAME, X_EMAIL, and X_PASSWORD.")
    return username, email, password


def _click_text_button(driver: webdriver.Chrome, text: str) -> bool:
    buttons = driver.find_elements(
        By.XPATH,
        f"//button[.//span[normalize-space()='{text}']] | "
        f"//div[@role='button'][.//span[normalize-space()='{text}']]",
    )
    if not buttons:
        return False
    driver.execute_script("arguments[0].click();", buttons[-1])
    return True


def login_x(driver: webdriver.Chrome) -> None:
    """Log in once and leave the resulting session in the persistent profile."""

    username, email, password = get_x_credentials()
    driver.get("https://x.com/i/flow/login")
    time.sleep(4)

    username_fields = driver.find_elements(By.CSS_SELECTOR, "input[autocomplete='username'], input[name='text']")
    if not username_fields:
        logging.info("X already has an authenticated session in this profile.")
        return

    username_fields[0].clear()
    username_fields[0].send_keys(email)
    if not _click_text_button(driver, "Next"):
        username_fields[0].submit()
    time.sleep(2)

    # X sometimes asks for the handle or phone after the email step.
    challenge_fields = driver.find_elements(By.CSS_SELECTOR, "input[name='text']")
    if challenge_fields:
        challenge_fields[0].clear()
        challenge_fields[0].send_keys(username)
        if not _click_text_button(driver, "Next"):
            challenge_fields[0].submit()
        time.sleep(2)

    password_field = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.NAME, "password"))
    )
    password_field.clear()
    password_field.send_keys(password)
    login_buttons = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='LoginForm_Login_Button']")
    if login_buttons:
        login_buttons[0].click()
    elif not _click_text_button(driver, "Log in"):
        password_field.submit()

    time.sleep(6)
    current_url = driver.current_url.lower()
    if driver.find_elements(By.NAME, "password") or "login" in current_url:
        raise RuntimeError(
            "X login did not complete. Check the credentials or complete any "
            "security challenge in headed mode, then rerun with the same profile."
        )
    logging.info("X login completed; the session was saved in the Chrome profile.")


def scroll_page(driver: webdriver.Chrome, scroll_times: int = 80, pause: float = 1.5) -> None:
    """Scroll a timeline or search feed to trigger lazy loading."""

    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        driver.execute_script("window.scrollBy(0, -300);")
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def format_timestamp(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def mentions_ph_location(text: str) -> bool:
    lowered = text.lower()
    return any(location.lower() in lowered for location in PH_LOCATIONS)


def extract_post_url(card: Any) -> str | None:
    try:
        link = card.find_element(By.XPATH, ".//a[contains(@href,'/status/')]").get_attribute("href")
        return link.split("?")[0] if link else None
    except WebDriverException:
        return None


def extract_username(post_url: str | None) -> str:
    if not post_url:
        return "Unknown"
    parts = [part for part in urlsplit(post_url).path.split("/") if part]
    return parts[0] if parts else "Unknown"


def process_x_cards(
    driver: webdriver.Chrome,
    results: list[dict[str, str]],
    seen_urls: set[str],
    identifier: str,
    cards: list[Any],
    cutoff_dt: datetime | None,
    scraped_at: str,
) -> None:
    """Filter and extract visible X post cards."""

    added = 0
    for card in cards:
        try:
            text = card.find_element(By.XPATH, ".//div[@data-testid='tweetText']").text.strip()
        except WebDriverException:
            continue

        if not text:
            continue
        if not any(keyword.lower() in text.lower() for keyword in KEYWORDS):
            continue
        if not mentions_ph_location(text):
            continue

        try:
            raw_timestamp = card.find_element(By.TAG_NAME, "time").get_attribute("datetime")
            post_time = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00")).astimezone(PH_TIME)
        except (AttributeError, TypeError, ValueError, WebDriverException):
            continue
        if cutoff_dt is not None and post_time < cutoff_dt:
            continue

        post_url = extract_post_url(card)
        dedupe_key = post_url or f"{identifier}|{post_time.isoformat()}|{text}"
        if dedupe_key in seen_urls:
            continue

        image_urls = extract_image_urls(driver, card, "x")
        downloaded_image = download_images(
            driver,
            image_urls,
            IMAGE_DIR,
            platform="x",
            post_key=post_url or dedupe_key,
        )
        if downloaded_image is None:
            image_url, image_path = "", ""
        else:
            image_url, image_path = downloaded_image
        seen_urls.add(dedupe_key)
        results.append(
            {
                "source": "X",
                "query_page": identifier,
                "text": text[:5000],
                "post_timestamp": format_timestamp(post_time),
                "scraped_timestamp": scraped_at,
                "user": extract_username(post_url),
                "post_url": post_url or "Unknown",
                "image_url": image_url,
                "image_path": image_path,
            }
        )
        added += 1

    logging.info("[X] %s: +%s flood post(s) (%s cards scanned)", identifier, added, len(cards))


def scrape_x(
    hours_user: int | None = None,
    hours_search: int | None = None,
    *,
    headless: bool = True,
    chromedriver_path: str | None = None,
    profile_dir: Path | str | None = DEFAULT_PROFILE_DIR,
    login: bool = False,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Scrape configured X timelines and searches."""

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    now_ph = datetime.now(PH_TIME)
    since_user = now_ph - timedelta(hours=hours_user) if hours_user is not None else None
    since_search = now_ph - timedelta(hours=hours_search) if hours_search is not None else None
    scraped_at = now_ph.strftime("%Y-%m-%d %H:%M")

    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    driver = init_driver(
        headless=headless,
        chromedriver_path=chromedriver_path,
        profile_dir=profile_dir,
    )

    try:
        if login:
            login_x(driver)

        for user in TWITTER["users"]:
            url = f"https://x.com/{user}"
            logging.info("[x_user] Visiting %s", url)
            driver.get(url)
            time.sleep(4)
            scroll_page(driver)
            cards = driver.find_elements(By.XPATH, "//article[@role='article']")
            process_x_cards(driver, results, seen_urls, user, cards, since_user, scraped_at)
            save_results(results, output_path, checkpoint=f"user:{user}")

        for query in TWITTER["search_queries"]:
            url = f"https://x.com/search?q={quote_plus(query)}&src=typed_query&f=live"
            logging.info("[x_search] Searching '%s'", query)
            driver.get(url)
            time.sleep(4)
            scroll_page(driver)
            cards = driver.find_elements(By.XPATH, "//article[@role='article']")
            process_x_cards(driver, results, seen_urls, query, cards, since_search, scraped_at)
            save_results(results, output_path, checkpoint=f"search:{query}")
    finally:
        driver.quit()

    dataframe = pd.DataFrame(results, columns=CSV_COLUMNS)
    logging.info("X flood scraper collected %s post(s)", len(dataframe))
    return dataframe


def save_results(
    results: list[dict[str, str]],
    output_path: Path | None,
    *,
    checkpoint: str | None = None,
) -> None:
    """Save a checkpoint atomically without overwriting another scrape."""

    if output_path is None:
        return
    dataframe = pd.DataFrame(results, columns=CSV_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    dataframe.to_csv(temporary_path, index=False, encoding="utf-8-sig")
    temporary_path.replace(output_path)
    if checkpoint:
        logging.info(
            "Checkpoint saved after %s: %s row(s) -> %s",
            checkpoint,
            len(dataframe),
            output_path,
        )


def choose_output_path(requested_path: Path | None) -> Path:
    """Create a unique timestamped path for every scrape."""

    timestamp = datetime.now(PH_TIME).strftime("%m-%d-%Y_%H%M%S")
    automatic_path = RAW_DIR / f"twitter_raw_floodData_{timestamp}.csv"

    def unused(path: Path) -> Path:
        candidate = path
        counter = 2
        while candidate.exists():
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            counter += 1
        return candidate

    if requested_path is None:
        return unused(automatic_path)
    if requested_path.name.lower() in {"twitter_raw_flooddata.csv", "twitter_raw_flooddata_latest.csv"}:
        return unused(requested_path.parent / f"twitter_raw_floodData_{timestamp}.csv")
    if requested_path.exists():
        suffix = requested_path.suffix or ".csv"
        return unused(requested_path.with_name(f"{requested_path.stem}_{timestamp}{suffix}"))
    return requested_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape flood-related X posts into CSV.")
    parser.add_argument("--hours-user", type=int, default=None, help="Only keep timeline posts from this many hours ago.")
    parser.add_argument("--hours-search", type=int, default=None, help="Only keep search posts from this many hours ago.")
    parser.add_argument("--headed", action="store_true", help="Show Chrome while scraping.")
    parser.add_argument("--login", action="store_true", help="Log in using X_* environment variables before scraping.")
    parser.add_argument("--chromedriver", help="Path to chromedriver.exe.")
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR, help=f"Persistent Chrome profile (default: {DEFAULT_PROFILE_DIR}).")
    parser.add_argument("--output", type=Path, default=None, help="Optional output path; omitted means a new timestamped CSV.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = choose_output_path(args.output)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.info("This run will save to %s", output_path)
    try:
        dataframe = scrape_x(
            hours_user=args.hours_user,
            hours_search=args.hours_search,
            headless=not args.headed and not args.login,
            chromedriver_path=args.chromedriver,
            profile_dir=args.profile_dir,
            login=args.login,
            output_path=output_path,
        )
        save_results(dataframe.to_dict("records"), output_path)
        logging.info("Saved %s row(s) to %s", len(dataframe), output_path)
        return 0
    except KeyboardInterrupt:
        logging.warning("Scraper interrupted. The latest checkpoint, if any, remains at %s", output_path)
        return 130
    except (RuntimeError, TimeoutException) as error:
        logging.error("X scraper stopped: %s", error)
        return 1
    except WebDriverException as error:
        logging.error("ChromeDriver could not start or load X: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
