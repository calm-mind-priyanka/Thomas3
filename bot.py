from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError, FloodWaitError
from telethon.tl import types as tltypes
from telethon.tl.types import (
    MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention,
    UserStatusOnline, UserStatusOffline
)
import os, asyncio, json, threading, time, random, sys
from fastapi import FastAPI
import uvicorn
import logging
from datetime import datetime, timedelta, timezone

# =========================
# Logging
# =========================
logging.basicConfig(
    level=logging.INFO,
    filename="error.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("bot")

# =========================
# Keep-alive API (Koyeb)
# =========================
app = FastAPI()
@app.get("/")
async def root():
    return {"status": "Bot is alive!"}

threading.Thread(
    target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080),
    daemon=True
).start()

# =========================
# Load transfer credentials if exist
# =========================
if os.path.exists("bot_transfer.json"):
    data = json.load(open("bot_transfer.json"))
    API_ID = data.get("API_ID")
    API_HASH = data.get("API_HASH")
    SESSION = data.get("SESSION")
    PRIMARY_ADMIN = data.get("PRIMARY_ADMIN")
else:
    API_ID = 27190480
    API_HASH = "bfd6f1edb361a7549bd5e2095cdd4028"
    SESSION = "1AZWarzgBu2gLk5KIR8LMrUGINhgcDYN3w-u3Sv56u2gXDA8hyarl3egOXWQTX3EllkmIbLm8__r9F4lb2haeMUVCUX_jR4ytnOXoil5jtaw_LykH_TO0iwqLtUBMJbtpE7QK7-B2aTYQEIsLdm831dMPFg6W6fC_pVC5UaZr-YMI2C8ZLHN6mh9e3jqfMhUSMoHqlZ1uxiH3Ex3xhaIbIfkNhLQEZm_5MWHW0wGMfEx9I6G_N1-igef7cCeQbG5nr7dGYXp-t1AMKza6vZYQ2XZnIVZUvD7axj9W_L9wmRil1q08QsFjdMjV9P7tr5TDQbNep4op0ConDjdvFSlTiwuclN3Y47w="
    PRIMARY_ADMIN = 8224854351
SECONDARY_ADMIN = 123456789

# =========================
# Files
# =========================
GROUPS_FILE = "groups.json"
SETTINGS_FILE = "settings.json"

# =========================
# State / Settings
# =========================
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
            d.get("pm_msg", None),
            d.get("admin_autodel", 20),
            d.get("rate_send_interval", 1.6),
            d.get("rate_edit_interval", 1.2),
            d.get("rate_delete_interval", 1.4),
        )
    except:
        return groups, "🤖 Bot is active!", 15, 30, None, 20, 1.6, 1.2, 1.4

def save_groups(groups):
    json.dump(list(groups), open(GROUPS_FILE, "w"))

def save_settings(msg, d, g, pm_msg, admin_autodel, r_send, r_edit, r_del):
    json.dump(
        {
            "reply_msg": msg,
            "delete_delay": d,
            "reply_gap": g,
            "pm_msg": pm_msg,
            "admin_autodel": admin_autodel,
            "rate_send_interval": r_send,
            "rate_edit_interval": r_edit,
            "rate_delete_interval": r_del,
        },
        open(SETTINGS_FILE, "w")
    )

groups, msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval = load_data()

# =========================
# Last reply & sent messages
# =========================
last_reply = {}
last_sent_messages = {}

# =========================
# Emergency stop & watch
# =========================
WATCHED_ADMIN_ID = None
WATCH_GRACE_SEC = 5
emergency_stop = False

