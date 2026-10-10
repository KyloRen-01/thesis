#!/usr/bin/env python3
"""Collect flood-related Facebook posts and save them as CSV.

This follows the senior project's Facebook scraper structure:

* visit configured page timelines;
* visit configured flood-related hashtag and post-search feeds;
* scroll to trigger Facebook's lazy loading;
* extract visible post text, timestamps, authors, and URLs;
* apply flood and Philippine-location filters;
* return a pandas DataFrame for CSV storage.

The scraper does not attempt to bypass login, CAPTCHA, or other access
controls. It only processes content visible to the Selenium browser session.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

try:
    from .fb_scraping_config import FACEBOOK, KEYWORDS, PH_LOCATIONS
except ImportError:
    # Allows direct execution with: py src/scraper/fb_flood_scraper.py
    from fb_scraping_config import FACEBOOK, KEYWORDS, PH_LOCATIONS


BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw" / "facebook"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PH_TIME = timezone(timedelta(hours=8))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DEFAULT_PROFILE_DIR = BASE_DIR / ".facebook_chrome_profile"


def init_driver(
    *,
    headless: bool = True,
    chromedriver_path: str | None = None,
    profile_dir: Path | str | None = DEFAULT_PROFILE_DIR,
) -> webdriver.Chrome:
    """Create Chrome through an explicit ChromeDriver service.

    ``CHROMEDRIVER_PATH`` may be used when a local executable must be selected.
    If it is not supplied, Selenium Manager resolves a compatible driver.
    ``profile_dir`` persists cookies between runs so manual Facebook login is
    not lost when the scraper exits.
    """

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


def scroll_page(driver: webdriver.Chrome, scroll_times: int = 80, pause: float = 1.5) -> None:
    """Scroll through a feed until it stops growing or the limit is reached."""

    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        driver.execute_script("window.scrollBy(0, -300);")
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def mentions_ph_location(text: str) -> bool:
    lowered = text.lower()
    return any(location.lower() in lowered for location in PH_LOCATIONS)


def extract_utime(post: Any) -> int | None:
    try:
        raw = post.find_element(By.XPATH, ".//abbr").get_attribute("data-utime")
        return int(raw) if raw else None
    except (ValueError, WebDriverException):
        return None


def format_readable(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def clean_comment_tail(text: str) -> str:
    """Keep the post caption and remove common visible comment-tail labels."""

    comment_patterns = [
        r"stay safe",
        r"ingat",
        r"commented",
        r"replied",
        r"shared",
        r"tagged",
        r"^see more comments",
        r"^view more replies",
    ]
    lines = text.splitlines()
    filtered_lines = []
    for line in lines:
        if any(re.search(pattern, line.strip().lower()) for pattern in comment_patterns):
            break
        filtered_lines.append(line)
    return " ".join(filtered_lines).strip()


def expand_see_more(driver: webdriver.Chrome, post: Any) -> None:
    try:
        button = post.find_element(
            By.XPATH,
            ".//div[contains(@role,'button') and contains(normalize-space(.),'See more')]",
        )
        driver.execute_script("arguments[0].click();", button)
        time.sleep(0.5)
    except WebDriverException:
        pass


def extract_caption(driver: webdriver.Chrome, post: Any) -> str | None:
    """Extract visible post text, expanding a collapsed caption when possible."""

    try:
        expand_see_more(driver, post)
        blocks = post.find_elements(By.XPATH, ".//div[@dir='auto']")
        if not blocks:
            return None
        joined = " ".join(block.text.strip() for block in blocks[:2] if block.text.strip())
        text = clean_comment_tail(joined)
        return text if text and len(text.split()) >= 3 else None
    except WebDriverException:
        return None


def extract_username(post: Any) -> str:
    try:
        return post.find_element(By.XPATH, ".//h4//a").text or "Unknown"
    except WebDriverException:
        return "Unknown"


def extract_post_url(driver: webdriver.Chrome, post: Any) -> str:
    try:
        links = post.find_elements(By.XPATH, ".//a[@href]")
        for link in links:
            href = link.get_attribute("href") or ""
            if any(marker in href for marker in ("/posts/", "/permalink/", "/videos/")):
                return href.split("?")[0]
    except WebDriverException:
        pass
    return driver.current_url


def process_fb_articles(
    driver: webdriver.Chrome,
    results: list[dict[str, str]],
    seen_urls: set[str],
    identifier: str,
    is_search_query: bool,
    since_page: datetime | None,
    since_query: datetime | None,
    scraped_timestamp: str,
) -> None:
    """Extract flood posts from the currently loaded Facebook feed."""

    articles = driver.find_elements(By.XPATH, "//div[@role='article']")
    added = 0

    for article in articles:
        text = extract_caption(driver, article)
        if not text:
            continue
        if not any(keyword.lower() in text.lower() for keyword in KEYWORDS):
            continue
        if not mentions_ph_location(text):
            continue

        post_timestamp = "Unknown"
        unix_timestamp = extract_utime(article)
        if unix_timestamp:
            post_time = datetime.fromtimestamp(unix_timestamp, tz=PH_TIME)
            cutoff = since_query if is_search_query else since_page
            if cutoff is not None and post_time < cutoff:
                continue
            post_timestamp = format_readable(post_time)

        post_url = extract_post_url(driver, article)
        if post_url in seen_urls:
            continue
        seen_urls.add(post_url)

        results.append(
            {
                "source": "Facebook",
                "query_page": identifier,
                "text": text[:5000],
                "post_timestamp": post_timestamp,
                "scraped_timestamp": scraped_timestamp,
                "user": extract_username(article),
                "post_url": post_url,
            }
        )
        added += 1

    logging.info(
        "[Facebook] %s: +%s flood post(s) (%s article(s) scanned)",
        identifier,
        added,
        len(articles),
    )


def scrape_facebook(
    hours_page: int | None = None,
    hours_search: int | None = None,
    *,
    headless: bool = True,
    chromedriver_path: str | None = None,
    profile_dir: Path | str | None = DEFAULT_PROFILE_DIR,
    login: bool = False,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Scrape configured Facebook pages, hashtags, and post searches.

    With ``login=True``, the browser opens Facebook in headed mode and waits
    for the user to complete login manually before collection starts.
    """

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    now_ph = datetime.now(PH_TIME)
    since_page = now_ph - timedelta(hours=hours_page) if hours_page is not None else None
    since_query = now_ph - timedelta(hours=hours_search) if hours_search is not None else None
    scraped_timestamp = now_ph.strftime("%Y-%m-%d %H:%M")

    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    driver = init_driver(
        headless=headless,
        chromedriver_path=chromedriver_path,
        profile_dir=profile_dir,
    )

    try:
        if login:
            driver.get("https://www.facebook.com/")
            print(
                "\nA Facebook Chrome window is open. Complete login manually there, "
                "then return to this terminal and press Enter to start scraping."
            )
            input()

        for page in FACEBOOK["users"]:
            url = f"https://www.facebook.com/{page.rstrip('/')}/posts"
            logging.info("[fb_page] Visiting %s", url)
            driver.get(url)
            time.sleep(5)
            scroll_page(driver)
            process_fb_articles(
                driver,
                results,
                seen_urls,
                page,
                False,
                since_page,
                since_query,
                scraped_timestamp,
            )
            save_results(results, output_path, checkpoint=f"page:{page}")

        for tag in FACEBOOK["search_queries"]:
            encoded_tag = quote_plus(tag)
            url = f"https://www.facebook.com/hashtag/{encoded_tag}"
            logging.info("[fb_hashtag] Visiting #%s", tag)
            driver.get(url)
            time.sleep(5)
            scroll_page(driver)
            process_fb_articles(
                driver,
                results,
                seen_urls,
                f"#{tag}",
                True,
                since_page,
                since_query,
                scraped_timestamp,
            )
            save_results(results, output_path, checkpoint=f"hashtag:{tag}")

        for query in FACEBOOK["search_queries"]:
            url = f"https://www.facebook.com/search/posts/?q={quote_plus(query)}"
            logging.info("[fb_search] Searching '%s'", query)
            driver.get(url)
            time.sleep(5)
            scroll_page(driver)
            process_fb_articles(
                driver,
                results,
                seen_urls,
                query,
                True,
                since_page,
                since_query,
                scraped_timestamp,
            )
            save_results(results, output_path, checkpoint=f"search:{query}")
    finally:
        driver.quit()

    dataframe = pd.DataFrame(
        results,
        columns=[
            "source",
            "query_page",
            "text",
            "post_timestamp",
            "scraped_timestamp",
            "user",
            "post_url",
        ],
    )
    logging.info("Facebook flood scraper collected %s post(s)", len(dataframe))
    return dataframe


