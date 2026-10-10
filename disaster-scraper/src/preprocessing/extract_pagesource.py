import re
import numpy as np
from preprocessing.location_filter import mentions_ph_location

# Define mapping from raw usernames → formatted organization names
SOURCE_NAME_MAP = {
    "abscbnnews": "ABS-CBN",
    "atenews": "Atenews",
    "bfprhq11": "BFPRHQ11",
    "civildefensedavao": "Civil Defense Davao",
    "davaocitydrmmc": "Davao City DRRMC",
    "davaodrrmo": "Davao DRRMO",
    "davaocitydisasterradio": "Davao City Disaster Radio",
    "dzmmteleradyo.mspc": "DZMM Teleradyo MSPC",
    "gmanews": "GMA News",
    "inquirerdotnet": "Inquirer.net",
    "manilabulletin": "Manila Bulletin",
    "mprsdcdo": "MPRSD CDO",
    "mindanews": "Mindanews",
    "mrpsd.com.ph": "MRPSD",
    "ndrrmc": "NDRRMC",
    "pagasa.dost.gov.ph": "PAGASA",
    "philstarnews": "Philstar News",
    "phivolcs": "PHIVOLCS",
    "piagovernment": "PIA Government",
    "rapplerdotcom": "Rappler",
    "sunstardavaonews": "SunStar Davao",
    "sunstarphilippines": "SunStar Philippines",
    "stormchasersph": "Storm Chasers PH",
    "untvnewsrescue": "UNTV News Rescue",
    "weather.davao": "Weather Davao",
}

# 🔑 Whitelist for trusted sources (normalize to lowercase)
TRUSTED_SOURCES = {
    # Official PH agencies
    "pagasa", "pagasa.dost.gov.ph", "dost.pagasa", "phivolcs", "ndrrmc",
    "piagovernment",

    # Major PH news orgs
    "abs-cbn", "gma news", "philstar news", "inquirer.net",
    "manila bulletin", "rappler",

    # Regional / local PH sources
    "sunstar davao", "sunstar philippines",
    "atenews", "mindanews",
    "mprsdcdo", "mrpsd.com.ph",
    "davao city drrmc", "davao drrmo", "davao city disaster radio",
    "dzmm teleradyo mspc",
    "storm chasers ph", "untv news rescue", "weather davao",
    "bfprhq11", "civil defense davao"
}

TRUSTED_SOURCES = {s.lower() for s in TRUSTED_SOURCES}

def extract_pagesource(url):
    if not isinstance(url, str):
        return np.nan

    # 1. If URL points to a hashtag
    hashtag_match = re.search(r"(?:facebook\.com|x\.com)/hashtag/([^/?#\s]+)", url)
    if hashtag_match:
        return f"#{hashtag_match.group(1).lower()}"

    # 2. Otherwise extract the page name/username
    match = re.search(r"(?:facebook\.com|x\.com)/(?!hashtag|watch|reel)([^/?#\s]+)", url)
    if match:
        raw_page = match.group(1).lower().strip().strip(".@/")
        return SOURCE_NAME_MAP.get(raw_page, raw_page)

    return np.nan

def keep_post(row):
    """Keep post if it mentions PH location or comes from trusted source."""
    txt_ok = mentions_ph_location(row.get("text_content", ""))
    src = str(row.get("page_source", "")).lower()
    trusted_ok = src in TRUSTED_SOURCES
    return txt_ok or trusted_ok