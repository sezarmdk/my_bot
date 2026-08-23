import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import ReactionCustomEmoji, ReactionEmoji
from telethon.tl.functions.stories import (
    GetPeerStoriesRequest, ReadStoriesRequest, SendReactionRequest
)
from telethon.utils import get_display_name

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
LOG_CHANNEL_ID = -1004327250392
PORT = int(os.environ.get("PORT", 8080))

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_CHAT_ID = None
ONLINE_TASK = None
AUTO_READ_ENABLED = False

UZ_TZ = timezone(timedelta(hours=5))
def get_uz_time(): return datetime.now(UZ_TZ)

def format_duration(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days > 0: parts.append(f"{days} kun")
    if hours > 0: parts.append(f"{hours} soat")
    if minutes > 0: parts.append(f"{minutes} daqiqa")
    parts.append(f"{seconds} soniya")
    return ", ".join(parts)

DB_FILE = 'story_bot_db.json'

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"story_targets": {}, "viewed_stories": {}}

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_data()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def notify_log(text):
    try:
        await client.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        print(f"Log xatosi: {e}")

# ----------------- 1. STORY TRACKER LOOP -----------------
async def check_stories():
    while True:
        try:
            targets = list(db.get("story_targets", {}).items())
            for uid_str, info in targets:
                try:
                    uid = int(uid_str) if uid_str.lstrip('-').isdigit() else uid_str
                    ent = await client.get_entity(uid)
                    res = await client(GetPeerStoriesRequest(peer=ent))
                    
                    if hasattr(res, 'stories') and res.stories:
                        for s in res.stories.stories:
                            viewed_list = db.setdefault("viewed_stories", {}).setdefault(str(ent.id), [])
                            if s.id not in viewed_list:
                                await client(ReadStoriesRequest(peer=ent, max_id=s.id))
                                
                                emoji_id = str(info.get("emoji_id"))
                                try:
                                    await client(SendReactionRequest(
                                        peer=ent,
                                        story_id=s.id,
                                        reaction=ReactionCustomEmoji(document_id=int(emoji_id))
                                    ))
                                except Exception:
                                    try:
                                        await client(SendReactionRequest(
                                            peer=ent,
                                            story_id=s.id,
                                            reaction=ReactionEmoji(emoticon='❤️')
                                        ))
                                    except Exception: pass

                                viewed_list.append(s.id)
                                save_data(db)
                                
                                name = get_display_name(ent)
                                username = f"@{ent.username}" if getattr(ent, 'username', None) else "Mavjud emas"
                                time_str = get_uz_time().strftime('%Y-%m-%d %H:%M:%S')
                                
                                log_text = (
                                    f"🔥 **Storyga Reaksiya Bosildi!**\n\n"
                                    f"👤 **Foydalanuvchi:** {name}\n"
                                    f"🔗 **Username:** {username}\n"
                                    f"🆔 **ID:** `{ent.id}`\n"
                                    f"✨ **Emoji ID:** `{emoji_id}`\n"
                                    f"📊 **Story ID:** `{s.id}`\n"
                                    f"⏰ **Vaqti:** `{time_str}`"
                                )
                                await notify_log(log_text)
                except Exception: pass
                await asyncio.sleep(2)
        except Exception: pass
        await asyncio.sleep(10)

# ----------------- 2. 24/7 ONLINE LOOP -----------------
async def online_worker():
    global ONLINE_CHAT_ID
    while True:
        try:
            if ONLINE_CHAT_ID is not None:
                current_time = get_uz_time().strftime('%H:%M:%S')
                msg = await client.send_message(ONLINE_CHAT_ID, f"🕒 {current_time}")
                await asyncio.sleep(1)
                await msg.delete()
        except Exception as e:
            print(f"Online xabari xatosi: {e}")
        await asyncio.sleep(29)

# ----------------- 3. AUTO READ PERSONAL MESSAGES -----------------
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def auto_read_private_handler(event):
    global AUTO_READ_ENABLED
    if AUTO_READ_ENABLED:
        try:
            await event.mark_read()
        except Exception as e:
            print(f"Auto read xatosi: {e}")

