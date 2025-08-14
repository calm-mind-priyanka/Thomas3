from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError, FloodWaitError, MessageNotModifiedError
from telethon.tl import types as tltypes
from telethon.tl.types import (
    MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention,
    UserStatusOnline, UserStatusOffline
)
import os, asyncio, json, threading, time, random
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
# Config (move to env in prod)
# =========================
API_ID = 25626481
API_HASH = "a9e1d02e77df46371377822273acff31"
SESSION = "1AZWarzgBu5L-DOiMp9XS7TCNoEOydKIHUG4nd9v7lyhJJdoVQAencswU9IGES5H4sQ0GsD1ce2mfb2fmV35cFjUNhm7y4plDFAbASDETdJrllM_v5yBoLDo9F3IC20o9FzLQ-znVzqzJZ-CUfC6siOg8rHghDlkMIgAhbqnesSebrfsoUhfswYzvBNA45ZbFgK-mXfDHACA3YfAKmuwLVkK38UquIcjoBVpQj1xf0nwrAor8EBFcox50M9P6x_wJJbPKWTHnrIhU3OwsjGwjxZ3EP1DNvpoi9DUNLH8bqLYbYm4QBNQpw7ceYdhfTSdo4wYDBiwWXF3lFWBgBgCOYxmHCobuOw4="
ADMIN = 8382954144  # int Telegram user ID

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

# Per-chat last reply timestamp
last_reply = {}
# Track last sent message to possibly delete on emergency stop
last_sent_messages = {}

# Emergency watch feature
WATCHED_ADMIN_ID = None
WATCH_GRACE_SEC = 5  # avoid false triggers
emergency_stop = False

# Tracking
start_time = time.time()
message_count = 0
warned_admin_about_slow = False
warned_admin_about_flood = False

# =========================
# Time helpers (IST 12h)
# =========================
IST = timezone(timedelta(hours=5, minutes=30))

def now_utc():
    return datetime.now(timezone.utc)

