import random
import re
from pathlib import Path
from typing import Dict, List

import requests


WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

DEFAULT_UA = "videoex1801-vhs-arg-generator/1.1 (GitHub Actions; contact: none)"


def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def _safe_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s


def wiki_search(lang: str, query: str, limit: int = 6) -> List[str]:
    s = _session()
    r = s.get(WIKI_API.format(lang=lang), params={
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": limit,
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    return [x["title"] for x in data.get("query", {}).get("search", [])]


def wiki_extract(lang: str, title: str) -> str:
    s = _session()
    r = s.get(WIKI_API.format(lang=lang), params={
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "titles": title,
        "format": "json",
        "exsectionformat": "plain",
    }, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    if not pages:
        return ""
    page = next(iter(pages.values()))
    return page.get("extract", "") or ""


def commons_search_image_urls(query: str, thumb_width: int = 1400, limit: int = 12) -> List[str]:
    """
    Search Wikimedia Commons directly (more reliable than page-embedded images).
    """
    s = _session()
    r = s.get(COMMONS_API, params={
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": limit,
        "gsrnamespace": 6,   # File:
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": thumb_width,
        "format": "json",
    }, timeout=30)
    r.raise_for_status()
    pages = (r.json().get("query", {}) or {}).get("pages", {}) or {}
    urls = []
    for _, p in pages.items():
        ii = (p.get("imageinfo") or [])
        if not ii:
            continue
        u = ii[0].get("thumburl") or ii[0].get("url")
        if u and any(u.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            urls.append(u)
    return urls


def download_image(url: str, out_path: Path) -> bool:
    s = _session()
    try:
        r = s.get(url, timeout=30)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return True
    except Exception:
        return False


def pick_paragraphs(extract: str, max_paragraphs: int) -> List[str]:
    parts = [p.strip() for p in extract.split("\n") if p.strip()]
    # keep paragraphs with some substance
    parts = [p for p in parts if len(p) > 90]
    return [_safe_text(p) for p in parts[:max_paragraphs]]


def scrape_bundle(cfg: dict, theme: dict, workdir: Path) -> Dict:
    rng = random.Random(theme["rng_int"])
    lang = cfg["scrape"].get("wikipedia_lang", "en")
    anchor = theme["anchor"]
    brain = theme["brain"]

    fallback_titles = ["Shortwave radio", "Noise (electronics)", "Numbers station"]
    fallback_paras = [
        "A weak carrier tone persists beneath broadband noise. Interference fluctuates with time, distance, and equipment condition.",
        "Recorded material may exhibit dropouts, tracking errors, and temporal smearing that resemble intentional edits.",
        "When documentation is incomplete, interpretation drifts. The record remains technically consistent while meaning becomes uncertain.",
        "Field notes indicate repeated patterns at irregular intervals. The source remains unverified.",
    ]

    # Titles
    try:
        titles = wiki_search(lang, anchor, limit=10)
        if not titles:
            titles = wiki_search(lang, brain, limit=10)
        if not titles:
            titles = fallback_titles
    except Exception:
        titles = fallback_titles

    rng.shuffle(titles)
    picked = titles[:3]

    paras = []
    image_paths = []
    image_urls = []

    img_dir = workdir / "imgs"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Text
    for t in picked:
        try:
            ex = wiki_extract(lang, t)
            paras.extend(pick_paragraphs(ex, cfg["scrape"].get("max_wiki_paragraphs", 8)))
        except Exception:
            pass

    if not paras:
        paras = fallback_paras

    # Images: Commons direct search (anchor + brain) so we actually get something
    urls = []
    if cfg["scrape"].get("allow_wikimedia", True) and cfg["scrape"].get("commons_search_fallback", True):
        try:
            urls.extend(commons_search_image_urls(anchor, limit=12))
        except Exception:
            pass
        try:
            urls.extend(commons_search_image_urls(brain, limit=12))
        except Exception:
            pass

    # dedupe
    seen = set()
    urls2 = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        urls2.append(u)

    rng.shuffle(urls2)
    max_images = int(cfg["scrape"].get("max_images", 10))
    for u in urls2[:max_images]:
        outp = img_dir / f"img_{len(image_paths):02d}.jpg"
        if download_image(u, outp):
            image_paths.append(str(outp))
            image_urls.append(u)

    tech = []
    for _ in range(16):
        code = rng.randint(100, 999)
        hz = rng.randint(2000, 18000)
        tech.append(f"{brain.upper()}-{code} / CARRIER {hz}Hz / CRC {rng.randint(100000, 999999)}")

    return {
        "titles": picked,
        "paragraphs": paras[: int(cfg["scrape"].get("max_wiki_paragraphs", 8))],
        "images": image_paths,
        "image_urls": image_urls,
        "tech_lines": tech,
        "brain": brain,
        "anchor": anchor,
    }