# ----------------- COMMANDS -----------------
@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global db, ONLINE_CHAT_ID, ONLINE_START_TIME, ONLINE_TASK, AUTO_READ_ENABLED
    txt = event.raw_text or ""
    if not txt.startswith("."):
        return

    parts = txt.strip().split()
    cmd = parts[0]

    if cmd == ".ping":
        await event.edit("🏓 **Pong! Bot faol ishlayapti.**")

    elif cmd == ".story":
        if len(parts) < 3:
            await event.edit("❌ **Ishlatish:** `.story <id/@username> <emoji_id>`")
            return
        
        target_arg = parts[1]
        emoji_id_arg = parts[2]
        
        if not emoji_id_arg.isdigit():
            await event.edit("❌ **Xato:** Emoji ID faqat raqamlardan iborat bo'lishi kerak!")
            return

        try:
            ent = await client.get_entity(int(target_arg) if target_arg.lstrip('-').isdigit() else target_arg)
            
            if str(ent.id) in db.get("viewed_stories", {}):
                db["viewed_stories"][str(ent.id)] = []

            db.setdefault("story_targets", {})[str(ent.id)] = {
                "emoji_id": emoji_id_arg,
                "name": get_display_name(ent)
            }
            save_data(db)
            
            await event.edit(
                f"✅ **Kuzatuvga olindi!**\n\n"
                f"👤 {get_display_name(ent)} (`{ent.id}`)\n"
                f"✨ **Custom Emoji ID:** `{emoji_id_arg}`"
            )
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    elif cmd == ".stop":
        if len(parts) < 2:
            await event.edit("❌ **Ishlatish:** `.stop <id/@username>`")
            return
        target_arg = parts[1]
        try:
            ent = await client.get_entity(int(target_arg) if target_arg.lstrip('-').isdigit() else target_arg)
            targets = db.get("story_targets", {})
            if str(ent.id) in targets:
                del targets[str(ent.id)]
                save_data(db)
                await event.edit(f"🛑 **To'xtatildi:** {get_display_name(ent)} (`{ent.id}`)")
            else:
                await event.edit("⚠️ Bu foydalanuvchi topilmadi.")
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    elif cmd == ".stat":
        targets = db.get("story_targets", {})
        if not targets:
            await event.edit("📊 Hozirda kuzatuvda hech kim yo'q.")
            return
            
        text = f"📊 **Kuzatuvdagilar ({len(targets)} ta):**\n\n"
        for uid, info in targets.items():
            name = info.get("name", "Noma'lum")
            emoji_id = info.get("emoji_id")
            text += f"👤 **Ism:** {name}\n🆔 **ID:** `{uid}`\n✨ **Emoji ID:** `{emoji_id}`\n-------------------\n"
        await event.edit(text)

    elif cmd == ".on":
        ONLINE_CHAT_ID = event.chat_id
        ONLINE_START_TIME = time.time()
        
        if ONLINE_TASK is None or ONLINE_TASK.done():
            ONLINE_TASK = asyncio.create_task(online_worker())
            
        await event.edit(f"🟢 **24/7 Online rejimi yoqildi!**\n📍 Har 30 soniyada ushbu chat orqali online signal yuboriladi.")

    elif cmd == ".off":
        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
        ONLINE_CHAT_ID = None
        ONLINE_START_TIME = None
        await event.edit("🔴 **24/7 Online rejimi to'xtatildi.**")

    elif cmd == ".read":
        AUTO_READ_ENABLED = True
        await event.edit("👀 **Avtomatik o'qish (Auto-Read) yoqildi!**\nBarcha shaxsiy chatlardan kelgan yangi xabarlar kelishi bilanoq o'qilgan qilinadi.")

    elif cmd == ".unread":
        AUTO_READ_ENABLED = False
        await event.edit("🙈 **Avtomatik o'qish (Auto-Read) to'xtatildi.**")

    elif cmd == ".info":
        uptime_str = format_duration(time.time() - BOT_START_TIME)
        
        if ONLINE_START_TIME:
            online_str = format_duration(time.time() - ONLINE_START_TIME)
            status_online = f"🟢 **Faol** ({online_str})"
        else:
            status_online = "🔴 **O'chiq**"

        status_read = "🟢 **Yoqilgan**" if AUTO_READ_ENABLED else "🔴 **O'chirilgan**"

        await event.edit(
            f"ℹ️ **Tizim Ma'lumotlari:**\n\n"
            f"⏳ **Skript ishlash vaqti (Uptime):** {uptime_str}\n"
            f"📶 **24/7 Online holati:** {status_online}\n"
            f"👀 **Auto-Read holati:** {status_read}\n"
            f"📸 **Kuzatuvdagi Storylar:** {len(db.get('story_targets', {}))} ta"
        )

async def handle_ping_web(request):
    return web.Response(text="OK")

async def main():
    await client.start()
    
    app = web.Application()
    app.router.add_get('/', handle_ping_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    
    asyncio.create_task(check_stories())
    print("Bot 3 ta modul bilan to'liq ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
