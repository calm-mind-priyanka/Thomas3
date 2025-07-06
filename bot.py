from telethon import TelegramClient, events
from telethon.sessions import StringSession
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
SESSION = "1BVtsOJwBuzQs91-vpRA6BdUyhXKJS_s5uLvo_k5fvt6DO3RfFDA6LwSTL1TKKqfXHUwwUy3LiDt6DM5Q1SBP4sSvv_dT2pLiOD5-PU7rfTsqcw8vNqm5igK3XTx-V4DUL0fFN1C1YYM1BdkuhIeSR8yuo5aVTL4xyRQ6emmRNsyJpn9W5Y9GTOptJLYn8z0WVLMaPrm21NmbfbXjSQoaluc8DJ0OzrV7-w0-2l524Fsmh-nlu75B2f8z56OE13hyCgFNnjzGGSMl8MwSIKERxpZQuDqZXWO4M7YOolJ757EuygcaH_6CUdvIRcDep-4JrUyMunNQTmEkXRtDnFjtXIyvP39VWuw="
ADMINS = [7229962808]
GROUPS_FILE = "groups.json"
SETTINGS_FILE = "settings.json"
STRIKES_FILE = "strikes.json"

PROMO_TRIGGERS = ["dm me", "pm me", "join group", "t.me/", "http", "https", "@", ".me/", "link in bio", "telegram group", "promotion", "follow me", "movie link"]
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
TARGET_GROUPS = groups

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
last_reply_time = {}
if os.path.exists(STRIKES_FILE): STRIKES = json.load(open(STRIKES_FILE))

@client.on(events.ChatAction)
async def bot_kick_on_add(event):
    if event.user_added and event.is_group:
        added_user = await client.get_entity(event.user_id)
        if added_user.bot:
            try:
                await client.kick_participant(event.chat_id, event.user_id)
                await event.respond(f"🤖 Bot `{added_user.first_name}` not allowed. Kicked!")
                adder_id = event.action_message.from_id.user_id
                key = f"botadder_{event.chat_id}_{adder_id}"
                STRIKES[key] = STRIKES.get(key, 0) + 1
                save_strikes()
                if STRIKES[key] >= 2:
                    await client.kick_participant(event.chat_id, adder_id)
                    await event.respond(f"🔨 `{adder_id}` banned for adding bots repeatedly.")
                else:
                    await event.respond("⚠️ Don't add bots! You'll be banned next time.")
            except Exception as e:
                print(f"❌ Error kicking bot or punishing user: {e}")

@client.on(events.NewMessage(pattern="/id"))
async def id_handler(event):
    if event.sender_id in ADMINS:
        await event.reply(f"👤 Your ID: `{event.sender_id}`\n👥 Group ID: `{event.chat_id}`")

@client.on(events.NewMessage(pattern="/add"))
async def add_group(event):
    if event.sender_id in ADMINS:
        TARGET_GROUPS.add(event.chat_id)
        save_groups(TARGET_GROUPS)
        await event.reply("✅ Group added for auto-reply.")

@client.on(events.NewMessage(pattern="/remove"))
async def remove_group(event):
    if event.sender_id in ADMINS:
        if event.chat_id in TARGET_GROUPS:
            TARGET_GROUPS.remove(event.chat_id)
            save_groups(TARGET_GROUPS)
            await event.reply("❌ Group removed.")
        else:
            await event.reply("⚠️ Group not in list.")

@client.on(events.NewMessage(pattern="/setmsg"))
async def set_msg(event):
    if event.sender_id in ADMINS:
        msg = event.raw_text.split(" ", 1)
        if len(msg) > 1:
            global AUTO_REPLY_MSG
            AUTO_REPLY_MSG = msg[1]
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply("✅ Message updated.")
        else:
            await event.reply("⚠️ Usage: /setmsg Your Message")

@client.on(events.NewMessage(pattern="/setgap"))
async def set_gap(event):
    if event.sender_id in ADMINS:
        try:
            global REPLY_GAP
            REPLY_GAP = int(event.raw_text.split(" ", 1)[1])
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply(f"✅ Gap set to {REPLY_GAP} sec.")
        except:
            await event.reply("⚠️ Usage: /setgap 30")

@client.on(events.NewMessage(pattern="/setdel"))
async def set_del(event):
    if event.sender_id in ADMINS:
        try:
            global DELETE_DELAY
            DELETE_DELAY = int(event.raw_text.split(" ", 1)[1])
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply(f"✅ Delete delay set to {DELETE_DELAY} sec.")
        except:
            await event.reply("⚠️ Usage: /setdel 15")

@client.on(events.NewMessage(pattern="/autodel"))
async def toggle_autodel(event):
    if event.sender_id in ADMINS:
        cmd = event.raw_text.split(" ", 1)
        global AUTO_DEL_ON
        if len(cmd) > 1 and cmd[1].lower() in ["on", "off"]:
            AUTO_DEL_ON = (cmd[1].lower() == "on")
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply(f"✅ Auto-delete set to {AUTO_DEL_ON}")
        else:
            await event.reply("⚠️ Usage: /autodel on or /autodel off")

@client.on(events.NewMessage)
async def global_moderation(event):
    sender = await event.get_sender()
    me = await client.get_me()
    text = event.raw_text.lower()
    is_group = event.is_group
    is_me_admin = (await client.get_permissions(event.chat_id, me.id)).is_admin if is_group else False
    is_promo = any(x in text for x in PROMO_TRIGGERS) or len(text) > 100

    # 🔥 Global auto-delete promo logic (NO command needed, just make admin)
    if is_group and is_promo and sender.id != me.id and not sender.bot and is_me_admin:
        try:
            await event.delete()
        except: pass

    # 🤖 Auto-reply logic only if group is added
    if is_group and event.chat_id in TARGET_GROUPS and sender.id != me.id and not sender.bot:
        now = time.time()
        if now - last_reply_time.get(event.chat_id, 0) >= REPLY_GAP:
            last_reply_time[event.chat_id] = now
            try:
                msg = await event.reply(AUTO_REPLY_MSG)
                await asyncio.sleep(DELETE_DELAY)
                await msg.delete()
            except: pass

while True:
    try:
        print("🤖 Running...")
        client.start()
        client.run_until_disconnected()
    except Exception as e:
        print(f"⚠️ Error: {e}\n🔁 Restarting...")
        time.sleep(5)
