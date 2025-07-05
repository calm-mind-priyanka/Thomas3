from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio, json, time, os, threading
from fastapi import FastAPI
import uvicorn

API_ID = 23739953
API_HASH = "cf389d498c77dd79d877e33a6f7bc03f"
SESSION = "1BVtsOJwBuzQs91-vpRA6BdUyhXKJS_s5uLvo_k5fvt6DO3RfFDA6LwSTL1TKKqfXHUwwUy3LiDt6DM5Q1SBP4sSvv_dT2pLiOD5-PU7rfTsqcw8vNqm5igK3XTx-V4DUL0fFN1C1YYM1BdkuhIeSR8yuo5aVTL4xyRQ6emmRNsyJpn9W5Y9GTOptJLYn8z0WVLMaPrm21NmbfbXjSQoaluc8DJ0OzrV7-w0-2l524Fsmh-nlu75B2f8z56OE13hyCgFNnjzGGSMl8MwSIKERxpZQuDqZXWO4M7YOolJ757EuygcaH_6CUdvIRcDep-4JrUyMunNQTmEkXRtDnFjtXIyvP39VWuw="
ADMINS = [7229962808]

SETTINGS_FILE = "group_settings.json"
STRIKES_FILE = "strikes.json"

app = FastAPI()
@app.get("/")
async def root(): return {"status": "Bot is alive!"}
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
GROUP_SETTINGS = {}
STRIKES = {}
last_reply_time = {}

if os.path.exists(SETTINGS_FILE): GROUP_SETTINGS = json.load(open(SETTINGS_FILE))
if os.path.exists(STRIKES_FILE): STRIKES = json.load(open(STRIKES_FILE))

def save_settings(): json.dump(GROUP_SETTINGS, open(SETTINGS_FILE, "w"))
def save_strikes(): json.dump(STRIKES, open(STRIKES_FILE, "w"))

PROMOTION_TRIGGERS = ["dm me", "msg me", "pm me", "text me", "inbox me", "ping me",
"join my group", "join group", "telegram.me/", "t.me/", "promotion", "promote", "group link", "channel link", "visit channel",
"bio me", "check bio", "link in bio", "click bio", "see bio", "insta", "instagram", "follow me", "youtube", "yt", "shorts",
"mere paas movie", "movie mere pass", "mere paas hai", "mere paas", "film mere paas", "movie link", "send link", "link lelo",
"group join karo", "add me", "movie in dm", "dm for movie", "group ka link", "join fast", "join now", "link de diya",
"de dia link", "movie ke liye dm", "telegram join", "telegram group", "new channel", "channel join", "connect with me", 
"promotion only", "chat with me"]

FUNNY_WARNINGS = [
    "🤣 Bhai, yahan reply allowed nahi!",
    "😜 Public mein reply mat kar!",
    "😁 Reply karna mana hai boss!",
    "⚠️ Apna dhandha kahin aur chala!",
    "🚫 Yahan promotion allowed nahi. Last warning!"
]

@client.on(events.NewMessage(pattern="/set"))
async def handle_set(event):
    if event.sender_id in ADMINS and event.reply_to_msg_id:
        reply = await event.get_reply_message()
        if "|" in reply.text:
            gid = str(event.chat_id)
            GROUP_SETTINGS.setdefault(gid, {})["msg"] = reply.text
            save_settings()
            await event.reply("✅ Auto message set.")

@client.on(events.NewMessage(pattern="/setdel"))
async def handle_del(event):
    try:
        if event.sender_id in ADMINS:
            parts = event.text.split()
            GROUP_SETTINGS.setdefault(str(event.chat_id), {})["delay"] = int(parts[1])
            save_settings()
            await event.reply("✅ Delete delay set.")
    except: await event.reply("❌ Format: /setdel <seconds>")

@client.on(events.NewMessage(pattern="/setgap"))
async def handle_gap(event):
    try:
        if event.sender_id in ADMINS:
            parts = event.text.split()
            GROUP_SETTINGS.setdefault(str(event.chat_id), {})["gap"] = int(parts[1])
            save_settings()
            await event.reply("✅ Reply gap set.")
    except: await event.reply("❌ Format: /setgap <seconds>")

@client.on(events.NewMessage(pattern="/autodel on"))
async def enable_autodel(event):
    if event.sender_id in ADMINS:
        GROUP_SETTINGS.setdefault(str(event.chat_id), {})["autodel_members_only"] = True
        save_settings()
        await event.reply("🧽 Auto delete for members: ON")

@client.on(events.NewMessage(pattern="/autodel off"))
async def disable_autodel(event):
    if event.sender_id in ADMINS:
        GROUP_SETTINGS.setdefault(str(event.chat_id), {})["autodel_members_only"] = False
        save_settings()
        await event.reply("🧽 Auto delete for members: OFF")

@client.on(events.NewMessage)
async def all_handler(event):
    if not event.is_group: return
    gid = str(event.chat_id)
    sender = await event.get_sender()
    me = await client.get_me()
    my_perms = await client.get_permissions(event.chat_id, me.id)
    if not my_perms.is_admin or sender.bot: return

    # Auto-delete non-admin messages
    if GROUP_SETTINGS.get(gid, {}).get("autodel_members_only") and sender.id not in ADMINS:
        await event.delete(); return

    # Promotion check
    if event.is_reply:
        reply = await event.get_reply_message()
        if reply.sender_id != me.id and sender.id not in ADMINS:
            text = event.text.lower()
            if any(x in text for x in PROMOTION_TRIGGERS):
                key = f"{gid}_{sender.id}"
                STRIKES[key] = STRIKES.get(key, 0) + 1
                lvl = STRIKES[key]
                save_strikes()
                await event.delete()
                if lvl == 1:
                    msg = await event.reply("⚠️ Apna dhandha kahin aur chala!")
                    await asyncio.sleep(7); await msg.delete()
                elif lvl == 2:
                    await client.edit_permissions(event.chat_id, sender.id, send_messages=False)
                    msg = await event.reply("🔇 Mute laga 5 minute ke liye!")
                    await asyncio.sleep(300)
                    await client.edit_permissions(event.chat_id, sender.id, send_messages=True)
                    await asyncio.sleep(7); await msg.delete()
                elif lvl == 3:
                    await client.edit_permissions(event.chat_id, sender.id, send_messages=False)
                    msg = await event.reply("🔕 24 ghante ka mute! Akl aajaye.")
                    await asyncio.sleep(86400)
                    await client.edit_permissions(event.chat_id, sender.id, send_messages=True)
                    await asyncio.sleep(7); await msg.delete()
                else:
                    await client.kick_participant(event.chat_id, sender.id)
                    msg = await event.reply("🔨 Banned! Promotion se mana kiya tha.")
                    await asyncio.sleep(7); await msg.delete()
            else:
                await event.delete()
                warn = FUNNY_WARNINGS[hash(sender.id) % len(FUNNY_WARNINGS)]
                msg = await event.respond(warn)
                await asyncio.sleep(7); await msg.delete()

    # Auto reply
    settings = GROUP_SETTINGS.get(gid, {})
    if "msg" in settings:
        gap = settings.get("gap", 30)
        delay = settings.get("delay", 15)
        now = time.time()
        if now - last_reply_time.get(gid, 0) >= gap:
            last_reply_time[gid] = now
            if "|" in settings["msg"]:
                txt, link = settings["msg"].split("|", 1)
                sent = await event.reply(txt.strip() + f"\n👉 {link.strip()}")
            else:
                sent = await event.reply(settings["msg"])
            await asyncio.sleep(delay); await sent.delete()

client.start()
client.run_until_disconnected()
