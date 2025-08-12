from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError, FloodWaitError
from telethon.tl.types import (
    MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention,
    UserStatusOnline, UserStatusOffline
)
import os, asyncio, json, threading, time, sys
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
API_ID = 27190480
API_HASH = "bfd6f1edb361a7549bd5e2095cdd4028"
SESSION = "1AZWarzgBu2gLk5KIR8LMrUGINhgcDYN3w-u3Sv56u2gXDA8hyarl3egOXWQTX3EllkmIbLm8__r9F4lb2haeMUVCUX_jR4ytnOXoil5jtaw_LykH_TO0iwqLtUBMJbtpE7QK7-B2aTYQEIsLdm831dMPFg6W6fC_pVC5UaZr-YMI2C8ZLHN6mh9e3jqfMhUSMoHqlZ1uxiH3Ex3xhaIbIfkNhLQEZm_5MWHW0wGMfEx9I6G_N1-igef7cCeQbG5nr7dGYXp-t1AMKza6vZYQ2XZnIVZUvD7axj9W_L9wmRil1q08QsFjdMjV9P7tr5TDQbNep4op0ConDjdvFSlTiwuclN3Y47w="
ADMIN = 8224854351

# Emergency watch feature
WATCHED_ADMIN_ID = None  # Put the admin's ID here if you want to enable, else keep None
emergency_stop = False
last_sent_messages = {}  # store last sent message per chat

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

# Tracking bot usage for warnings and restart
start_time = time.time()
message_count = 0
warned_admin_about_slow = False
warned_admin_about_flood = False

# Client
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

# Helper: async delete later
async def delete_later(m, sec):
    await asyncio.sleep(sec)
    try:
        await m.delete()
    except:
        pass

# Send admin notification helper
async def notify_admin(text):
    try:
        await client.send_message(ADMIN, text)
    except Exception as e:
        logging.error(f"Failed to notify admin: {e}")

# Message handler for groups and PMs
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    global emergency_stop, message_count, warned_admin_about_slow, warned_admin_about_flood

    try:
        if emergency_stop:
            return

        if event.is_private:
            if pm_msg:
                m = await event.reply(pm_msg)
                asyncio.create_task(delete_later(m, 60))
            return

        if event.chat_id not in groups:
            return
        if event.sender.bot:
            return

        # Skip clickable messages (links, mentions, etc.)
        if event.message.entities:
            for ent in event.message.entities:
                if isinstance(ent, (MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention)):
                    return

        now = time.time()
        if now - last_reply.get(event.chat_id, 0) < gap:
            return
        last_reply[event.chat_id] = now

        # Track message count
        message_count += 1

        # Check if slow warning needed (e.g. after 6 hours or 1000 messages)
        uptime = now - start_time
        if not warned_admin_about_slow and (uptime > 6 * 3600 or message_count > 1000):
            await notify_admin("⚠️ Bot has been running for a long time or processed many messages and may slow down soon. Use /restart to refresh.")
            warned_admin_about_slow = True

        m = await event.reply(msg)
        last_sent_messages[event.chat_id] = m  # store last message
        if delay > 0:
            asyncio.create_task(delete_later(m, delay))

    except FloodWaitError as fwe:
        # Notify admin about flood wait time before stopping
        if not warned_admin_about_flood:
            await notify_admin(f"🚨 FloodWait detected! Sleeping for {fwe.seconds} seconds. Please wait before sending more messages.")
            warned_admin_about_flood = True
        await asyncio.sleep(fwe.seconds)
        warned_admin_about_flood = False

    except ChatWriteForbiddenError:
        pass

    except Exception as e:
        logging.error(f"[Handler Error] {e}")
        await notify_admin(f"❌ Bot encountered an error and might stop: {e}")

# Watch for watched admin online/offline
@client.on(events.UserUpdate)
async def watch_admin(event):
    global emergency_stop
    if WATCHED_ADMIN_ID and event.user_id == WATCHED_ADMIN_ID:
        if isinstance(event.status, UserStatusOnline):
            print("🚨 Watched admin is online! Emergency stop activated.")
            emergency_stop = True
            for chat_id, msg_obj in list(last_sent_messages.items()):
                try:
                    await msg_obj.delete()
                    print(f"Deleted last message in {chat_id}")
                except:
                    pass
            last_sent_messages.clear()
        elif isinstance(event.status, UserStatusOffline):
            print("✅ Watched admin went offline. Resuming bot.")
            emergency_stop = False

# Admin commands only for ADMIN
@client.on(events.NewMessage(from_users=ADMIN))
async def admin_handler(e):
    global msg, delay, gap, pm_msg, WATCHED_ADMIN_ID
    global warned_admin_about_slow, warned_admin_about_flood, message_count, start_time

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

        elif txt.startswith("/setwatch "):
            try:
                WATCHED_ADMIN_ID = int(txt.split(" ", 1)[1])
                return await e.reply(f"✅ Watching admin ID: {WATCHED_ADMIN_ID}")
            except:
                return await e.reply("❌ Usage: /setwatch 123456789")

        elif txt == "/removewatch":
            WATCHED_ADMIN_ID = None
            return await e.reply("❌ Watch removed.")

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
        uptime_sec = time.time() - start_time
        uptime_str = time.strftime("%H:%M:%S", time.gmtime(uptime_sec))
        await e.reply(
            f"Groups: {len(groups)}\nMsg: {msg}\nPM msg: {pm_msg or '❌ Off'}\nDel: {delay}s\nGap: {gap}s\nWatch: {WATCHED_ADMIN_ID or '❌ Off'}\nUptime: {uptime_str}\nMessages processed: {message_count}"
        )

    elif txt == "/ping":
        await e.reply("🏓 Bot is alive!")

    elif txt == "/restart":
        await e.reply("♻️ Restarting bot...")
        await client.disconnect()
        # The hosting platform (like Koyeb) will restart the process automatically

# Start bot
async def start_bot():
    try:
        await client.start()
        print("✅ Bot running...")
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"[Startup Error] {e}")
        await notify_admin(f"❌ Bot failed to start: {e}")

if __name__ == "__main__":
    asyncio.run(start_bot())
