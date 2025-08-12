from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError
from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention
import os, asyncio, json, threading, time
from fastapi import FastAPI
import uvicorn
import logging

# Logging
logging.basicConfig(level=logging.INFO, filename="error.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Keep-alive API (Koyeb)
app = FastAPI()
@app.get("/")
async def root():
    return {"status": "Bot is alive!"}
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

# Config
API_ID = 27611770
API_HASH = "6950f9a1b53b3453e745bc893b28e54d"
SESSION = "1BVtsOJwBu8SVdXduJm6biZuzJ2xhf3CS11q6VMAwKFOVWjYb6nGpc2CG5CCCVYXOzH65QRrp-KDenlBJTxsRIZsb182eaRaFd_bhN38BCCl8w5FNzfBADTdS_-coGiKBtnnQnvgun_B-d53MoWDn2YgeK2KYg7UGs5rXnqgVGMo9MznnlDm1UW0_M4nyreud8O2hEXcfy5h3TDUCGMo2axNXPZzsxPHIHyVDRdcNb5YcbDiVTC8vgyibhHoPyIQU5j2iS0tGrp9P-NHFgbRM3tKvC3KePP_jkxQWwbdMTcGD-NwGRLPi5HuYdpsGPMm5U2iiceX9tvqcvh2TokjsErSsf_tplts="
ADMIN = 2056329003

GROUPS_FILE = "groups.json"
SETTINGS_FILE = "settings.json"

# Load/save
def load_data():
    try:
        groups = set(json.load(open(GROUPS_FILE)))
    except:
        groups = set()
    try:
        d = json.load(open(SETTINGS_FILE))
        return (
            groups,
            d.get("reply_msg", "🤖 Bot is active!"),
            d.get("delete_delay", 15),
            d.get("reply_gap", 30),
            d.get("pm_msg", None)
        )
    except:
        return groups, "🤖 Bot is active!", 15, 30, None

def save_groups(groups):
    json.dump(list(groups), open(GROUPS_FILE, "w"))

def save_settings(msg, d, g, pm_msg):
    json.dump({"reply_msg": msg, "delete_delay": d, "reply_gap": g, "pm_msg": pm_msg}, open(SETTINGS_FILE, "w"))

# Initial
groups, msg, delay, gap, pm_msg = load_data()
last_reply = {}

# Client
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

# Helper: async delete later
async def delete_later(m, sec):
    await asyncio.sleep(sec)
    try:
        await m.delete()
    except:
        pass

# Message handler for groups
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    try:
        if event.is_private:
            if pm_msg:
                m = await event.reply(pm_msg)
                asyncio.create_task(delete_later(m, 60))
            return

        # Only reply in allowed groups
        if event.chat_id not in groups:
            return
        if event.sender.bot:
            return

        # Skip clickable messages (links, mentions, etc.)
        if event.message.entities:
            for ent in event.message.entities:
                if isinstance(ent, (MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention)):
                    return  # Ignore message completely

        now = time.time()
        if now - last_reply.get(event.chat_id, 0) < gap:
            return
        last_reply[event.chat_id] = now

        m = await event.reply(msg)
        if delay > 0:
            asyncio.create_task(delete_later(m, delay))

    except ChatWriteForbiddenError:
        pass
    except Exception as e:
        logging.error(f"[Handler Error] {e}")

# Admin commands only for ADMIN
@client.on(events.NewMessage(from_users=ADMIN))
async def admin_handler(e):
    global msg, delay, gap, pm_msg
    txt = e.raw_text.strip()

    if e.is_private:
        if txt.startswith("/addgroup"):
            try:
                gid = int(txt.split(" ", 1)[1])
            except:
                return await e.reply("❌ Usage: /addgroup -100xxxx")
            groups.add(gid)
            save_groups(groups)
            return await e.reply(f"✅ Added {gid}")

        elif txt.startswith("/removegroup"):
            try:
                gid = int(txt.split(" ", 1)[1])
            except:
                return await e.reply("❌ Usage: /removegroup -100xxxx")
            groups.discard(gid)
            save_groups(groups)
            return await e.reply(f"❌ Removed {gid}")

        elif txt.startswith("/setmsgpm "):
            pm_msg = txt.split(" ", 1)[1]
            save_settings(msg, delay, gap, pm_msg)
            return await e.reply("✅ PM auto-reply set.")

        elif txt == "/setmsgpmoff":
            pm_msg = None
            save_settings(msg, delay, gap, pm_msg)
            return await e.reply("❌ PM auto-reply turned off.")

    if txt == "/add":
        groups.add(e.chat_id)
        save_groups(groups)
        return await e.reply("✅ Group added.")

    elif txt == "/remove":
        groups.discard(e.chat_id)
        save_groups(groups)
        return await e.reply("❌ Group removed.")

    elif txt.startswith("/setmsg "):
        msg = txt.split(" ", 1)[1]
        save_settings(msg, delay, gap, pm_msg)
        await e.reply("✅ Message set")

    elif txt.startswith("/setdel "):
        delay = int(txt.split(" ", 1)[1])
        save_settings(msg, delay, gap, pm_msg)
        await e.reply("✅ Delete delay set")

    elif txt.startswith("/setgap "):
        gap = int(txt.split(" ", 1)[1])
        save_settings(msg, delay, gap, pm_msg)
        await e.reply("✅ Gap set")

    elif txt == "/status":
        await e.reply(f"Groups: {len(groups)}\nMsg: {msg}\nPM msg: {pm_msg or '❌ Off'}\nDel: {delay}s\nGap: {gap}s")

    elif txt == "/ping":
        await e.reply("🏓 Bot is alive!")

# Start bot
async def start_bot():
    try:
        await client.start()
        print("✅ Bot running...")
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"[Startup Error] {e}")

asyncio.get_event_loop().run_until_complete(start_bot())
