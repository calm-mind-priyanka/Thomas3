from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, asyncio, json, threading, time
from fastapi import FastAPI
import uvicorn

# FastAPI for health check
app = FastAPI()
@app.get("/")
async def root():
    return {"status": "Bot is alive!"}
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

API_ID = 23739953
API_HASH = "cf389d498c77dd79d877e33a6f7bc03f"
SESSION = "1BVtsOJwBuzQs91-vpRA6BdUyhXKJS_s5uLvo_k5fvt6DO3RfFDA6LwSTL1TKKqfXHUwwUy3LiDt6DM5Q1SBP4sSvv_dT2pLiOD5-PU7rfTsqcw8vNqm5igK3XTx-V4DUL0fFN1C1YYM1BdkuhIeSR8yuo5aVTL4xyRQ6emmRNsyJpn9W5Y9GTOptJLYn8z0WVLMaPrm21NmbfbXjSQoaluc8DJ0OzrV7-w0-2l524Fsmh-nlu75B2f8z56OE13hyCgFNnjzGGSMl8MwSIKERxpZQuDqZXWO4M7YOolJ757EuygcaH_6CUdvIRcDep-4JrUyMunNQTmEkXRtDnFjtXIyvP39VWuw="
ADMINS = [7229962808]
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

groups, AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON = load_data()
groups.add(-1002713014167)  # your group ID
TARGET_GROUPS = groups

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
    now = time.time()

    # ✅ Auto delete normal messages only if /autodel is enabled AND group is added
    if AUTO_DEL_ON and sender.id not in ADMINS and sender.id != me.id and not sender.bot and event.chat_id in TARGET_GROUPS:
        await event.delete()
        return

    # ✅ Always active: if user replies to another (not bot), check and act
    if event.is_reply and sender.id not in ADMINS and not sender.bot:
        reply = await event.get_reply_message()
        if reply and reply.sender_id != me.id:
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

    # 🟡 Auto reply works only in added groups
    if event.chat_id in TARGET_GROUPS and sender.id != me.id and not sender.bot and now - last_reply_time.get(event.chat_id, 0) >= REPLY_GAP:
        last_reply_time[event.chat_id] = now
        msg = await event.reply(AUTO_REPLY_MSG)
        await asyncio.sleep(DELETE_DELAY)
        try: await msg.delete()
        except: pass

@client.on(events.NewMessage(pattern="/autodel"))
async def toggle_autodel(event):
    global AUTO_DEL_ON
    if event.sender_id in ADMINS:
        args = event.raw_text.split()
        if len(args) == 2 and args[1].lower() in ["on", "off"]:
            AUTO_DEL_ON = args[1].lower() == "on"
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply(f"{'✅' if AUTO_DEL_ON else '❎'} Auto delete {'enabled' if AUTO_DEL_ON else 'disabled'}.")
        else:
            await event.reply("Usage: `/autodel on` or `/autodel off`")

@client.on(events.NewMessage(pattern="/setmsg"))
async def setmsg(event):
    global AUTO_REPLY_MSG
    if event.sender_id in ADMINS and " " in event.raw_text:
        AUTO_REPLY_MSG = event.raw_text.split(" ", 1)[1]
        save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
        await event.reply("✅ Message updated.")
    else:
        await event.reply("❌ Usage: /setmsg your_message_here")

@client.on(events.NewMessage(pattern="/setgap"))
async def setgap(event):
    global REPLY_GAP
    if event.sender_id in ADMINS:
        try:
            REPLY_GAP = int(event.raw_text.split(" ", 1)[1])
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply(f"⏱️ Reply gap set to {REPLY_GAP}s.")
        except:
            await event.reply("❌ Usage: /setgap 10")

@client.on(events.NewMessage(pattern="/setdel"))
async def setdel(event):
    global DELETE_DELAY
    if event.sender_id in ADMINS:
        try:
            DELETE_DELAY = int(event.raw_text.split(" ", 1)[1])
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply(f"⌛ Delete delay set to {DELETE_DELAY}s.")
        except:
            await event.reply("❌ Usage: /setdel 10")

@client.on(events.NewMessage(pattern="/add"))
async def add(event):
    if event.sender_id in ADMINS:
        try:
            gid = int(event.raw_text.split(" ", 1)[1])
            TARGET_GROUPS.add(gid)
            save_groups(TARGET_GROUPS)
            await event.reply(f"✅ Group `{gid}` added.")
        except:
            await event.reply("❌ Usage: /add -1001234567890")

@client.on(events.NewMessage(pattern="/remove"))
async def remove(event):
    if event.sender_id in ADMINS:
        try:
            gid = int(event.raw_text.split(" ", 1)[1])
            TARGET_GROUPS.discard(gid)
            save_groups(TARGET_GROUPS)
            await event.reply(f"❎ Group `{gid}` removed.")
        except:
            await event.reply("❌ Usage: /remove -1001234567890")

@client.on(events.NewMessage(pattern="/id"))
async def id_cmd(event):
    await event.reply(f"Chat ID: `{event.chat_id}`\nUser ID: `{event.sender_id}`")

# 🔁 Auto restart loop
while True:
    try:
        print("🤖 Running...")
        client.start()
        client.run_until_disconnected()
    except Exception as e:
        print(f"⚠️ Error: {e}\n🔁 Restarting in 5 seconds...")
        time.sleep(5)
