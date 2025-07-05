from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError
import os, asyncio, json, threading, time
from fastapi import FastAPI
import uvicorn

app = FastAPI()
@app.get("/")
async def root(): return {"status": "Bot is alive!"}
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

API_ID = 22938364
API_HASH = "81cc7882c88b7cb7785cb1a8d59e93a8"
SESSION = "1BVtsOJwBuzjwnv-Q9-rNWjr9LrPJBq0swEvwkmGKwm4ainxC3UkeMsDflfLwAfxZwxhrKnAjfSD2fipWKnRKLa92HgMD1S5aHcFkxBFcHUtYdln9OQVx8ZQ3nroVXDP7Ahy-14wIwjVCUGDwsrPZFpD0p9vDya_rqigzgbUSuLZ9z-LW5E95C7uejbZRjbywW4BCNEP7eIYgRMy2-9Tj3GtjFmZztJy-B_lArxtJ6R9GWgO9GX2ZPS2b8XyC4-HVuHj-it1RSX4-fp5r0AhsgFEA6vA0giUDcmHzUzJIWeB7aKma2FUSvxAODe0jncBbwRLZfGiZm8AeT4b-sMfWVgEySHWzttc="
ADMINS = [6046055058]
GROUPS_FILE = "groups.json"
SETTINGS_FILE = "settings.json"
STRIKES_FILE = "strikes.json"

PROMO_TRIGGERS = ["dm me", "join group", "t.me/", "link in bio", "telegram group", "promotion", "follow me", "movie link"]
FUNNY_RESPONSES = ["⚠️ Yeh kya be? Public mein dhandha?", "🚫 Apna dhandha kahi aur le ja!", "🤨 Promote karne aaye ho? Seedha ban!"]
STRIKES = {}

def load_data():
    try: groups = set(json.load(open(GROUPS_FILE)))
    except: groups = set()
    try:
        data = json.load(open(SETTINGS_FILE))
        return groups, data.get("reply_msg", "SEARCH MOVIE HERE"), data.get("delete_delay", 15), data.get("reply_gap", 30), data.get("autodel", False)
    except: return groups, "SEARCH MOVIE HERE", 15, 30, False

def save_all(reply, delay, gap, autodel): json.dump({"reply_msg": reply, "delete_delay": delay, "reply_gap": gap, "autodel": autodel}, open(SETTINGS_FILE, "w"))
def save_groups(g): json.dump(list(g), open(GROUPS_FILE, "w"))
def save_strikes(): json.dump(STRIKES, open(STRIKES_FILE, "w"))

TARGET_GROUPS, AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON = load_data()
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
last_reply_time = {}
if os.path.exists(STRIKES_FILE): STRIKES = json.load(open(STRIKES_FILE))

@client.on(events.ChatAction)
async def auto_joined(event):
    if event.user_added or event.user_joined:
        if event.user_id == (await client.get_me()).id and event.is_group:
            TARGET_GROUPS.add(event.chat_id)
            save_groups(TARGET_GROUPS)

@client.on(events.NewMessage)
async def message_handler(event):
    global AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON
    if not event.is_group: return
    sender = await event.get_sender()
    me = await client.get_me()
    if event.chat_id in TARGET_GROUPS:
        if AUTO_DEL_ON and sender.id not in ADMINS and not sender.bot:
            await event.delete(); return
        if event.is_reply and sender.id not in ADMINS:
            reply = await event.get_reply_message()
            if reply.sender_id != me.id:
                text = event.text.lower()
                if any(x in text for x in PROMO_TRIGGERS):
                    key = f"{event.chat_id}_{sender.id}"
                    STRIKES[key] = STRIKES.get(key, 0) + 1
                    level = STRIKES[key]
                    save_strikes()
                    await event.delete()
                    if level == 1:
                        msg = await event.reply("⚠️ First Warning! Yahaan apna dhandha mat chalao.")
                        await asyncio.sleep(5); await msg.delete()
                    elif level == 2:
                        msg = await event.reply("⛔ Second Warning! Agli baar mute milega.")
                        await asyncio.sleep(5); await msg.delete()
                    elif level == 3:
                        await client.edit_permissions(event.chat_id, sender.id, send_messages=False)
                        msg = await event.reply("🤐 Muted for 5 minutes. Samajh ja!")
                        await asyncio.sleep(300)
                        await client.edit_permissions(event.chat_id, sender.id, send_messages=True)
                        await asyncio.sleep(3); await msg.delete()
                    else:
                        await client.kick_participant(event.chat_id, sender.id)
                        await event.respond("🔨 Permanent Ban! Yeh group tera nahi.")
                else:
                    await event.delete()
                    msg = await event.respond(FUNNY_RESPONSES[hash(sender.id) % len(FUNNY_RESPONSES)])
                    await asyncio.sleep(4); await msg.delete()
        now = time.time()
        if sender.id != me.id and not sender.bot and now - last_reply_time.get(event.chat_id, 0) >= REPLY_GAP:
            last_reply_time[event.chat_id] = now
            msg = await event.reply(AUTO_REPLY_MSG)
            await asyncio.sleep(DELETE_DELAY)
            try: await msg.delete()
            except: pass

@client.on(events.NewMessage(pattern="/autodel"))
async def toggle_autodel(event):
    global AUTO_DEL_ON, AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP
    if event.sender_id in ADMINS:
        cmd = event.text.split(" ")
        if len(cmd) == 2:
            if cmd[1].lower() == "on":
                AUTO_DEL_ON = True
                save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
                await event.reply("✅ Auto delete for members enabled.")
            elif cmd[1].lower() == "off":
                AUTO_DEL_ON = False
                save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
                await event.reply("❎ Auto delete for members disabled.")
            else:
                await event.reply("Usage: `/autodel on` or `/autodel off`")

@client.on(events.NewMessage(pattern="/setmsg"))
async def setmsg(event):
    global AUTO_REPLY_MSG
    if event.sender_id in ADMINS:
        AUTO_REPLY_MSG = event.raw_text.split(" ", 1)[1]
        save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
        await event.reply("✅ Message set.")

@client.on(events.NewMessage(pattern="/setgap"))
async def setgap(event):
    global REPLY_GAP
    if event.sender_id in ADMINS:
        REPLY_GAP = int(event.raw_text.split(" ", 1)[1])
        save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
        await event.reply(f"⏱️ Reply gap set to {REPLY_GAP}s.")

@client.on(events.NewMessage(pattern="/setdel"))
async def setdel(event):
    global DELETE_DELAY
    if event.sender_id in ADMINS:
        DELETE_DELAY = int(event.raw_text.split(" ", 1)[1])
        save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
        await event.reply(f"⌛ Delete delay set to {DELETE_DELAY}s.")

@client.on(events.NewMessage(pattern="/add"))
async def add(event):
    if event.sender_id in ADMINS:
        gid = int(event.raw_text.split(" ", 1)[1])
        TARGET_GROUPS.add(gid)
        save_groups(TARGET_GROUPS)
        await event.reply(f"✅ Group `{gid}` added.")

@client.on(events.NewMessage(pattern="/remove"))
async def remove(event):
    if event.sender_id in ADMINS:
        gid = int(event.raw_text.split(" ", 1)[1])
        TARGET_GROUPS.discard(gid)
        save_groups(TARGET_GROUPS)
        await event.reply(f"❎ Group `{gid}` removed.")

@client.on(events.NewMessage(pattern="/id"))
async def id_cmd(event):
    await event.reply(f"Chat ID: `{event.chat_id}`\nUser ID: `{event.sender_id}`")

print("🤖 Running...")
client.start()
client.run_until_disconnected()
