from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError
import os, asyncio, json, threading, time
from fastapi import FastAPI
import uvicorn
import logging

# 🟩 Logging setup (errors go to error.log)
logging.basicConfig(level=logging.INFO, filename="error.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# FastAPI Health Check for Koyeb
app = FastAPI()
@app.get("/")
async def root():
    return {"status": "Bot is alive!"}
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

# Hardcoded Credentials for Bot 1 & 2
API_ID1 = 23739953
API_HASH1 = "cf389d498c77dd79d877e33a6f7bc03f"
SESSION1 = "1BVtsOJwBuzQs91-vpRA6BdUyhXKJS_s5uLvo_k5fvt6DO3RfFDA6LwSTL1TKKqfXHUwwUy3LiDt6DM5Q1SBP4sSvv_dT2pLiOD5-PU7rfTsqcw8vNqm5igK3XTx-V4DUL0fFN1C1YYM1BdkuhIeSR8yuo5aVTL4xyRQ6emmRNsyJpn9W5Y9GTOptJLYn8z0WVLMaPrm21NmbfbXjSQoaluc8DJ0OzrV7-w0-2l524Fsmh-nlu75B2f8z56OE13hyCgFNnjzGGSMl8MwSIKERxpZQuDqZXWO4M7YOolJ757EuygcaH_6CUdvIRcDep-4JrUyMunNQTmEkXRtDnFjtXIyvP39VWuw="
ADMIN1 = 7229962808

API_ID2 = 25801447
API_HASH2 = "1b2905795e78355baf7e289183bccb9a"
SESSION2 = "1BVtsOJwBu11_cQ5HN1VHctDPK7jEPaGWMsDTFGz7gksmVUMNoQxeztgDPhUY2AVDwgE5XzmFz2f70WU9NOaBv9l2X4NrnyXM4Wa1r57CdkjVEmykLueeNZJrE2pYvJ-zM_VJPYIFVDQuPCF4tIX3_qu5u_YAXNlPfVl63us2CgMl85q3pfRcF1SC5FyErD_cc8jd9P4BYir4-fUb8Nmws9XN77JMaFs-Euk17uenf151Nx7sOhG5r7EG3-eiiSDe384NG7AIR4KaHQFg6xVcoV1p62S_moNE8oYocPijp80ACvgm1Bi5sYKZYRmB6sMoMaG8p7B1eYV-qyIyDRc2UFR7r1_u9Ng="
ADMIN2 = 7554623404

GROUPS_FILE1 = "groups1.json"
SETTINGS_FILE1 = "settings1.json"
GROUPS_FILE2 = "groups2.json"
SETTINGS_FILE2 = "settings2.json"

# Load/save
def load_data(groups_file, settings_file, default_msg):
    try:
        with open(groups_file) as f: groups = set(json.load(f))
    except: groups = set()
    try:
        with open(settings_file) as f:
            d = json.load(f)
            return groups, d.get("reply_msg", default_msg), d.get("delete_delay", 15), d.get("reply_gap", 30)
    except: return groups, default_msg, 15, 30

def save_groups(path, groups): json.dump(list(groups), open(path, "w"))
def save_settings(path, msg, d, g): json.dump({"reply_msg": msg, "delete_delay": d, "reply_gap": g}, open(path, "w"))

# Configs
groups1, msg1, delay1, gap1 = load_data(GROUPS_FILE1, SETTINGS_FILE1, "🤖 Bot1 here!")
groups2, msg2, delay2, gap2 = load_data(GROUPS_FILE2, SETTINGS_FILE2, "👥 Bot2 here!")
last_reply1, last_reply2 = {}, {}

# Clients
client1 = TelegramClient(StringSession(SESSION1), API_ID1, API_HASH1)
client2 = TelegramClient(StringSession(SESSION2), API_ID2, API_HASH2)

# Bot1 Handler
@client1.on(events.NewMessage)
async def handle1(event):
    global msg1, delay1, gap1
    try:
        sender = await event.get_sender()
        if event.chat_id in groups1 and not sender.bot:
            now = time.time()
            if now - last_reply1.get(event.chat_id, 0) < gap1: return
            last_reply1[event.chat_id] = now
            m = await event.reply(msg1)
            if delay1 > 0: await asyncio.sleep(delay1); await m.delete()
    except ChatWriteForbiddenError: pass
    except Exception as e: logging.error(f"[Bot1] {e}")

# Bot2 Handler
@client2.on(events.NewMessage)
async def handle2(event):
    global msg2, delay2, gap2
    try:
        sender = await event.get_sender()
        if event.chat_id in groups2 and not sender.bot:
            now = time.time()
            if now - last_reply2.get(event.chat_id, 0) < gap2: return
            last_reply2[event.chat_id] = now
            m = await event.reply(msg2)
            if delay2 > 0: await asyncio.sleep(delay2); await m.delete()
    except ChatWriteForbiddenError: pass
    except Exception as e: logging.error(f"[Bot2] {e}")

# Admin Commands Bot 1
@client1.on(events.NewMessage(pattern="/add"))
async def add1(e): 
    if e.sender_id == ADMIN1: groups1.add(e.chat_id); save_groups(GROUPS_FILE1, groups1); await e.reply("✅ Added")

@client1.on(events.NewMessage(pattern="/setmsg"))
async def setmsg1(e):
    global msg1
    if e.sender_id == ADMIN1:
        try: msg1 = e.raw_text.split(" ", 1)[1]; save_settings(SETTINGS_FILE1, msg1, delay1, gap1); await e.reply("✅ Msg set")
        except: await e.reply("❌ Usage: /setmsg text")

@client1.on(events.NewMessage(pattern="/setdel"))
async def setdel1(e):
    global delay1
    if e.sender_id == ADMIN1:
        try: delay1 = int(e.raw_text.split(" ", 1)[1]); save_settings(SETTINGS_FILE1, msg1, delay1, gap1); await e.reply("✅ Delete set")
        except: await e.reply("❌ Usage: /setdel seconds")

@client1.on(events.NewMessage(pattern="/setgap"))
async def setgap1(e):
    global gap1
    if e.sender_id == ADMIN1:
        try: gap1 = int(e.raw_text.split(" ", 1)[1]); save_settings(SETTINGS_FILE1, msg1, delay1, gap1); await e.reply("✅ Gap set")
        except: await e.reply("❌ Usage: /setgap seconds")

@client1.on(events.NewMessage(pattern="/ping"))
async def ping1(e): 
    if e.sender_id == ADMIN1: await e.reply("🏓 Bot1 alive!")

@client1.on(events.NewMessage(pattern="/status"))
async def status1(e):
    if e.sender_id == ADMIN1:
        await e.reply(f"🔧 Bot1 Status:\nGroups: {len(groups1)}\nMsg: {msg1}\nGap: {gap1}s\nDelete: {delay1}s")

# Admin Commands Bot 2
@client2.on(events.NewMessage(pattern="/add"))
async def add2(e): 
    if e.sender_id == ADMIN2: groups2.add(e.chat_id); save_groups(GROUPS_FILE2, groups2); await e.reply("✅ Added")

@client2.on(events.NewMessage(pattern="/setmsg"))
async def setmsg2(e):
    global msg2
    if e.sender_id == ADMIN2:
        try: msg2 = e.raw_text.split(" ", 1)[1]; save_settings(SETTINGS_FILE2, msg2, delay2, gap2); await e.reply("✅ Msg set")
        except: await e.reply("❌ Usage: /setmsg text")

@client2.on(events.NewMessage(pattern="/setdel"))
async def setdel2(e):
    global delay2
    if e.sender_id == ADMIN2:
        try: delay2 = int(e.raw_text.split(" ", 1)[1]); save_settings(SETTINGS_FILE2, msg2, delay2, gap2); await e.reply("✅ Delete set")
        except: await e.reply("❌ Usage: /setdel seconds")

@client2.on(events.NewMessage(pattern="/setgap"))
async def setgap2(e):
    global gap2
    if e.sender_id == ADMIN2:
        try: gap2 = int(e.raw_text.split(" ", 1)[1]); save_settings(SETTINGS_FILE2, msg2, delay2, gap2); await e.reply("✅ Gap set")
        except: await e.reply("❌ Usage: /setgap seconds")

@client2.on(events.NewMessage(pattern="/ping"))
async def ping2(e): 
    if e.sender_id == ADMIN2: await e.reply("🏓 Bot2 alive!")

@client2.on(events.NewMessage(pattern="/status"))
async def status2(e):
    if e.sender_id == ADMIN2:
        await e.reply(f"🔧 Bot2 Status:\nGroups: {len(groups2)}\nMsg: {msg2}\nGap: {gap2}s\nDelete: {delay2}s")

# Start Bots with Await
async def start_clients():
    try: await client1.start()
    except Exception as e: logging.error(f"[Client1 Start Failed] {e}")
    try: await client2.start()
    except Exception as e: logging.error(f"[Client2 Start Failed] {e}")

    tasks = []
    if client1.is_connected(): tasks.append(client1.run_until_disconnected())
    if client2.is_connected(): tasks.append(client2.run_until_disconnected())

    print("✅ Running bots...")
    if tasks: await asyncio.gather(*tasks)
    else: print("❌ Both sessions failed. Check session strings.")

asyncio.get_event_loop().run_until_complete(start_clients())
