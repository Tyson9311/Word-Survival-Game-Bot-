import json
import re
from pathlib import Path

WORDS_FILE = Path("data/words_seed.txt")
SUDO_FILE = Path("sudo.json")

WORDS = WORDS_FILE.read_text().splitlines()
SUDO = json.loads(SUDO_FILE.read_text()) if SUDO_FILE.exists() else []

def save_words():
    WORDS_FILE.write_text("\n".join(sorted(set(WORDS))))

def save_sudo():
    SUDO_FILE.write_text(json.dumps(SUDO, indent=2))

def is_english(word: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z]+", word))

def add_word(word: str) -> str:
    word = word.lower()
    if not is_english(word):
        return "❌ Only English words allowed."
    if word in WORDS:
        return f"⚠️ '{word}' already exists."
    WORDS.append(word)
    save_words()
    return f"✅ '{word}' added to dictionary."

def rm_word(word: str, user_id: int, owner_id: int) -> str:
    if not (user_id in SUDO or user_id == owner_id):
        return "⛔ Only owner/sudo can remove words."
    if word not in WORDS:
        return f"❌ '{word}' not found."
    WORDS.remove(word)
    save_words()
    return f"🗑️ '{word}' removed."

def add_sudo(user_id: int, by_id: int, owner_id: int) -> str:
    if by_id != owner_id:
        return "⛔ Only owner can add sudo."
    if user_id in SUDO:
        return "⚠️ Already sudo."
    SUDO.append(user_id)
    save_sudo()
    return f"✅ {user_id} added to sudo."

def rm_sudo(user_id: int, by_id: int, owner_id: int) -> str:
    if by_id != owner_id:
        return "⛔ Only owner can remove sudo."
    if user_id not in SUDO:
        return "⚠️ Not in sudo."
    SUDO.remove(user_id)
    save_sudo()
    return f"🗑️ {user_id} removed from sudo."

def list_sudo(owner_id: int) -> str:
    text = f"👑 Owner: <code>{owner_id}</code>\n"
    if SUDO:
        text += "🛡️ Sudo:\n" + "\n".join([f"- <code>{uid}</code>" for uid in SUDO])
    else:
        text += "🛡️ No sudo users."
    return text