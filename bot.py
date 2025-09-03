import asyncio
import os
import time
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

from dictionary import add_word, rm_word, add_sudo, rm_sudo, list_sudo, WORDS, SUDO
from game import init_game, build_prompt, validate_word, update_constraints

# Load env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("BOT_OWNER_ID","0"))

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

games = {}

# ---- Dictionary Commands ----
@dp.message(F.text.startswith("/addword"))
async def cmd_addword(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts)<2: return await msg.reply("Usage: /addword <word>")
    await msg.reply(add_word(parts[1]))

@dp.message(F.text.startswith("/rmword"))
async def cmd_rmword(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts)<2: return await msg.reply("Usage: /rmword <word>")
    await msg.reply(rm_word(parts[1], msg.from_user.id, OWNER_ID))

@dp.message(F.text.startswith("/addsudo"))
async def cmd_addsudo(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts)<2: return await msg.reply("Usage: /addsudo <id>")
    await msg.reply(add_sudo(int(parts[1]), msg.from_user.id, OWNER_ID))

@dp.message(F.text.startswith("/rmsudo"))
async def cmd_rmsudo(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts)<2: return await msg.reply("Usage: /rmsudo <id>")
    await msg.reply(rm_sudo(int(parts[1]), msg.from_user.id, OWNER_ID))

@dp.message(F.text=="/sudolist")
async def cmd_sudolist(msg: Message):
    await msg.reply(list_sudo(OWNER_ID))

# ---- Game Commands ----
@dp.message(F.text=="/startgame")
async def cmd_startgame(msg: Message):
    if msg.chat.id in games: return await msg.reply("Game already running.")
    g=init_game(msg.chat.id)
    games[msg.chat.id]=g
    await msg.reply("🎮 Lobby open! /join to enter (30s)")
    await asyncio.sleep(30)
    g["lobby_open"]=False
    if len(g["lobby_players"])<2:
        games.pop(msg.chat.id)
        return await msg.reply("Not enough players.")
    g["running"]=True
    g["players"]=[p["id"] for p in g["lobby_players"]]
    g["alive"]=set(g["players"])
    g["scores"]={uid:{"points":0,"streak":0} for uid in g["players"]}
    g["turn_index"]=0
    await next_turn(msg,g)

@dp.message(F.text=="/join")
async def cmd_join(msg: Message):
    g=games.get(msg.chat.id)
    if not g or not g["lobby_open"]: return
    if any(p["id"]==msg.from_user.id for p in g["lobby_players"]): return
    if len(g["lobby_players"])>=15: return await msg.reply("Lobby full")
    g["lobby_players"].append({"id":msg.from_user.id,"username":msg.from_user.username or msg.from_user.first_name})
    await msg.reply(f"✅ {msg.from_user.username} joined")

async def next_turn(msg,g):
    update_constraints(g)
    uid=g["players"][g["turn_index"]]
    while uid not in g["alive"]:
        g["turn_index"]=(g["turn_index"]+1)%len(g["players"])
        uid=g["players"][g["turn_index"]]
    user=next(p for p in g["lobby_players"] if p["id"]==uid)
    text,meta=build_prompt(g,user)
    g["current"]={"uid":uid,"meta":meta,"mode":g["mode"],"deadline":time.time()+g["constraints"]["time"]}
    await msg.reply(text)

@dp.message()
async def answers(msg: Message):
    g=games.get(msg.chat.id)
    if not g or not g["running"] or not g["current"]: return
    if msg.from_user.id!=g["current"]["uid"]: return
    if time.time()>g["current"]["deadline"]:
        g["alive"].remove(msg.from_user.id)
        await msg.reply(f"❌ @{msg.from_user.username} eliminated")
        if len(g["alive"])<=1: return await end_game(msg,g)
        g["turn_index"]=(g["turn_index"]+1)%len(g["players"])
        return await next_turn(msg,g)
    valid,reason=validate_word(g,msg.text,g["current"]["mode"],g["current"]["meta"])
    if not valid: return await msg.reply(f"❌ {reason}")
    g["scores"][msg.from_user.id]["points"]+=10
    g["word_count"]+=1
    await msg.reply("✅ Accepted +10 pts")
    g["turn_index"]=(g["turn_index"]+1)%len(g["players"])
    await next_turn(msg,g)

async def end_game(msg,g):
    winner=list(g["alive"])[0] if g["alive"] else max(g["scores"],key=lambda x:g["scores"][x]["points"])
    winuser=next(p for p in g["lobby_players"] if p["id"]==winner)
    await msg.reply(f"🏆 Winner: @{winuser['username']}")
    games.pop(msg.chat.id,None)

# ---- Main ----
async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())