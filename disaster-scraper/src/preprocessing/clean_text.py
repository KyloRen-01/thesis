import re
import unicodedata as ud

def normalize_fonted_unicode(text):
    return ''.join(
        c for c in ud.normalize('NFKD', text)
        if not ud.combining(c)
    )
    
def clean_text(text):
    """
    Lightly normalize text for semantic embedding (RAG-ready):
    - Keeps punctuation and hashtags
    - Removes URLs, emojis, HTML, and non-text noise
    - Lowercases
    - Preserves structure and disaster-relevant terms
    """
    text = str(text)
    if text.lower().strip() in {"", "nan", "none"}:
        return ""

    text = normalize_fonted_unicode(text)                     # Normalize stylized Unicode (𝑨 → A)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)         # Remove URLs
    text = re.sub(r"<.*?>", "", text)                         # Remove HTML tags
    text = re.sub(r"&\w+;", "", text)                         # Remove HTML entities like &amp;
    text = re.sub(r"[-=*_]{3,}", " ", text)                   # Remove visual separators like "====", "-----", "***"
    text = re.sub(r"(\.\s*){3,}", " ", text)                  # Remove long dot or spaced-dot patterns ("....." or ". . . . .")
    text = text.encode("ascii", "ignore").decode("ascii")     # Remove emojis and non-ASCII chars
    text = re.sub(r"\s+", " ", text).strip()                  # Normalize spacing
    text = text.lower()                                       # Lowercase (preserve hashtags)

    # Optional: remove "shared" boilerplate text if desired
    text = re.sub(r"(shared a post|see more|commented|replied)", "", text, flags=re.I)

    # Skip if only punctuation or too short
    if len(text) < 90 or re.fullmatch(r"[. ]+", text):
        return ""
    
    # Skip if text is mostly numeric or looks like a garbage timestamp
    if re.fullmatch(r"[0-9\s:/.-]{6,}", text):
        return ""

    return text