def fmt_ist(dt_utc: datetime):
    # 12-hour format with AM/PM and explicit IST label
    return dt_utc.astimezone(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")

def fmt_utc(dt_utc: datetime):
    return dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

def hhmmss(total_seconds: int):
    m, s = divmod(max(0, int(total_seconds)), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

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
# Admin DM auto-delete after *read*
# =========================
# We store DM messages sent to ADMIN and delete them N seconds after Telegram
# tells us the ADMIN has read them (UpdateReadHistoryOutbox).
admin_dm_pending: dict[int, tuple] = {}  # msg_id -> (Message, seconds)

async def _schedule_delete_after_read(msg, seconds: int):
    # Store to be triggered on read
    admin_dm_pending[msg.id] = (msg, seconds)

@client.on(events.Raw)
async def on_raw_update(update):
    # Trigger deletions when ADMIN reads the DM
    try:
        if isinstance(update, tltypes.UpdateReadHistoryOutbox):
            peer = update.peer
            if isinstance(peer, tltypes.PeerUser) and peer.user_id == ADMIN:
                max_id = update.max_id
                to_delete = [mid for mid in list(admin_dm_pending.keys()) if mid <= max_id]
                for mid in to_delete:
                    msg, sec = admin_dm_pending.pop(mid, (None, None))
                    if msg:
                        asyncio.create_task(safe_delete(msg, sec))
    except Exception as e:
        log.debug(f"on_raw_update error: {e}")

# =========================
# Helpers
# =========================
async def safe_delete(message, after_sec: float):
    # Stagger deletions (avoid bursts)
    await asyncio.sleep(after_sec + random.uniform(0.5, 2.0))
    try:
        await delete_rl.wait()
        await message.delete()
    except Exception as e:
        log.warning(f"Delete failed: {e}")

async def notify_admin(text: str, autodel_on_read: bool = True, autodel_sec: int | None = None):
    """Send admin DM; optionally delete N seconds after *admin reads it*."""
    try:
        await send_rl.wait()
        m = await client.send_message(ADMIN, text)
        if autodel_on_read:
            sec = autodel_sec if autodel_sec is not None else admin_autodel
            asyncio.create_task(_schedule_delete_after_read(m, sec))
        return m
    except Exception as e:
        log.error(f"Failed to notify admin: {e}")

async def send_reply(event, text: str):
    await send_rl.wait()
    return await event.reply(text)

# Live countdown editor for FloodWait (IST time + human delta)
async def flood_countdown(seconds: int, header: str = "🚨 Flood wait detected!"):
    """Send a single admin message and edit it to show remaining time (IST)."""
    start = now_utc()
    resume = start + timedelta(seconds=seconds)
    msg = await notify_admin(
        f"{header}\n⏳ Resumes in {hhmmss(seconds)}\n📅 Resume time: {fmt_ist(resume)}",
        autodel_on_read=False
    )
    try:
        remaining = seconds
        # Update once per second, but respect edit rate limit
        while remaining > 0:
            await asyncio.sleep(1)
            remaining -= 1
            try:
                await edit_rl.wait()
                await msg.edit(
                    f"{header}\n⏳ Resumes in {hhmmss(remaining)}\n📅 Resume time: {fmt_ist(resume)}"
                )
            except MessageNotModifiedError:
                pass
            except Exception as e:
                log.debug(f"Countdown edit failed (continuing): {e}")
        await edit_rl.wait()
        await msg.edit(f"✅ Bot resuming now ({fmt_ist(now_utc())})")
        asyncio.create_task(safe_delete(msg, 15))
    except Exception as e:
        log.debug(f"Countdown loop error: {e}")

# =========================
# Main handler
# =========================
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    global emergency_stop, message_count, warned_admin_about_slow, warned_admin_about_flood

    try:
        if emergency_stop:
            return

        # PM auto-reply
        if event.is_private:
            if pm_msg:
                await asyncio.sleep(random.uniform(0.8, 2.0))
                m = await send_reply(event, pm_msg)
                if delay > 0:
                    asyncio.create_task(safe_delete(m, min(delay, 120)))  # cap to 120s in PMs
            return

        # Only act in configured groups
        if event.chat_id not in groups:
            return

        # Ignore other bots
        if event.sender and getattr(event.sender, "bot", False):
            return

        # Skip messages with links/mentions to avoid unwanted triggers
        if event.message.entities:
            for ent in event.message.entities:
                if isinstance(ent, (MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention)):
                    return

        # Per-chat gap control
        now = time.time()
        if now - last_reply.get(event.chat_id, 0) < gap:
            return

        # Human-like reaction time
        await asyncio.sleep(random.uniform(1.0, 2.5))

        # Send reply
        last_reply[event.chat_id] = time.time()
        m = await send_reply(event, msg)
        last_sent_messages[event.chat_id] = m
        message_count += 1

        # Schedule deletion (staggered)
        if delay > 0:
            asyncio.create_task(safe_delete(m, delay))

        # Occasional uptime heads-up
        uptime = time.time() - start_time
        if not warned_admin_about_slow and (uptime > 6 * 3600 or message_count > 1000):
            await notify_admin("⚠️ Bot has high uptime / message count. Consider restart.", autodel_on_read=True)
            warned_admin_about_slow = True

    except FloodWaitError as fwe:
        seconds = int(getattr(fwe, "seconds", 30))
        if not warned_admin_about_flood:
            warned_admin_about_flood = True
            asyncio.create_task(flood_countdown(seconds))
        await asyncio.sleep(seconds)
        warned_admin_about_flood = False
        await notify_admin(f"✅ Bot resumed at {fmt_ist(now_utc())}", autodel_on_read=True)

    except ChatWriteForbiddenError:
        await notify_admin("❌ Bot is forbidden from writing in one or more chats. Check permissions.", autodel_on_read=True)

    except Exception as e:
        log.error(f"[Handler Error] {e}")
        await notify_admin(f"❌ Unexpected error: {e}", autodel_on_read=True)

# =========================
# Watch admin online/offline (with grace)
# =========================
@client.on(events.UserUpdate)
async def watch_admin(event):
    global emergency_stop
    if WATCHED_ADMIN_ID and event.user_id == WATCHED_ADMIN_ID:
        if isinstance(event.status, UserStatusOnline):
            # Grace period to reduce false triggers
            await asyncio.sleep(WATCH_GRACE_SEC)
            emergency_stop = True
            await notify_admin(f"🚨 Emergency stop activated (watched admin online at {fmt_ist(now_utc())}).", autodel_on_read=True)
            # Try to delete our last replies to clean up
            for chat_id, msg_obj in list(last_sent_messages.items()):
                try:
                    await delete_rl.wait()
                    await msg_obj.delete()
                except:
                    pass
            last_sent_messages.clear()
        elif isinstance(event.status, UserStatusOffline):
            emergency_stop = False
            await notify_admin(f"✅ Emergency stop lifted (watched admin offline at {fmt_ist(now_utc())}).", autodel_on_read=True)

# =========================
# Admin commands
# =========================
@client.on(events.NewMessage(from_users=ADMIN))
async def admin_handler(e):
    global msg, delay, gap, pm_msg, WATCHED_ADMIN_ID
    global warned_admin_about_slow, warned_admin_about_flood, message_count, start_time
    global admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval, send_rl, edit_rl, delete_rl

    txt = (e.raw_text or "").strip()

    if e.is_private:
        if txt.startswith("/addgroup"):
            try:
                gid = int(txt.split(" ", 1)[1])
            except:
                return await e.reply("❌ Usage: /addgroup -100xxxxxxxxxx")
            groups.add(gid)
            save_groups(groups)
            return await e.reply(f"✅ Added {gid}")

        elif txt.startswith("/removegroup"):
            try:
                gid = int(txt.split(" ", 1)[1])
            except:
                return await e.reply("❌ Usage: /removegroup -100xxxxxxxxxx")
            groups.discard(gid)
            save_groups(groups)
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
            try:
                WATCHED_ADMIN_ID = int(txt.split(" ", 1)[1])
                return await e.reply(f"✅ Watching admin ID: {WATCHED_ADMIN_ID}")
            except:
                return await e.reply("❌ Usage: /setwatch 123456789")

        elif txt == "/removewatch":
            WATCHED_ADMIN_ID = None
            return await e.reply("❌ Watch removed.")

        elif txt.startswith("/setautodel "):
            try:
                admin_autodel = int(txt.split(" ", 1)[1])
                save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
                return await e.reply(f"✅ Admin notification auto-delete set to {admin_autodel}s.")
            except:
                return await e.reply("❌ Usage: /setautodel <seconds>")

        elif txt.startswith("/setrate "):
            """
            Usage: /setrate <send_interval> <edit_interval> <delete_interval>
            Example: /setrate 1.6 1.2 1.4
            """
            try:
                parts = txt.split()
                rate_send_interval = float(parts[1])
                rate_edit_interval = float(parts[2])
                rate_delete_interval = float(parts[3])
                send_rl = RateLimiter(rate_send_interval, jitter=0.5)
                edit_rl = RateLimiter(rate_edit_interval, jitter=0.4)
                delete_rl = RateLimiter(rate_delete_interval, jitter=0.6)
                save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
                return await e.reply(f"✅ Rates set. send={rate_send_interval}s, edit={rate_edit_interval}s, delete={rate_delete_interval}s")
            except:
                return await e.reply("❌ Usage: /setrate <send_interval> <edit_interval> <delete_interval>")

    # Chat-scope commands (usable in group too)
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
        save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
        return await e.reply("✅ Reply message set.")

    elif txt.startswith("/setdel "):
        try:
            delay = int(txt.split(" ", 1)[1])
            save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
            return await e.reply(f"✅ Delete delay set to {delay}s.")
        except:
            return await e.reply("❌ Usage: /setdel <seconds>")

    elif txt.startswith("/setgap "):
        try:
            gap = int(txt.split(" ", 1)[1])
            save_settings(msg, delay, gap, pm_msg, admin_autodel, rate_send_interval, rate_edit_interval, rate_delete_interval)
            return await e.reply(f"✅ Reply gap set to {gap}s.")
        except:
            return await e.reply("❌ Usage: /setgap <seconds>")

    elif txt == "/status":
        uptime_sec = time.time() - start_time
        uptime_str = time.strftime("%H:%M:%S", time.gmtime(uptime_sec))
        server_time_utc = fmt_utc(now_utc())
        server_time_ist = fmt_ist(now_utc())
        group_info_lines = []
        for gid in groups:
            try:
                chat = await client.get_entity(gid)
                group_info_lines.append(f"{getattr(chat, 'title', 'Unknown')} ({gid})")
            except Exception:
                group_info_lines.append(f"Unknown group ({gid})")
        group_list = "\n".join(group_info_lines) if group_info_lines else "No groups added."
        status_message = (
            f"🤖 Bot Status\n"
            f"Server time: {server_time_utc} / {server_time_ist}\n"
            f"Uptime: {uptime_str}\n"
            f"Messages processed: {message_count}\n\n"
            f"Groups ({len(groups)}):\n{group_list}\n\n"
            f"Reply message: {msg}\n"
            f"PM auto-reply: {pm_msg or '❌ Off'}\n"
            f"Delete delay: {delay}s | Reply gap: {gap}s\n"
            f"Watch admin: {WATCHED_ADMIN_ID or '❌ Off'}\n"
            f"Rate (send/edit/delete): {rate_send_interval}/{rate_edit_interval}/{rate_delete_interval}s\n"
            f"Admin notify autodelete-after-read: {admin_autodel}s"
        )
        return await e.reply(status_message)

    elif txt == "/ping":
        return await e.reply("🏓 Bot is alive!")

    elif txt == "/restart":
        await e.reply("♻️ Restarting bot...")
        await client.disconnect()

# =========================
# Start bot
# =========================
async def start_bot():
    await client.start()
    print("✅ Bot running...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(start_bot())
