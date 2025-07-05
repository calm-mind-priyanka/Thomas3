from telethon import TelegramClient, events, Button
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

PROMOTION_TRIGGERS = [
    "dm me", "msg me", "pm me", "text me", "inbox me", "ping me",
    "join my group", "join group", "telegram.me/", "t.me/", "promotion", "promote",
    "group link", "channel link", "visit channel", "bio me", "check bio", "link in bio",
    "click bio", "see bio", "insta", "instagram", "follow me", "youtube", "yt", "shorts",
    "mere paas movie", "movie mere pass", "mere paas hai", "mere paas", "film mere paas",
    "movie link", "send link", "link lelo", "group join karo", "add me", "movie in dm",
    "dm for movie", "group ka link", "join fast", "join now", "link de diya", "de dia link",
    "movie ke liye dm", "telegram join", "telegram group", "new channel", "channel join",
    "connect with me", "promotion only", "chat with me"
]

FUNNY_WARNINGS = [
    "🤣 Bhai, yahan reply allowed nahi!",
    "😜 Public mein reply mat kar!",
    "😁 Reply karna mana hai boss!"
]

@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    if event.sender_id in ADMINS:
        btn = [Button.inline("📋 View Groups", b"view_groups"), Button.inline("🧽 Main", b"main_panel")]
        await event.reply("Welcome Admin. Choose an option:", buttons=btn)

@client.on(events.CallbackQuery(data=b"view_groups"))
async def show_groups(event):
    btns = []
    for gid in GROUP_SETTINGS:
        title = GROUP_SETTINGS[gid].get("title", "Unnamed")
        btns.append([Button.inline(f"⚙️ {title}", f"group_{gid}".encode())])
    btns.append([Button.inline("➕ Add Group", b"add_group")])
    btns.append([Button.inline("🔙 Back", b"main_panel")])
    await event.edit("📋 Group List:", buttons=btns)

@client.on(events.CallbackQuery(pattern=b"group_(.*)"))
async def group_options(event):
    gid = event.data.decode().split("_")[1]
    btn = [
        [Button.inline("✏️ Set Msg", f"setmsg_{gid}".encode()), Button.inline("🕒 Set Delay", f"setdel_{gid}".encode())],
        [Button.inline("⏱️ Set Gap", f"setgap_{gid}".encode()), Button.inline("🧹 Toggle DeleteAll", f"toggledelete_{gid}".encode())],
        [Button.inline("🔙 Back", b"view_groups")]
    ]
    await event.edit(f"⚙️ Settings for Group ID: `{gid}`", buttons=btn)

@client.on(events.CallbackQuery(pattern=b"setmsg_(.*)"))
async def setmsg_prompt(event): await event.edit("✏️ Send new message with format:\n`Text|https://link`")

@client.on(events.NewMessage(pattern="/set"))
async def handle_set(event):
    if event.reply_to_msg_id:
        reply = await event.get_reply_message()
        parts = reply.text.split("|")
        if len(parts) == 2:
            gid = str(event.chat_id)
            GROUP_SETTINGS.setdefault(gid, {})["msg"] = reply.text
            save_settings()
            await event.reply("✅ Message set!")

@client.on(events.CallbackQuery(pattern=b"setdel_(.*)"))
async def set_del(event): await event.edit("🕒 Send: `/setdel <seconds>`")

@client.on(events.NewMessage(pattern="/setdel"))
async def handle_del(event):
    try:
        parts = event.text.split()
        GROUP_SETTINGS.setdefault(str(event.chat_id), {})["delay"] = int(parts[1])
        save_settings()
        await event.reply("✅ Delete delay set!")
    except: await event.reply("❌ Format: `/setdel <seconds>`")

@client.on(events.CallbackQuery(pattern=b"setgap_(.*)"))
async def set_gap(event): await event.edit("⏱️ Send: `/setgap <seconds>`")

@client.on(events.NewMessage(pattern="/setgap"))
async def handle_gap(event):
    try:
        parts = event.text.split()
        GROUP_SETTINGS.setdefault(str(event.chat_id), {})["gap"] = int(parts[1])
        save_settings()
        await event.reply("✅ Reply gap set!")
    except: await event.reply("❌ Format: `/setgap <seconds>`")

@client.on(events.CallbackQuery(pattern=b"toggledelete_(.*)"))
async def toggle_delete(event):
    gid = event.data.decode().split("_")[1]
    setting = GROUP_SETTINGS.setdefault(gid, {})
    setting["deleteall"] = not setting.get("deleteall", False)
    save_settings()
    status = "ON" if setting["deleteall"] else "OFF"
    await event.edit(f"🧹 DeleteAll now: {status}", buttons=[[Button.inline("🔙 Back", b"view_groups")]])

