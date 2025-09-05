import json
import re
from pathlib import Path
from typing import List

WORDS_FILE = Path("data/words_seed.txt")
SUDO_FILE = Path("sudo.json")

# Ensure words file
if not WORDS_FILE.exists():
    WORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORDS_FILE.write_text("apple\nbanana\norange\n")

WORDS: List[str] = [w.strip().lower() for w in WORDS_FILE.read_text().splitlines() if w.strip()]

# Ensure sudo file
if not SUDO_FILE.exists():
    SUDO_FILE.write_text("[]")
SUDO = json.loads(SUDO_FILE.read_text())

def _save_words():
    WORDS_FILE.write_text("\n".join(sorted(set(WORDS))))

def _save_sudo():
    SUDO_FILE.write_text(json.dumps(sorted(set(SUDO)), indent=2))

def is_english(word: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z]+", word or ""))

def add_word(word: str) -> str:
    word = (word or "").lower().strip()
    if not is_english(word):
        return "❌ Only English letters allowed."
    if word in WORDS:
        return f"⚠️ '{word}' already exists."
    WORDS.append(word)
    _save_words()
    return f"✅ '{word}' added."

def rm_word(word: str, user_id: int, owner_id: int) -> str:
    word = (word or "").lower().strip()
    if not (user_id == owner_id or user_id in SUDO):
        return "⛔ Only owner/sudo can remove words."
    if word not in WORDS:
        return f"❌ '{word}' not found."
    WORDS.remove(word)
    _save_words()
    return f"🗑️ '{word}' removed."

def add_sudo(user_id: int, by_id: int, owner_id: int) -> str:
    if by_id != owner_id:
        return "⛔ Only owner can add sudo."
    if user_id in SUDO:
        return "⚠️ Already sudo."
    SUDO.append(user_id)
    _save_sudo()
    return f"✅ {user_id} added to sudo."

def rm_sudo(user_id: int, by_id: int, owner_id: int) -> str:
    if by_id != owner_id:
        return "⛔ Only owner can remove sudo."
    if user_id not in SUDO:
        return "⚠️ Not in sudo."
    SUDO.remove(user_id)
    _save_sudo()
    return f"🗑️ {user_id} removed from sudo."

def list_sudo(owner_id: int) -> str:
    text = f"👑 Owner: <code>{owner_id}</code>\n"
    if SUDO:
        text += "🛡️ Sudo:\n" + "\n".join(f"- <code>{uid}</code>" for uid in sorted(SUDO))
    else:
        text += "🛡️ No sudo users."
    return text
