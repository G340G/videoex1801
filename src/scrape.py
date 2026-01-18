import random
import re
from pathlib import Path
from typing import Dict, List

import requests


WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Wikimedia recommends identifying your application with a clear UA.
# In GitHub Actions, a missing/weak UA often yields 403.
DEFAULT_UA = "videoex1801-vhs-arg-generator/1.0 (GitHub Actions; contact: none)"


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
    }, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    if not pages:
        return ""
    page = next(iter(pages.values()))
    return page.get("extract", "") or ""


def wiki_images(lang: str, title: str, thumb_width: int = 1200, max_images: int = 8) -> List[str]:
    s = _session()
    # 1) get images list for page
    r = s.get(WIKI_API.format(lang=lang), params={
        "action": "query",
        "titles": title,
        "prop": "images",
        "format": "json",
        "imlimit": 50,
    }, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    if not pages:
        return []
    page = next(iter(pages.values()))
    imgs = [
        x["title"] for x in page.get("images", [])
        if x.get("title", "").lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    # 2) fetch imageinfo from commons for thumbnails
    urls = []
    for name in imgs[: max_images * 3]:
        rr = s.get(COMMONS_API, params={
            "action": "query",
            "titles": name,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": thumb_width,
            "format": "json",
        }, timeout=30)
        rr.raise_for_status()
        pdata = rr.json().get("query", {}).get("pages", {})
        if not pdata:
            continue
        p = next(iter(pdata.values()))
        ii = (p.get("imageinfo") or [])
        if not ii:
            continue
        thumb = ii[0].get("thumburl") or ii[0].get("url")
        if thumb:
            urls.append(thumb)
        if len(urls) >= max_images:
            break
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
    parts = [p for p in parts if len(p) > 80]
    return [_safe_text(p) for p in parts[:max_paragraphs]]


def scrape_bundle(cfg: dict, theme: dict, workdir: Path) -> Dict:
    """
    Scrape bundle is best-effort:
    - If Wikipedia blocks (403) or any network error happens, we fall back to a local bundle.
    - This keeps the generator reliable in CI.
    """
    rng = random.Random(theme["rng_int"])
    lang = cfg["scrape"].get("wikipedia_lang", "en")
    anchor = theme["anchor"]

    # --- fallback local pack (keeps video coherent even offline/blocked)
    fallback_titles = ["Shortwave radio", "Noise (electronics)", "Numbers station"]
    fallback_paras = [
        "A weak carrier tone persists beneath broadband noise. Interference fluctuates with time, distance, and equipment condition. "
        "Signal artifacts repeat in patterns that resemble synchronization attempts.",
        "Recorded material may exhibit dropouts, tracking errors, and temporal smearing. These distortions can resemble intentional edits, "
        "even when caused by damaged tape or unstable playback.",
        "When documentation is incomplete, interpretation drifts. The record remains technically consistent while meaning becomes uncertain."
    ]

    try:
        titles = wiki_search(lang, anchor, limit=8)
        if not titles:
            titles = wiki_search(lang, theme["keyword"], limit=8)
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

    for t in picked:
        try:
            ex = wiki_extract(lang, t)
            paras.extend(pick_paragraphs(ex, cfg["scrape"].get("max_wiki_paragraphs", 6)))
        except Exception:
            # continue collecting from other titles
            pass

        if cfg["scrape"].get("allow_wikimedia", True):
            try:
                urls = wiki_images(
                    lang, t,
                    thumb_width=1400,
                    max_images=cfg["scrape"].get("max_images", 8)
                )
                rng.shuffle(urls)
                for u in urls:
                    if len(image_paths) >= cfg["scrape"].get("max_images", 8):
                        break
                    outp = img_dir / f"img_{len(image_paths):02d}.jpg"
                    if download_image(u, outp):
                        image_paths.append(str(outp))
                        image_urls.append(u)
            except Exception:
                pass

    if not paras:
        paras = fallback_paras

    # creepy technical metadata lines (seeded)
    tech = []
    for _ in range(12):
        code = rng.randint(100, 999)
        hz = rng.randint(2000, 18000)
        tech.append(f"{theme['keyword'].upper()}-{code} / CARRIER {hz}Hz / CHECKSUM {rng.randint(100000, 999999)}")

    return {
        "titles": picked,
        "paragraphs": paras[: cfg["scrape"].get("max_wiki_paragraphs", 6)],
        "images": image_paths,
        "image_urls": image_urls,
        "tech_lines": tech,
    }

