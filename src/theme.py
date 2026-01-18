import hashlib
import time
import random


KEYWORDS = [
    "contamination", "signal", "archive", "broadcast", "protocol",
    "interference", "recovery", "anomaly", "inspection", "calibration",
    "threshold", "relay", "obsolete", "missing", "static", "corrosion",
    "artifact", "drift", "leak", "witness"
]

TOPICS = [
    "missing person notice", "civil defense bulletin", "equipment manual",
    "field report", "weather radar", "numbers station", "railway memo",
    "medical pamphlet", "inspection log", "frequency chart", "site map",
    "photographic plate", "incident summary"
]

ROOMS = [
    ("FOYER", "entry camera / door seam"),
    ("LIVING ROOM", "wide angle / low light"),
    ("KITCHEN", "fluorescent hum / tile reflections"),
    ("BEDROOM", "soft shadows / cloth movement"),
    ("BASEMENT", "low ceiling / damp walls"),
    ("ATTIC", "wood dust / insulation fibers"),
]


def _stable_int(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def make_seed_and_theme(seed_cfg: str):
    if seed_cfg == "AUTO":
        seed_cfg = str(int(time.time()))
    seed = seed_cfg
    rng = random.Random(_stable_int(seed))

    # “brain keyword” that drives everything
    brain = rng.choice(KEYWORDS)
    topic = rng.choice(TOPICS)

    # Cohesion anchor for scraping & on-screen language
    anchor = f"{brain} {topic}"

    # Stable room ordering but still “tape-like”
    rooms = ROOMS.copy()
    rng.shuffle(rooms)

    return seed, {
        "brain": brain,
        "keyword": brain,      # backward compatible
        "topic": topic,
        "anchor": anchor,
        "rooms": rooms,        # list of (room_name, room_note)
        "rng_int": _stable_int(seed),
    }

