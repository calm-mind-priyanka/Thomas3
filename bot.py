from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.custom import Button
import os, asyncio, json, threading, time
from fastapi import FastAPI
import uvicorn

app = FastAPI()
@app.get("/")
async def root():
    return {"status": "Bot is alive!"}
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

API_ID = 23739953
API_HASH = "cf389d498c77dd79d877e33a6f7bc03f"
SESSION = "1BVtsOJ..."  # your session
ADMINS = [7229962808]
GROUPS_FILE, SETTINGS_FILE, STRIKES_FILE = "groups.json", "settings.json", "strikes.json"

AUTO_REPLY_MSG = "🏷️ Your Files are ready now\n📂 540p | 720p | 1080p\n📌 Download & Watch|https://t.me/+bwi-Oeeg11g2ZmI1"

def load_data():
    try: groups = set(json.load(open(GROUPS_FILE)))
    except: groups = set()
    try:
        data = json.load(open(SETTINGS_FILE))
        reply_msg = data.get("reply_msg", AUTO_REPLY_MSG)
        delete_delay = data.get("delete_delay", 15)
        reply_gap = data.get("reply_gap", 30)
        delete_all_enabled = data.get("delete_all_enabled", False)
    except:
        reply_msg, delete_delay, reply_gap, delete_all_enabled = AUTO_REPLY_MSG, 15, 30, False
    try: strikes = json.load(open(STRIKES_FILE))
    except: strikes = {}
    return groups, reply_msg, delete_delay, reply_gap, delete_all_enabled, strikes

def save_all():
    json.dump(list(TARGET_GROUPS), open(GROUPS_FILE, "w"))
    json.dump({
        "reply_msg": AUTO_REPLY_MSG,
        "delete_delay": DELETE_DELAY,
        "reply_gap": REPLY_GAP,
        "delete_all_enabled": DELETE_ALL_ENABLED
    }, open(SETTINGS_FILE, "w"))
    json.dump(STRIKES, open(STRIKES_FILE, "w"))

TARGET_GROUPS, AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, DELETE_ALL_ENABLED, STRIKES = load_data()
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
last_reply_time = {}

PROMOTION_TRIGGERS = [
    "dm me", "msg me", "movie mere paas", "join my group", "telegram.me/",
    "check bio", "promotion", "send message", "insta", "bio me"
]

FUNNY_WARNINGS = [
    "😅 Oye bro! Group mein kisi ko reply mat karo. Aisa lagta hai date fix kar rahe ho! 🤭",
    "😁 Bhai bhai bhai... reply nahi karna allowed! Warna log samjhenge tum admin ho 🤫",
    "🤣 Kya yeh tumhare phupa ka ladka/ladki hai jo reply kar rahe ho?",
    "😜 Shadi pakki samjhe kya? Public mein romance band karo!"
]

async def handle_strike(chat_id, user_id, event):
    key = f"{chat_id}_{user_id}"
    STRIKES[key] = STRIKES.get(key, 0) + 1
    save_all()
    level = STRIKES[key]
    if level == 1:
        msg = await event.reply("⚠️ *Warning!* Ye group free hai, apna dhanda bahar karo!")
        await asyncio.sleep(7)
        await msg.delete()
    elif level == 2:
        await client.edit_permissions(chat_id, user_id, send_messages=False)
        m = await event.reply("🔇 Mute laga diya bhai 5 min ke liye!")
        await asyncio.sleep(300)
        await client.edit_permissions(chat_id, user_id, send_messages=True)
        await asyncio.sleep(7)
        await m.delete()
    elif level == 3:
        await client.edit_permissions(chat_id, user_id, send_messages=False)
        m = await event.reply("🔕 24 ghante ke liye mute! Akl thikane aayegi.")
        await asyncio.sleep(86400)
        await client.edit_permissions(chat_id, user_id, send_messages=True)
        await asyncio.sleep(7)
        await m.delete()
    elif level >= 4:
        await client.kick_participant(chat_id, user_id)
        m = await event.reply("🔨 Banned! Promotion karna allowed nahi!")
        await asyncio.sleep(7)
        await m.delete()

@client.on(events.NewMessage)
async def message_handler(event):
    try:
        if not event.is_group: return
        me = await client.get_me()
        my_perms = await client.get_permissions(event.chat_id, me.id)
        if not my_perms.is_admin or not my_perms.delete_messages: return
        sender = await event.get_sender()
        if sender.bot: return
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.sender_id != me.id:
                sender_perms = await client.get_permissions(event.chat_id, sender.id)
                if sender_perms and not sender_perms.is_admin:
                    text = event.text.lower()
                    if any(p in text for p in PROMOTION_TRIGGERS):
                        await event.delete()
                        await handle_strike(event.chat_id, sender.id, event)
                    else:
                        await event.delete()
                        funny = FUNNY_WARNINGS[hash(event.sender_id) % len(FUNNY_WARNINGS)]
                        msg = await event.respond(funny)
                        await asyncio.sleep(7)
                        await msg.delete()
        if DELETE_ALL_ENABLED:
            await asyncio.sleep(1)
            await event.delete()
    except Exception as e:
        print(f"[!] Handler error: {e}")