@client.on(events.NewMessage(pattern="/main"))
async def main_cmd(event):
    if event.sender_id in ADMINS:
        btn = [
            [Button.inline("🧽 AutoDelete (Members Only)", b"autodel_members")],
            [Button.inline("🔙 Back", b"start_menu")]
        ]
        await event.reply("Main Settings:", buttons=btn)

@client.on(events.CallbackQuery(data=b"main_panel"))
async def main_panel(event):
    btn = [
        [Button.inline("🧽 AutoDelete (Members Only)", b"autodel_members")],
        [Button.inline("🔙 Back", b"start_menu")]
    ]
    await event.edit("Main Settings:", buttons=btn)

@client.on(events.CallbackQuery(data=b"start_menu"))
async def go_start_menu(event):
    btn = [Button.inline("📋 View Groups", b"view_groups"), Button.inline("🧽 Main", b"main_panel")]
    await event.edit("Welcome Admin. Choose an option:", buttons=btn)

@client.on(events.CallbackQuery(data=b"autodel_members"))
async def toggle_member_delete(event):
    gid = str(event.chat_id)
    setting = GROUP_SETTINGS.setdefault(gid, {})
    setting["autodel_members_only"] = not setting.get("autodel_members_only", False)
    save_settings()
    status = "ON" if setting["autodel_members_only"] else "OFF"
    await event.edit(f"🧽 AutoDelete (Members Only): {status}", buttons=[[Button.inline("🔙 Back", b"main_panel")]])

@client.on(events.NewMessage)
async def all_handler(event):
    if not event.is_group: return
    gid = str(event.chat_id)
    sender = await event.get_sender()
    me = await client.get_me()
    my_perms = await client.get_permissions(event.chat_id, me.id)
    if not my_perms.is_admin or sender.bot: return

    # Auto-delete member messages only
    if GROUP_SETTINGS.get(gid, {}).get("autodel_members_only") and not sender.id in ADMINS:
        await event.delete()
        return

    # Promotion filter
    if event.is_reply:
        reply = await event.get_reply_message()
        if reply.sender_id != me.id:
            if sender.id not in ADMINS:
                text = event.text.lower()
                if any(x in text for x in PROMOTION_TRIGGERS):
                    key = f"{gid}_{sender.id}"
                    STRIKES[key] = STRIKES.get(key, 0) + 1
                    lvl = STRIKES[key]
                    save_strikes()
                    await event.delete()
                    if lvl == 1:
                        msg = await event.reply("⚠️ Ye group free hai, apna danda bahar karo!")
                        await asyncio.sleep(7)
                        await msg.delete()
                    elif lvl == 2:
                        await client.edit_permissions(event.chat_id, sender.id, send_messages=False)
                        msg = await event.reply("🔇 Mute laga diya bhai 5 min ke liye! Apna danda sambhal ke rakh.")
                        await asyncio.sleep(300)
                        await client.edit_permissions(event.chat_id, sender.id, send_messages=True)
                        await asyncio.sleep(7)
                        await msg.delete()
                    elif lvl == 3:
                        await client.edit_permissions(event.chat_id, sender.id, send_messages=False)
                        msg = await event.reply("🔕 24 ghante ke liye mute! Ab shant raho, warna apna danda yaad rakhna!")
                        await asyncio.sleep(86400)
                        await client.edit_permissions(event.chat_id, sender.id, send_messages=True)
                        await asyncio.sleep(7)
                        await msg.delete()
                    else:
                        await client.kick_participant(event.chat_id, sender.id)
                        msg = await event.reply("🔨 Banned! Promotion karna allowed nahi, apna danda chal gaya!")
                        await asyncio.sleep(7)
                        await msg.delete()
                else:
                    await event.delete()
                    warn = FUNNY_WARNINGS[hash(sender.id) % len(FUNNY_WARNINGS)]
                    msg = await event.respond(warn)
                    await asyncio.sleep(7)
                    await msg.delete()

    settings = GROUP_SETTINGS.get(gid, {})
    if "msg" in settings:
        gap = settings.get("gap", 30)
        delay = settings.get("delay", 15)
        now = time.time()
        if now - last_reply_time.get(gid, 0) >= gap:
            last_reply_time[gid] = now
            if "|" in settings["msg"]:
                txt, link = settings["msg"].split("|", 1)
                btn = [Button.url("📂 CLICK HERE FOR FILE", link.strip())]
                sent = await event.reply(txt.strip(), buttons=btn)
            else:
                sent = await event.reply(settings["msg"])
            await asyncio.sleep(delay)
            await sent.delete()

client.start()
client.run_until_disconnected()
