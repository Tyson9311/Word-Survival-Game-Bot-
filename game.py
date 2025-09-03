import random
import re
import time
from dictionary import WORDS, is_english
from pathlib import Path
import json

CATEGORIES = json.loads(Path("data/categories.json").read_text())

def random_from(lst): return random.choice(lst)
def random_letter(): return random.choice("abcdefghijklmnopqrstuvwxyz")
def clamp(n, mn, mx): return max(mn, min(mx, n))

def init_game(chat_id: int):
    return {
        "lobby_open": True,
        "lobby_players": [],  # {id, username}
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
        "start_time": None,
    }

def update_constraints(game):
    wc = game["word_count"]
    if wc >= 100:
        game["constraints"] = {"min_len": 10, "max_len": 30, "time": 10}
    elif wc >= 75:
        game["constraints"] = {"min_len": 7, "max_len": 30, "time": 15}
    else:
        game["constraints"] = {"min_len": 3, "max_len": 10, "time": 15}

MODES = ["snake","ladder","category","stop"]

def build_prompt(game, user):
    mode = random_from(MODES)
    game["mode"] = mode
    last = game["last_word"] or random_from(WORDS)
    game["last_word"] = last

    if mode == "snake":
        start = last[-1]
        return f"@{user['username']}, word must start with '{start.upper()}'", {"start": start}
    elif mode == "ladder":
        return f"@{user['username']}, change '{last.upper()}' by ONE letter", {"base": last}
    elif mode == "category":
        cat = random_from(list(CATEGORIES.keys()))
        return f"@{user['username']}, word in category '{cat.upper()}'", {"cat": cat}
    elif mode == "stop":
        f = random_letter()
        return f"@{user['username']}, word WITHOUT '{f.upper()}'", {"f": f}

def validate_word(game, word, mode, meta):
    word = word.lower()
    cl = game["constraints"]
    if not is_english(word):
        return False,"English only"
    if len(word)<cl["min_len"] or len(word)>cl["max_len"]:
        return False,f"Length {cl['min_len']}-{cl['max_len']} required"

    if mode=="snake" and not word.startswith(meta["start"]): return False,f"Must start with '{meta['start']}'"
    if mode=="ladder":
        base=meta["base"].lower()
        if len(word)!=len(base): return False,"Length mismatch"
        diff=sum(1 for a,b in zip(word,base) if a!=b)
        if diff!=1: return False,"Must change 1 letter"
    if mode=="category" and word not in CATEGORIES.get(meta["cat"],[]): return False,"Not in category"
    if mode=="stop" and meta["f"] in word: return False,f"Forbidden '{meta['f']}'"
    return True,""