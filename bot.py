from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os, asyncio, json, threading, time, random
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
FUNNY_RESPONSES = ["😏 Kya bhai? Tera fufa ka ladka ya lakhi hai kya?"]
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
            await event.reply("❌ Group removed from auto-reply.")
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
            await event.reply("✅ Auto-reply message updated.")
        else:
            await event.reply("⚠️ Usage: /setmsg Your Message")

@client.on(events.NewMessage(pattern="/setgap"))
async def set_gap(event):
    if event.sender_id in ADMINS:
        try:
            global REPLY_GAP
            REPLY_GAP = int(event.raw_text.split(" ", 1)[1])
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply(f"✅ Reply gap set to {REPLY_GAP} seconds.")
        except:
            await event.reply("⚠️ Usage: /setgap 30")

@client.on(events.NewMessage(pattern="/setdel"))
async def set_del(event):
    if event.sender_id in ADMINS:
        try:
            global DELETE_DELAY
            DELETE_DELAY = int(event.raw_text.split(" ", 1)[1])
            save_all(AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON)
            await event.reply(f"✅ Delete delay set to {DELETE_DELAY} seconds.")
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
async def message_handler(event):
    global AUTO_REPLY_MSG, DELETE_DELAY, REPLY_GAP, AUTO_DEL_ON
    if not event.is_group: return
    sender = await event.get_sender()
    me = await client.get_me()
    now = time.time()
    text = event.text.lower()
    is_promo = any(x in text for x in PROMO_TRIGGERS) or len(text) > 100

    # Auto-delete if autodel is on and userbot is admin
    if AUTO_DEL_ON and sender.id != me.id and not sender.bot:
        perms = await client.get_permissions(event.chat_id, me.id)
        if perms.is_admin:
            await event.delete()
            return

    # Handle reply promotions or chats
    if event.is_reply and sender.id != me.id and not sender.bot:
        reply = await event.get_reply_message()
        if reply and reply.sender_id != me.id:
            if is_promo:
                key = f"{event.chat_id}_{sender.id}"
                STRIKES[key] = STRIKES.get(key, 0) + 1
                level = STRIKES[key]
                save_strikes()
                await event.delete()
                if level == 1:
                    msg = await event.reply("⚠️ First Warning! Apna dhandha yahan nahi.")
                    await asyncio.sleep(5); await msg.delete()
                elif level == 2:
                    msg = await event.reply("⛔ Second Warning! Agli baar mute milega.")
                    await asyncio.sleep(5); await msg.delete()
                elif level == 3:
                    await client.edit_permissions(event.chat_id, sender.id, send_messages=False)
                    msg = await event.reply("🤐 Muted for 5 minutes.")
                    await asyncio.sleep(300)
                    await client.edit_permissions(event.chat_id, sender.id, send_messages=True)
                    await asyncio.sleep(2); await msg.delete()
                else:
                    await client.kick_participant(event.chat_id, sender.id)
                    await event.respond("🔨 Banned for repeated promotions.")
            else:
                await event.delete()
                msg = await event.reply(random.choice(FUNNY_RESPONSES))
                await asyncio.sleep(5)
                await msg.delete()

    # Handle direct promo messages (not replies)
    if is_promo and sender.id != me.id and not sender.bot:
        key = f"{event.chat_id}_{sender.id}"
        STRIKES[key] = STRIKES.get(key, 0) + 1
        level = STRIKES[key]
        save_strikes()
        await event.delete()
        if level == 1:
            msg = await event.reply("⚠️ First Warning! Apna dhandha yahan nahi.")
            await asyncio.sleep(5); await msg.delete()
        elif level == 2:
            msg = await event.reply("⛔ Second Warning! Agli baar mute milega.")
            await asyncio.sleep(5); await msg.delete()
        elif level == 3:
            await client.edit_permissions(event.chat_id, sender.id, send_messages=False)
            msg = await event.reply("🤐 Muted for 5 minutes.")
            await asyncio.sleep(300)
            await client.edit_permissions(event.chat_id, sender.id, send_messages=True)
            await asyncio.sleep(2); await msg.delete()
        else:
            await client.kick_participant(event.chat_id, sender.id)
            await event.respond("🔨 Banned for repeated promotions.")

    # Auto-reply only in added groups
    if event.chat_id in TARGET_GROUPS and sender.id != me.id and not sender.bot:
        if now - last_reply_time.get(event.chat_id, 0) >= REPLY_GAP:
            last_reply_time[event.chat_id] = now
            msg = await event.reply(AUTO_REPLY_MSG)
            await asyncio.sleep(DELETE_DELAY)
            try: await msg.delete()
            except: pass

while True:
    try:
        print("🤖 Running...")
        client.start()
        client.run_until_disconnected()
    except Exception as e:
        print(f"⚠️ Error: {e}\n🔁 Restarting in 5 seconds...")
        time.sleep(5)
