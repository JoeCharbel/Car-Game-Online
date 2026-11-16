"""
Local high-score storage.

Scores are kept in ``scores.json`` next to this file so they survive
restarts. Writes go through a temp file + replace so a crash mid-write
cannot corrupt the existing list.
"""

import json
import os
import time

SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.json")
MAX_SCORES = 10
MODES = ("single", "online")


def _empty():
    return {mode: [] for mode in MODES}


def _normalize(data):
    """Return a clean {mode: [entries]} dict, tolerating old/broken data."""
    if not isinstance(data, dict):
        return _empty()

    result = _empty()
    for mode in MODES:
        raw_entries = data.get(mode, [])
        if not isinstance(raw_entries, list):
            continue

        entries = []
        for raw in raw_entries:
            if not isinstance(raw, dict):
                continue
            try:
                score = int(raw.get("score", 0))
            except (TypeError, ValueError):
                continue
            name = str(raw.get("name", "Player")).strip()[:15] or "Player"
            entries.append({
                "name": name,
                "score": max(0, score),
                "date": str(raw.get("date", "")),
            })

        entries.sort(key=lambda entry: entry["score"], reverse=True)
        result[mode] = entries[:MAX_SCORES]
    return result


def load_scores():
    """Load all score tables. Never raises; returns empty tables on failure."""
    try:
        with open(SCORE_FILE, "r", encoding="utf-8") as score_file:
            return _normalize(json.load(score_file))
    except (OSError, ValueError):
        return _empty()


def save_scores(data):
    """Persist score tables atomically. Returns True on success."""
    try:
        temp_file = SCORE_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as score_file:
            json.dump(_normalize(data), score_file, indent=2)
            score_file.flush()
            os.fsync(score_file.fileno())
        os.replace(temp_file, SCORE_FILE)
        return True
    except OSError:
        return False


def add_score(mode, name, score):
    """
    Add a result and keep the top MAX_SCORES entries for that mode.

    Returns (rank, entries) where rank is 1-based, or None when the score
    did not make the table.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown score mode: {mode}")

    data = load_scores()
    entry = {
        "name": (str(name).strip() or "Player")[:15],
        "score": max(0, int(score)),
        "date": time.strftime("%Y-%m-%d"),
    }

    entries = data[mode]
    entries.append(entry)
    entries.sort(key=lambda item: item["score"], reverse=True)
    del entries[MAX_SCORES:]
    data[mode] = entries
    save_scores(data)

    rank = next((index + 1 for index, item in enumerate(entries) if item is entry), None)
    return rank, entries


def best_score(mode):
    """Highest saved score for a mode (0 when the table is empty)."""
    entries = load_scores().get(mode, [])
    return entries[0]["score"] if entries else 0


def top_scores(mode, limit=5):
    """Return up to `limit` entries, highest first."""
    return load_scores().get(mode, [])[:limit]
