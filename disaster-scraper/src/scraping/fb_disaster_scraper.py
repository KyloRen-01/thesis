#!/usr/bin/env python3
import re
import time
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from scraping.social_media_config import KEYWORDS, FACEBOOK

# --- Setup base dirs (safe absolute paths) ---
BASE_DIR = Path(__file__).resolve().parents[2]
LOOKUP_DIR = BASE_DIR / "data" / "lookup"
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# --- Setup constants ---
PH_TIME = timezone(timedelta(hours=8))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

# --- Load PH location reference data ---
ref_cities = pd.read_csv(LOOKUP_DIR / "refcitymun.csv")
ref_provs = pd.read_csv(LOOKUP_DIR / "refprovince.csv")
ref_regs = pd.read_csv(LOOKUP_DIR / "refregion.csv")

PH_LOCATIONS = set(
    pd.concat([ref_cities["citymunDesc"], ref_provs["provDesc"], ref_regs["regDesc"]], ignore_index=True)
    .str.lower()
    .str.strip()
    .unique()
)
PH_LOCATIONS.update(["philippines", "pilipinas", "ph"])


# --- Selenium Helpers ---
def init_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def scroll_page(driver, scroll_times=80, pause=1.5):
    """Scrolls through a Facebook page multiple times with small upward nudges to trigger lazy loading."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        driver.execute_script("window.scrollBy(0, -300);")  # tiny nudge to refresh
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


# --- Text Utilities ---
def mentions_ph_location(text):
    text = text.lower()
    return any(loc in text for loc in PH_LOCATIONS)


def extract_utime(post):
    try:
        raw = post.find_element(By.XPATH, ".//abbr").get_attribute("data-utime")
        return int(raw) if raw else None
    except:
        return None


def format_readable(ts):
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def clean_comment_tail(text):
    COMMENT_PATTERNS = [
        r"(stay safe|ingat|commented|replied|shared|🙏|po$|tagged)",
        r"^see more comments",
        r"^view more replies",
    ]
    lines = text.splitlines()
    filtered = []
    for line in lines:
        if any(re.search(pat, line.strip().lower()) for pat in COMMENT_PATTERNS):
            break
        filtered.append(line)
    return " ".join(filtered).strip()


def expand_see_more(driver, post):
    try:
        btn = post.find_element(By.XPATH, ".//div[contains(@role,'button') and contains(text(),'See more')]")
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(1)
    except:
        pass


def extract_caption(driver, post):
    """Extract visible post text, clicking 'See more' if needed."""
    try:
        expand_see_more(driver, post)
        blocks = post.find_elements(By.XPATH, ".//div[@dir='auto']")
        if not blocks:
            return None

        joined = " ".join(b.text.strip() for b in blocks[:2] if b.text.strip())
        text = clean_comment_tail(joined)
        if not text or len(text.split()) < 3:
            return None
        return text
    except:
        return None


def extract_username(post):
    try:
        return post.find_element(By.XPATH, ".//h4//a").text
    except:
        return "Unknown"


def extract_post_url(driver, post):
    try:
        return post.find_element(By.XPATH, ".//a[contains(@href,'/posts/')]").get_attribute("href")
    except:
        return driver.current_url


# --- Core scraper logic ---
def process_fb_articles(driver, results, identifier, is_search_query, since_page, since_hashtag, scraped_timestamp):
    articles = driver.find_elements(By.XPATH, "//div[@role='article']")
    added = 0

    for art in articles:
        text = extract_caption(driver, art)
        if not text:
            continue
        if not any(k in text.lower() for k in KEYWORDS):
            continue
        if not mentions_ph_location(text):
            continue

        ut = extract_utime(art)
        if ut:
            post_time = datetime.fromtimestamp(ut, tz=PH_TIME)
            cutoff = since_hashtag if is_search_query else since_page
            if post_time < cutoff:
                continue
            post_timestamp = format_readable(post_time)
        else:
            post_timestamp = "Unknown"

        results.append({
            "source": "Facebook",
            "query_page": identifier,
            "text": text[:5000],
            "post_timestamp": post_timestamp,
            "scraped_timestamp": scraped_timestamp,
            "user": extract_username(art),
            "post_url": extract_post_url(driver, art),
        })
        added += 1

    if added > 0:
        logging.info(f"[Facebook] {identifier}: +{added} posts ({len(articles)} articles scanned)")
    else:
        logging.info(f"[Facebook] {identifier}: no new posts found")


# --- Main function ---
def scrape_facebook(hours_page=24, hours_hashtag=24):
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    now_ph = datetime.now(PH_TIME)
    since_time_page = now_ph - timedelta(hours=hours_page)
    since_time_hashtag = now_ph - timedelta(hours=hours_hashtag)
    scraped_timestamp = now_ph.strftime("%Y-%m-%d %H:%M")

    FB_PAGES = FACEBOOK["users"]
    FB_QUERIES = FACEBOOK["search_queries"]

    driver = init_driver()
    results = []

    # --- Page feeds ---
    for page in FB_PAGES:
        url = f"https://www.facebook.com/{page.rstrip('/')}/posts"
        logging.info(f"[fb_page] Visiting {url}")
        driver.get(url)
        time.sleep(5)
        scroll_page(driver)
        process_fb_articles(driver, results, page, False, since_time_page, since_time_hashtag, scraped_timestamp)

    # --- Hashtag feeds ---
    for tag in FB_QUERIES:
        url = f"https://www.facebook.com/hashtag/{tag}"
        logging.info(f"[fb_hashtag] Visiting #{tag}")
        driver.get(url)
        time.sleep(5)
        scroll_page(driver)
        process_fb_articles(driver, results, f"#{tag}", True, since_time_page, since_time_hashtag, scraped_timestamp)

    # --- Search feeds ---
    for query in FB_QUERIES:
        url = f"https://www.facebook.com/search/posts/?q={query}"
        logging.info(f"[fb_search] Searching '{query}'")
        driver.get(url)
        time.sleep(5)
        scroll_page(driver)
        process_fb_articles(driver, results, query, True, since_time_page, since_time_hashtag, scraped_timestamp)

    driver.quit()

    df = pd.DataFrame(results)
    logging.info(f"✅ Scraped {len(df)} total posts from Facebook (past {hours_page}h).")
    return df


if __name__ == "__main__":
    df = scrape_facebook()
    out_path = RAW_DIR / "fb_raw_disaster_posts.csv"
    df.to_csv(out_path, index=False)
    logging.info(f"✅ Saved to {out_path}")