@client.on(events.NewMessage)
async def auto_reply_handler(event):
    try:
        sender = await event.get_sender()
        if (
            event.chat_id in TARGET_GROUPS and
            event.sender_id != (await client.get_me()).id and
            not getattr(sender, 'bot', False)
        ):
            now = time.time()
            if now - last_reply_time.get(event.chat_id, 0) < REPLY_GAP:
                return
            last_reply_time[event.chat_id] = now
            if "|" in AUTO_REPLY_MSG:
                msg_text, button_link = AUTO_REPLY_MSG.split("|", 1)
                btn = [Button.url("📂 CLICK HERE FOR FILE 📂", button_link.strip())]
                sent = await event.respond(msg_text.strip(), buttons=btn)
            else:
                sent = await event.reply(AUTO_REPLY_MSG)
            if DELETE_DELAY > 0:
                await asyncio.sleep(DELETE_DELAY)
                await sent.delete()
    except Exception as e:
        print(f"[!] Auto-reply error: {e}")

@client.on(events.NewMessage(pattern="/add"))
async def cmd_add(event):
    if event.sender_id in ADMINS:
        try:
            gid = int(event.text.split(" ", 1)[1])
            TARGET_GROUPS.add(gid)
            save_all()
            await event.reply(f"✅ Group added: `{gid}`")
        except: await event.reply("❌ Use: `/add <group_id>`")

@client.on(events.NewMessage(pattern="/remove"))
async def cmd_remove(event):
    if event.sender_id in ADMINS:
        try:
            gid = int(event.text.split(" ", 1)[1])
            TARGET_GROUPS.discard(gid)
            save_all()
            await event.reply(f"❎ Removed: `{gid}`")
        except: await event.reply("❌ Use: `/remove <group_id>`")

@client.on(events.NewMessage(pattern="/setmsg"))
async def cmd_setmsg(event):
    if event.sender_id in ADMINS:
        try:
            global AUTO_REPLY_MSG
            AUTO_REPLY_MSG = event.text.split(" ", 1)[1]
            save_all()
            await event.reply("✅ Custom button message set!")
        except: await event.reply("❌ Use: `/setmsg Text|https://link`")

@client.on(events.NewMessage(pattern="/delmsg"))
async def cmd_delmsg(event):
    if event.sender_id in ADMINS:
        global AUTO_REPLY_MSG
        AUTO_REPLY_MSG = ""
        save_all()
        await event.reply("🗑️ Auto reply message cleared.")

@client.on(events.NewMessage(pattern="/setdel"))
async def cmd_setdel(event):
    if event.sender_id in ADMINS:
        try:
            global DELETE_DELAY
            DELETE_DELAY = int(event.text.split(" ", 1)[1])
            save_all()
            await event.reply(f"🕒 Delete delay set: {DELETE_DELAY}s")
        except: await event.reply("❌ Use: `/setdel <seconds>`")

@client.on(events.NewMessage(pattern="/setgap"))
async def cmd_setgap(event):
    if event.sender_id in ADMINS:
        try:
            global REPLY_GAP
            REPLY_GAP = int(event.text.split(" ", 1)[1])
            save_all()
            await event.reply(f"⏳ Reply gap set: {REPLY_GAP}s")
        except: await event.reply("❌ Use: `/setgap <seconds>`")

@client.on(events.NewMessage(pattern="/deleteall on"))
async def enable_delete_all(event):
    if event.sender_id in ADMINS:
        global DELETE_ALL_ENABLED
        DELETE_ALL_ENABLED = True
        save_all()
        await event.reply("🧹 Now deleting all messages in 1 sec!")

@client.on(events.NewMessage(pattern="/deleteall off"))
async def disable_delete_all(event):
    if event.sender_id in ADMINS:
        global DELETE_ALL_ENABLED
        DELETE_ALL_ENABLED = False
        save_all()
        await event.reply("🚫 Stopped deleting all messages.")

@client.on(events.NewMessage(pattern="/id"))
async def id_cmd(event):
    if event.is_group:
        chat = await event.get_chat()
        await event.reply(f"👥 {chat.title}\n📢 ID: `{event.chat_id}`\n👤 Your ID: `{event.sender_id}`")
    else:
        await event.reply(f"👤 Your ID: `{event.sender_id}`")

async def main():
    print("✅ Bot running")
    await client.run_until_disconnected()

client.start()
client.loop.run_until_complete(main())
