"""Small helpers shared by the Facebook and X flood scrapers."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from selenium.webdriver.common.by import By


MAX_IMAGE_BYTES = 25 * 1024 * 1024


def _largest_srcset_url(srcset: str) -> str | None:
    """Return the last URL in a srcset, which is normally the largest one."""

    candidates: list[tuple[float, str]] = []
    for item in srcset.split(","):
        parts = item.strip().split()
        if not parts:
            continue
        descriptor = parts[1] if len(parts) > 1 else "0w"
        try:
            size = float(descriptor[:-1]) if descriptor.endswith("w") else 0.0
        except ValueError:
            size = 0.0
        candidates.append((size, parts[0]))
    return max(candidates, default=(0.0, None))[1]


def normalize_image_url(url: str, platform: str) -> str:
    """Prefer the largest normal X image variant when one is available."""

    if platform.lower() != "x" or "pbs.twimg.com" not in url:
        return url

    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "name" in query:
        query["name"] = "large"
    return urlunsplit(parsed._replace(query=urlencode(query)))


def extract_image_urls(driver: Any, post: Any, platform: str) -> list[str]:
    """Extract post-media image URLs while ignoring avatars and UI icons."""

    if platform.lower() == "x":
        images = post.find_elements(
            By.XPATH,
            ".//div[@data-testid='tweetPhoto']//img[@src or @data-src or @srcset]",
        )
    else:
        images = post.find_elements(By.XPATH, ".//img[@src or @data-src or @srcset]")

    urls: list[str] = []
    for image in images:
        try:
            srcset = image.get_attribute("srcset") or ""
            src = _largest_srcset_url(srcset) or image.get_attribute("src") or image.get_attribute("data-src")
            if not src or not src.startswith(("http://", "https://")):
                continue

            alt = (image.get_attribute("alt") or "").lower()
            if platform.lower() == "facebook" and any(
                marker in alt for marker in ("profile picture", "avatar", "emoji")
            ):
                continue

            # Facebook renders many icons and avatars as <img> elements. Real
            # post media is normally substantially larger than those elements.
            dimensions = driver.execute_script(
                "return {width: arguments[0].naturalWidth || 0, height: arguments[0].naturalHeight || 0};",
                image,
            )
            width = int(dimensions.get("width", 0))
            height = int(dimensions.get("height", 0))
            if platform.lower() == "facebook" and width and height and (width < 150 or height < 100):
                continue

            normalized = normalize_image_url(src, platform)
            if normalized not in urls:
                urls.append(normalized)
        except Exception:  # A stale image element should not discard its post.
            continue

    return urls


def download_images(
    driver: Any,
    image_urls: list[str],
    image_dir: Path,
    *,
    platform: str,
    post_key: str,
) -> tuple[str, str] | None:
    """Download the first usable post image and return its URL/path pair."""

    if not image_urls:
        return None

    image_dir.mkdir(parents=True, exist_ok=True)
    cookies = "; ".join(
        f"{cookie['name']}={cookie['value']}" for cookie in driver.get_cookies()
    )
    project_root = Path(__file__).resolve().parents[2]
    for image_url in image_urls:
        digest = hashlib.sha256(f"{post_key}|{image_url}".encode("utf-8")).hexdigest()[:20]
        request = Request(
            image_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Referer": post_key
                if post_key.startswith("http")
                else ("https://x.com/" if platform.lower() == "x" else "https://www.facebook.com/"),
                "Cookie": cookies,
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                content_type = (response.headers.get_content_type() or "").lower()
                payload = response.read(MAX_IMAGE_BYTES + 1)
            if len(payload) > MAX_IMAGE_BYTES or not content_type.startswith("image/"):
                logging.debug("Skipping non-image or oversized media: %s", image_url)
                continue

            extension = mimetypes.guess_extension(content_type) or ".jpg"
            if extension == ".jpe":
                extension = ".jpg"
            output_path = image_dir / f"{platform.lower()}_{digest}{extension}"
            if not output_path.exists():
                output_path.write_bytes(payload)
            try:
                relative_path = output_path.relative_to(project_root).as_posix()
            except ValueError:
                relative_path = str(output_path)
            return image_url, relative_path
        except Exception as error:
            logging.debug("Could not download image %s: %s", image_url, error)

    return None
