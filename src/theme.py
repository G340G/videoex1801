import hashlib
import time
import random


KEYWORDS = [
    "signal", "archive", "broadcast", "instruction", "warning",
    "obsolete", "contamination", "frequency", "recovery", "anomaly",
    "protocol", "inspection", "calibration", "incident", "unmarked",
    "dust", "static", "relay", "terminal", "threshold"
]

TOPICS = [
    "numbers station", "fog", "abandoned facility", "medical pamphlet",
    "railway bulletin", "civil defense", "field report", "weather radar",
    "missing person notice", "equipment manual", "interference pattern",
    "photographic plate", "floodlight survey", "underground corridor",
    "shortwave logbook"
]


def _stable_int(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def make_seed_and_theme(seed_cfg: str):
    if seed_cfg == "AUTO":
        # time-based but still printed for reproducibility
        seed_cfg = str(int(time.time()))
    seed = seed_cfg
    rng = random.Random(_stable_int(seed))

    kw = rng.choice(KEYWORDS)
    topic = rng.choice(TOPICS)

    # A “coherence anchor” phrase that will drive scraping + on-screen copy
    anchor = f"{kw} {topic}"
    return seed, {"keyword": kw, "topic": topic, "anchor": anchor, "rng_int": _stable_int(seed)}