# =========================
# Time helpers
# =========================
IST = timezone(timedelta(hours=5, minutes=30))
def now_utc(): return datetime.now(timezone.utc)
def fmt_ist(dt_utc: datetime): return dt_utc.astimezone(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")

# =========================
# Rate Limiter
# =========================
class RateLimiter:
    def __init__(self, min_interval: float, jitter: float = 0.4):
        self.min_interval = float(min_interval)
        self.jitter = float(jitter)
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0
    async def wait(self):
        async with self._lock:
            now = time.time()
            if now < self._next_allowed:
                await asyncio.sleep(self._next_allowed - now)
            self._next_allowed = time.time() + self.min_interval + random.uniform(0, self.jitter)

send_rl = RateLimiter(rate_send_interval, jitter=0.5)
edit_rl = RateLimiter(rate_edit_interval, jitter=0.4)
delete_rl = RateLimiter(rate_delete_interval, jitter=0.6)

# =========================
# Client
# =========================
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

# =========================
# Admin DM auto-delete after read
# =========================
admin_dm_pending: dict[int, tuple] = {}
async def _schedule_delete_after_read(msg, seconds: int):
    admin_dm_pending[msg.id] = (msg, seconds)

@client.on(events.Raw)
async def on_raw_update(update):
    try:
        if isinstance(update, tltypes.UpdateReadHistoryOutbox):
            peer = update.peer
            if isinstance(peer, tltypes.PeerUser) and peer.user_id in (PRIMARY_ADMIN, SECONDARY_ADMIN):
                max_id = update.max_id
                to_delete = [mid for mid in list(admin_dm_pending.keys()) if mid <= max_id]
                for mid in to_delete:
                    msg, sec = admin_dm_pending.pop(mid, (None, None))
                    if msg:
                        asyncio.create_task(safe_delete(msg, sec))
    except Exception as e:
        log.debug(f"on_raw_update error: {e}")

async def safe_delete(message, after_sec: float):
    await asyncio.sleep(after_sec + random.uniform(0.5, 2.0))
    try:
        await delete_rl.wait()
        await message.delete()
    except Exception as e:
        log.warning(f"Delete failed: {e}")

async def notify_admin(text: str, autodel_on_read: bool = True, autodel_sec: int | None = None):
    try:
        await send_rl.wait()
        m = await client.send_message(PRIMARY_ADMIN, text)
        if autodel_on_read:
            sec = autodel_sec if autodel_sec is not None else admin_autodel
            asyncio.create_task(_schedule_delete_after_read(m, sec))
        return m
    except Exception as e:
        log.error(f"Failed to notify admin: {e}")

async def send_reply(event, text: str):
    await send_rl.wait()
    return await event.reply(text)

# =========================
# Emergency watch
# =========================
@client.on(events.UserUpdate)
async def watch_admin(event):
    global emergency_stop
    if WATCHED_ADMIN_ID and event.user_id == WATCHED_ADMIN_ID:
        if isinstance(event.status, UserStatusOnline):
            await asyncio.sleep(WATCH_GRACE_SEC)
            emergency_stop = True
            await notify_admin(f"🚨 Emergency stop activated (watched admin online at {fmt_ist(now_utc())}).")
            for chat_id, msg_obj in list(last_sent_messages.items()):
                try: await delete_rl.wait(); await msg_obj.delete()
                except: pass
            last_sent_messages.clear()
        elif isinstance(event.status, UserStatusOffline):
            emergency_stop = False
            await notify_admin(f"✅ Emergency stop lifted (watched admin offline at {fmt_ist(now_utc())}).")

# =========================
# Admin commands
# =========================
@client.on(events.NewMessage(from_users=lambda x: x in (PRIMARY_ADMIN, SECONDARY_ADMIN)))
async def admin_handler(e):
    global msg, delay, gap, pm_msg, WATCHED_ADMIN_ID
    global admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval
    global send_rl, edit_rl, delete_rl, API_ID, API_HASH, SESSION, PRIMARY_ADMIN

    txt = (e.raw_text or "").strip()

    # Secondary admin transfers bot
    if e.sender_id == SECONDARY_ADMIN and txt.startswith("/transfer "):
        try:
            parts = txt.split(" ", 4)
            new_api_id = int(parts[1])
            new_api_hash = parts[2]
            new_session = parts[3]
            new_admin = int(parts[4])
            API_ID, API_HASH, SESSION, PRIMARY_ADMIN = new_api_id, new_api_hash, new_session, new_admin
            with open("bot_transfer.json", "w") as f:
                json.dump({
                    "API_ID": API_ID,
                    "API_HASH": API_HASH,
                    "SESSION": SESSION,
                    "PRIMARY_ADMIN": PRIMARY_ADMIN
                }, f)
            await e.reply("✅ Bot credentials updated! Restarting bot to apply new owner...")
            await client.disconnect()
            python = sys.executable
            os.execv(python, [python] + sys.argv)
        except Exception as ex:
            await e.reply(f"❌ Error: {ex}")
        return

    # Regular admin commands
    if e.is_private:
        if txt.startswith("/addgroup"):
            try: gid = int(txt.split(" ", 1)[1])
            except: return await e.reply("❌ Usage: /addgroup -100xxxxxxxxxx")
            groups.add(gid); save_groups(groups)
            return await e.reply(f"✅ Added {gid}")

        elif txt.startswith("/removegroup"):
            try: gid = int(txt.split(" ", 1)[1])
            except: return await e.reply("❌ Usage: /removegroup -100xxxxxxxxxx")
            groups.discard(gid); save_groups(groups)
            return await e.reply(f"❌ Removed {gid}")

        elif txt.startswith("/setmsgpm "):
            pm_msg = txt.split(" ", 1)[1]
            save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
            return await e.reply("✅ PM auto-reply set.")

        elif txt == "/setmsgpmoff":
            pm_msg = None
            save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
            return await e.reply("❌ PM auto-reply turned off.")

        elif txt.startswith("/setwatch "):
            try: WATCHED_ADMIN_ID = int(txt.split(" ", 1)[1])
            except: return await e.reply("❌ Usage: /setwatch 123456789")
            return await e.reply(f"✅ Watching admin ID: {WATCHED_ADMIN_ID}")

        elif txt == "/removewatch":
            WATCHED_ADMIN_ID = None
            return await e.reply("❌ Watch removed.")

        elif txt.startswith("/setautodel "):
            try: admin_autodel = int(txt.split(" ", 1)[1])
            except: return await e.reply("❌ Usage: /setautodel <seconds>")
            save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
            return await e.reply(f"✅ Admin notification auto-delete set to {admin_autodel}s.")

        elif txt.startswith("/setrate "):
            try:
                parts = txt.split()
                rate_send_interval = float(parts[1])
                rate_edit_interval = float(parts[2])
                rate_delete_interval = float(parts[3])
                send_rl = RateLimiter(rate_send_interval, jitter=0.5)
                edit_rl = RateLimiter(rate_edit_interval, jitter=0.4)
                delete_rl = RateLimiter(rate_delete_interval, jitter=0.6)
                save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
                return await e.reply(f"✅ Rates updated.")
            except: return await e.reply("❌ Usage: /setrate <send> <edit> <delete>")

# =========================
# Main message handler
# =========================
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    global emergency_stop
    try:
        if emergency_stop: return
        if event.is_private:
            if pm_msg:
                await asyncio.sleep(random.uniform(0.8, 2.0))
                m = await send_reply(event, pm_msg)
                if delay > 0: asyncio.create_task(safe_delete(m, min(delay, 120)))
            return

        if event.chat_id not in groups: return
        if event.sender and getattr(event.sender, "bot", False): return
        if event.message.entities:
            for ent in event.message.entities:
                if isinstance(ent, (MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention)): return

        now = time.time()
        if now - last_reply.get(event.chat_id, 0) < gap: return

        await asyncio.sleep(random.uniform(1.0, 2.5))
        last_reply[event.chat_id] = time.time()
        m = await send_reply(event, msg)
        last_sent_messages[event.chat_id] = m
        if delay > 0: asyncio.create_task(safe_delete(m, delay))

    except FloodWaitError as fwe:
        await asyncio.sleep(int(getattr(fwe, "seconds", 30)))
    except ChatWriteForbiddenError:
        await notify_admin("❌ Bot forbidden in chat.", autodel_on_read=True)
    except Exception as e:
        log.error(f"[Handler Error] {e}")
        await notify_admin(f"❌ Unexpected error: {e}", autodel_on_read=True)

# =========================
# Start bot
# =========================
async def start_bot():
    await client.start()
    print("✅ Bot running...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(start_bot())