def save_results(
    results: list[dict[str, str]],
    output_path: Path | None,
    *,
    checkpoint: str | None = None,
) -> None:
    """Save a checkpoint atomically so interruption does not lose prior feeds."""

    if output_path is None:
        return

    dataframe = pd.DataFrame(
        results,
        columns=[
            "source",
            "query_page",
            "text",
            "post_timestamp",
            "scraped_timestamp",
            "user",
            "post_url",
        ],
    )
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
    """Return a unique output path for this run.

    Slashes are invalid in Windows filenames, so the date uses hyphens while
    retaining the requested month-day-year and time order.
    """

    timestamp = datetime.now(PH_TIME).strftime("%m-%d-%Y_%H%M%S")
    automatic_path = RAW_DIR / f"fb_raw_floodData_{timestamp}.csv"

    def unused(path: Path) -> Path:
        candidate = path
        counter = 2
        while candidate.exists():
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            counter += 1
        return candidate

    if requested_path is None:
        return unused(automatic_path)

    # Treat the old fixed-name convention as a request for a new run file.
    if requested_path.name.lower() in {"fb_raw_flooddata_latest.csv", "fb_raw_flood_posts.csv"}:
        return unused(requested_path.parent / f"fb_raw_floodData_{timestamp}.csv")

    # Never overwrite an existing explicitly named output either.
    if requested_path.exists():
        suffix = requested_path.suffix or ".csv"
        stem = requested_path.stem
        return unused(requested_path.with_name(f"{stem}_{timestamp}{suffix}"))

    return requested_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape flood-related Facebook posts into CSV.")
    parser.add_argument(
        "--hours-page",
        type=int,
        default=None,
        help="Only keep page posts from this many hours ago. Omit for no time cutoff.",
    )
    parser.add_argument(
        "--hours-search",
        type=int,
        default=None,
        help="Only keep search/hashtag posts from this many hours ago. Omit for no time cutoff.",
    )
    parser.add_argument("--headed", action="store_true", help="Show Chrome while scraping.")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open Facebook for manual login before scraping; implies headed mode.",
    )
    parser.add_argument("--chromedriver", help="Path to chromedriver.exe.")
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=DEFAULT_PROFILE_DIR,
        help=f"Persistent Chrome profile directory (default: {DEFAULT_PROFILE_DIR}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path. Omit it to create a timestamped CSV automatically.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = choose_output_path(args.output)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.info("This run will save to %s", output_path)
    try:
        dataframe = scrape_facebook(
            hours_page=args.hours_page,
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
    except WebDriverException as error:
        logging.error("ChromeDriver could not start or load Facebook: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
