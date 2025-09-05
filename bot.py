import asyncio
import os
import time
from typing import Optional

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ChatType

from dictionary import add_word, rm_word, add_sudo, rm_sudo, list_sudo
from game import init_game, build_prompt, validate_word, update_constraints

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN") or ""
OWNER_ID = int(os.getenv("BOT_OWNER_ID") or "0")

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

# chat_id -> game state
games = {}

# ---------- Utility ----------
def is_owner_or_sudo(uid: int, g) -> bool:
    from dictionary import SUDO  # always get fresh
    return uid == OWNER_ID or uid in SUDO

async def send(chat_id, text):
    await bot.send_message(chat_id, text)

# ---------- Dictionary / Admin Commands ----------
@dp.message(F.text.startswith("/addword"))
async def cmd_addword(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply("Usage: <code>/addword word</code>")
    await msg.reply(add_word(parts[1]))

@dp.message(F.text.startswith("/rmword"))
async def cmd_rmword(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply("Usage: <code>/rmword word</code>")
    await msg.reply(rm_word(parts[1], msg.from_user.id, OWNER_ID))

@dp.message(F.text.startswith("/addsudo"))
async def cmd_addsudo(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply("Usage: <code>/addsudo user_id</code>")
    try:
        uid = int(parts[1])
    except ValueError:
        return await msg.reply("Provide numeric user id.")
    await msg.reply(add_sudo(uid, msg.from_user.id, OWNER_ID))

@dp.message(F.text.startswith("/rmsudo"))
async def cmd_rmsudo(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply("Usage: <code>/rmsudo user_id</code>")
    try:
        uid = int(parts[1])
    except ValueError:
        return await msg.reply("Provide numeric user id.")
    await msg.reply(rm_sudo(uid, msg.from_user.id, OWNER_ID))

@dp.message(F.text == "/sudolist")
async def cmd_sudolist(msg: Message):
    await msg.reply(list_sudo(OWNER_ID))

# ---------- Game Commands ----------
@dp.message(F.text == "/startgame")
async def cmd_startgame(msg: Message):
    if msg.chat.type not in {ChatType.SUPERGROUP, ChatType.GROUP}:
        return await msg.reply("This game runs in groups only.")

    if msg.chat.id in games:
        return await msg.reply("A game is already active in this chat.")

    g = init_game(msg.chat.id)
    games[msg.chat.id] = g

    await msg.reply("🎮 Lobby is open! Type <b>/join</b> to enter. Auto-starts in <b>30s</b>.")
    async def auto_start():
        await asyncio.sleep(30)
        g["lobby_open"] = False
        if len(g["lobby_players"]) < 2:
            games.pop(msg.chat.id, None)
            return await send(msg.chat.id, "Not enough players (need at least 2). Game cancelled.")
        g["running"] = True
        g["players"] = [p["id"] for p in g["lobby_players"]]
        g["alive"] = set(g["players"])
        g["scores"] = {uid: {"points": 0} for uid in g["players"]}
        g["turn_index"] = 0
        await send(msg.chat.id, "✅ Match started. No repeats allowed. Last survivor wins.")
        await next_turn(msg.chat.id, g)
    asyncio.create_task(auto_start())

@dp.message(F.text == "/join")
async def cmd_join(msg: Message):
    g = games.get(msg.chat.id)
    if not g or not g["lobby_open"]:
        return
    if any(p["id"] == msg.from_user.id for p in g["lobby_players"]):
        return
    if len(g["lobby_players"]) >= g.get("max_players", 15):
        return await msg.reply(f"Lobby full ({g['max_players']}/{g['max_players']}).")
    username = msg.from_user.username or msg.from_user.first_name or str(msg.from_user.id)
    g["lobby_players"].append({"id": msg.from_user.id, "username": username})
    await msg.reply(f"✅ <b>@{username}</b> joined the lobby.")

@dp.message(F.text == "/leaderboard")
async def cmd_leaderboard(msg: Message):
    g = games.get(msg.chat.id)
    if not g or not g["running"]:
        return await msg.reply("No active game.")
    text = "📊 <b>Leaderboard</b>\n"
    sorted_scores = sorted(g["scores"].items(), key=lambda x: x[1]["points"], reverse=True)
    for rank, (uid, score) in enumerate(sorted_scores, 1):
        user = next((p for p in g["lobby_players"] if p["id"] == uid), {"username": str(uid)})
        text += f"{rank}. @{user['username']} — {score['points']} pts\n"
    await msg.reply(text)

@dp.message(F.text == "/score")
async def cmd_score(msg: Message):
    g = games.get(msg.chat.id)
    if not g or not g["running"]:
        return await msg.reply("No active game.")
    sc = g["scores"].get(msg.from_user.id, {"points": 0})["points"]
    await msg.reply(f"🎯 Your score: <b>{sc}</b> pts")

@dp.message(F.text == "/forcestop")
async def cmd_forcestop(msg: Message):
    g = games.get(msg.chat.id)
    if not g:
        return await msg.reply("No game to stop.")
    if not is_owner_or_sudo(msg.from_user.id, g):
        return await msg.reply("⛔ Only owner/sudo can stop the game.")
    await end_game(msg.chat.id, g, forced=True)

@dp.message(F.text.startswith("/setmaxplayers"))
async def cmd_setmaxplayers(msg: Message):
    g = games.get(msg.chat.id)
    if not g:
        return await msg.reply("No active game in this chat.")
    if not is_owner_or_sudo(msg.from_user.id, g):
        return await msg.reply("⛔ Only owner/sudo can change max players.")

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply("Usage: <code>/setmaxplayers number</code>")
    try:
        num = int(parts[1])
    except ValueError:
        return await msg.reply("Enter a valid number.")

    if num < 2 or num > 50:
        return await msg.reply("Allowed range is 2–50.")

    g["max_players"] = num
    await msg.reply(f"✅ Max players set to {num}.")

# ---------- Turn Engine ----------
async def next_turn(chat_id: int, g):
    if g.get("reminder_task"):
        g["reminder_task"].cancel()
        g["reminder_task"] = None

    update_constraints(g)
    if not g["alive"]:
        return await end_game(chat_id, g)

    start_idx = g["turn_index"]
    while g["players"][g["turn_index"]] not in g["alive"]:
        g["turn_index"] = (g["turn_index"] + 1) % len(g["players"])
        if g["turn_index"] == start_idx:
            return await end_game(chat_id, g)

    uid = g["players"][g["turn_index"]]
    user = next((p for p in g["lobby_players"] if p["id"] == uid), {"id": uid, "username": str(uid)})

    text, meta = build_prompt(g, user)
    deadline = time.time() + g["constraints"]["time"]
    g["current"] = {"uid": uid, "mode": g["mode"], "meta": meta, "deadline": deadline}

    async def reminder():
        try:
            await asyncio.sleep(max(0, g["constraints"]["time"] - 5))
            cur = g.get("current")
            if cur and cur["uid"] == uid and time.time() < cur["deadline"]:
                await send(chat_id, f"⏰ <b>5s left</b> for @{user['username']}!")
        except asyncio.CancelledError:
            pass

    g["reminder_task"] = asyncio.create_task(reminder())
    await send(chat_id, text)

async def end_game(chat_id: int, g, forced: bool = False):
    if g.get("reminder_task"):
        g["reminder_task"].cancel()
        g["reminder_task"] = None

    winner_msg = ""
    if forced:
        if g.get("scores"):
            winner = max(g["scores"], key=lambda x: g["scores"][x]["points"])
            u = next((p for p in g["lobby_players"] if p["id"] == winner), {"username": str(winner)})
            winner_msg = f"🛑 Game stopped.\n🏆 Top: @{u['username']} ({g['scores'][winner]['points']} pts)"
        else:
            winner_msg = "🛑 Game stopped."
    else:
        if g["alive"]:
            winner = list(g["alive"])[0] if len(g["alive"]) == 1 else max(g["scores"], key=lambda x: g["scores"][x]["points"])
            u = next((p for p in g["lobby_players"] if p["id"] == winner), {"username": str(winner)})
            winner_msg = f"🏆 Winner: @{u['username']} — {g['scores'][winner]['points']} pts"
        else:
            winner_msg = "No survivors."
    await send(chat_id, winner_msg)
    games.pop(chat_id, None)

# ---------- Answer Handler ----------
@dp.message()
async def handle_answers(msg: Message):
    if msg.chat.type not in {ChatType.SUPERGROUP, ChatType.GROUP}:
        return
    if not msg.text:
        return

    g = games.get(msg.chat.id)
    if not g or not g.get("running") or not g.get("current"):
        return
    if msg.from_user.id != g["current"]["uid"]:
        return

    if time.time() > g["current"]["deadline"]:
        uid = msg.from_user.id
        username = msg.from_user.username or msg.from_user.first_name or str(uid)
        g["alive"].discard(uid)
        await msg.reply(f"❌ <b>@{username}</b> eliminated (timeout).")
        if len(g["alive"]) <= 1:
            return await end_game(msg.chat.id, g)
        g["turn_index"] = (g["turn_index"] + 1) % len(g["players"])
        return await next_turn(msg.chat.id, g)

    valid, reason = validate_word(g, msg.text, g["current"]["mode"], g["current"]["meta"])
    if not valid:
        return await msg.reply(f"❌ {reason}")

    uid = msg.from_user.id
    g["scores"][uid]["points"] += 10
    g["word_count"] += 1
    g["last_word"] = msg.text.strip().lower()
    g["used_words"].add(g["last_word"])   # Anti-Repeat
    await msg.reply("✅ Accepted. +10 pts")

    g["turn_index"] = (g["turn_index"] + 1) % len(g["players"])
    await next_turn(msg.chat.id, g)

# ---------- Main ----------
async def main():
    await dp.start_polling(bot, allowed_updates=["message"])

if __name__ == "__main__":
    asyncio.run(main())
