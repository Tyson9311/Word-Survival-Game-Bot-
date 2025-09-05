import random
import time
import json
from pathlib import Path
from typing import Dict, Any, Tuple

from dictionary import WORDS, is_english

# Load categories
CAT_FILE = Path("data/categories.json")
if not CAT_FILE.exists():
    CAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CAT_FILE.write_text(json.dumps({"fruits": ["apple","banana","mango"]}, indent=2))
CATEGORIES: Dict[str, list] = json.loads(CAT_FILE.read_text())

MODES = ["snake", "ladder", "category", "stop"]

MAX_PLAYERS_DEFAULT = 15

def _rand_from(lst):
    return random.choice(lst)

def _rand_letter():
    return random.choice("abcdefghijklmnopqrstuvwxyz")

def init_game(chat_id: int) -> Dict[str, Any]:
    return {
        "chat_id": chat_id,
        "lobby_open": True,
        "lobby_players": [],
        "running": False,
        "players": [],
        "alive": set(),
        "scores": {},
        "turn_index": 0,
        "word_count": 0,
        "last_word": None,
        "mode": None,
        "constraints": {"min_len": 3, "max_len": 10, "time": 15},
        "current": None,
        "reminder_task": None,
        "used_words": set(),         # Anti-Repeat
        "max_players": MAX_PLAYERS_DEFAULT
    }

def update_constraints(game: Dict[str, Any]):
    wc = game["word_count"]
    if wc >= 100:
        game["constraints"] = {"min_len": 10, "max_len": 30, "time": 15}
    elif wc >= 75:
        game["constraints"] = {"min_len": 7, "max_len": 30, "time": 15}
    else:
        game["constraints"] = {"min_len": 3, "max_len": 10, "time": 15}

def build_prompt(game: Dict[str, Any], user: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    mode = _rand_from(MODES)
    game["mode"] = mode
    base = game["last_word"] or _rand_from(WORDS)
    game["last_word"] = base

    if mode == "snake":
        start = base[-1]
        return (f"@{user['username']}, your word must start with <b>{start.upper()}</b> "
                f"(⏳ {game['constraints']['time']}s)"), {"start": start}
    if mode == "ladder":
        return (f"@{user['username']}, change <b>{base.upper()}</b> by exactly <b>one</b> letter "
                f"(⏳ {game['constraints']['time']}s)"), {"base": base}
    if mode == "category":
        cat = _rand_from(list(CATEGORIES.keys()))
        return (f"@{user['username']}, give a word in category <b>{cat.upper()}</b> "
                f"(⏳ {game['constraints']['time']}s)"), {"cat": cat}
    forb = _rand_letter()
    return (f"@{user['username']}, give a valid word <b>without</b> the letter <b>{forb.upper()}</b> "
            f"(⏳ {game['constraints']['time']}s)"), {"f": forb}

def validate_word(game: Dict[str, Any], word: str, mode: str, meta: Dict[str, Any]) -> Tuple[bool, str]:
    if not word:
        return False, "Empty word."
    w = word.strip().lower()
    cl = game["constraints"]

    if not is_english(w):
        return False, "English letters only."
    if not (cl["min_len"] <= len(w) <= cl["max_len"]):
        return False, f"Word length must be {cl['min_len']}–{cl['max_len']}."
    if w in game["used_words"]:
        return False, "Word already used in this game."

    if mode == "snake":
        if not w.startswith(meta["start"]):
            return False, f"Must start with '{meta['start']}'."
    elif mode == "ladder":
        base = meta["base"].lower()
        if len(w) != len(base):
            return False, "Length must match the base word."
        diff = sum(1 for a, b in zip(w, base) if a != b)
        if diff != 1:
            return False, "Change exactly one letter."
    elif mode == "category":
        allowed = CATEGORIES.get(meta["cat"], [])
        if w not in allowed:
            return False, f"Not in category '{meta['cat']}'."
    elif mode == "stop":
        if meta["f"] in w:
            return False, f"Forbidden letter '{meta['f']}' present."
    return True, ""
