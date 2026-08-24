import asyncio
import json
import os
import sys
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

# ==================== [KONFIGURATSIYA VA O'ZGARUVCHILAR] ====================
API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
LOG_CHANNEL_ID = -1004327250392
PORT = int(os.environ.get("PORT", 8080))
DB_FILE = 'story_bot_db.json'

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_CHAT_ID = None
ONLINE_TASK = None
AUTO_READ_ENABLED = False

UZ_TZ = timezone(timedelta(hours=5))

def get_uz_time():
    return datetime.now(UZ_TZ)

def format_duration(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} kun")
    if hours > 0:
        parts.append(f"{hours} soat")
    if minutes > 0:
        parts.append(f"{minutes} daqiqa")
    parts.append(f"{seconds} soniya")
    return ", ".join(parts) if parts else "0 soniya"

# ==================== [MA'LUMOTLAR BAZASI BOSHQARUVI] ====================
def load_database():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"Baza o'qishda xatolik: {e}")
    return {
        "story_targets": {},
        "viewed_stories": {}
    }

def save_database(data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Baza saqlashda xatolik: {e}")

db = load_database()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def notify_log_channel(text):
    try:
        await client.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        print(f"Log kanalga yuborishda xatolik: {e}")

# ==================== [MODUL 1: STORY MONITORING LOOP] ====================
async def story_monitoring_loop():
    while True:
        try:
            targets = list(db.get("story_targets", {}).items())
            for uid_str, info in targets:
                try:
                    uid = int(uid_str) if uid_str.lstrip('-').isdigit() else uid_str
                    peer_entity = await client.get_entity(uid)
                    stories_result = await client(GetPeerStoriesRequest(peer=peer_entity))
                    
                    if hasattr(stories_result, 'stories') and stories_result.stories:
                        for story_item in stories_result.stories.stories:
                            viewed_list = db.setdefault("viewed_stories", {}).setdefault(str(peer_entity.id), [])
                            
                            if story_item.id not in viewed_list:
                                await client(ReadStoriesRequest(peer=peer_entity, max_id=story_item.id))
                                
                                emoji_id = str(info.get("emoji_id"))
                                reaction_payload = ReactionCustomEmoji(document_id=int(emoji_id))
                                
                                is_reacted = False
                                try:
                                    await client(SendReactionRequest(
                                        peer=peer_entity,
                                        story_id=story_item.id,
                                        reaction=reaction_payload
                                    ))
                                    is_reacted = True
                                except Exception as reaction_error:
                                    print(f"Custom reaksiya xatosi: {reaction_error}, standart emoji sinab ko'rilmoqda...")
                                    try:
                                        await client(SendReactionRequest(
                                            peer=peer_entity,
                                            story_id=story_item.id,
                                            reaction=ReactionEmoji(emoticon='❤️')
                                        ))
                                        is_reacted = True
                                    except Exception as fallback_error:
                                        print(f"Standart reaksiya ham o'tmadi: {fallback_error}")

                                viewed_list.append(story_item.id)
                                save_database(db)
                                
                                user_display = get_display_name(peer_entity)
                                user_handle = f"@{peer_entity.username}" if getattr(peer_entity, 'username', None) else "Mavjud emas"
                                action_time = get_uz_time().strftime('%Y-%m-%d %H:%M:%S')
                                
                                log_entry = (
                                    f"🔥 **Storyga Reaksiya Bosildi!**\n\n"
                                    f"👤 **Foydalanuvchi:** {user_display}\n"
                                    f"🔗 **Username:** {user_handle}\n"
                                    f"🆔 **ID:** `{peer_entity.id}`\n"
                                    f"✨ **Custom Emoji ID:** `{emoji_id}`\n"
                                    f"📊 **Story ID:** `{story_item.id}`\n"
                                    f"⏰ **Vaqti:** `{action_time}`"
                                )
                                await notify_log_channel(log_entry)
                except Exception as user_proc_error:
                    pass
                await asyncio.sleep(2)
        except Exception as main_story_error:
            pass
        await asyncio.sleep(10)

# ==================== [MODUL 2: 24/7 ALWAYS ONLINE LOOP] ====================
async def always_online_loop():
    global ONLINE_CHAT_ID
    while True:
        try:
            if ONLINE_CHAT_ID is not None:
                current_clock = get_uz_time().strftime('%H:%M:%S')
                ping_message = await client.send_message(ONLINE_CHAT_ID, f"🕒 {current_clock}")
                await asyncio.sleep(1)
                await ping_message.delete()
        except Exception as online_ping_error:
            print(f"Online xabari xatosi: {online_ping_error}")
        await asyncio.sleep(29)

# ==================== [MODUL 3: INSTANT AUTO-READ PRIVATE MESSAGES] ====================
@client.on(events.NewMessage(incoming=True))
async def global_incoming_message_handler(event):
    global AUTO_READ_ENABLED
    if AUTO_READ_ENABLED and event.is_private:
        try:
            await event.mark_read()
        except Exception as read_error:
            pass

# ==================== [YAGONA BUYRUQLAR BOSHQARUV MARKAZI] ====================
@client.on(events.NewMessage(outgoing=True))
async def master_commands_router(event):
    global db, ONLINE_CHAT_ID, ONLINE_START_TIME, ONLINE_TASK, AUTO_READ_ENABLED
    
    raw_content = (event.raw_text or "").strip()
    if not raw_content.startswith("."):
        return

    tokens = raw_content.split()
    command = tokens[0].lower()

    if command == ".ping":
        await event.edit("🏓 **Pong! Bot va barcha modullar faol ishlayapti.**")

    elif command == ".story":
        if len(tokens) < 3:
            await event.edit("❌ **Ishlatish:** `.story <id/@username> <emoji_id>`")
            return
        
        target_param = tokens[1]
        emoji_id_param = tokens[2]
        
        if not emoji_id_param.isdigit():
            await event.edit("❌ **Xato:** Custom Emoji ID faqat raqamlardan iborat bo'lishi kerak!")
            return

        try:
            target_identity = int(target_param) if target_param.lstrip('-').isdigit() else target_param
            entity_obj = await client.get_entity(target_identity)
            
            if str(entity_obj.id) in db.get("viewed_stories", {}):
                db["viewed_stories"][str(entity_obj.id)] = []

            db.setdefault("story_targets", {})[str(entity_obj.id)] = {
                "emoji_id": emoji_id_param,
                "name": get_display_name(entity_obj)
            }
            save_database(db)
            
            await event.edit(
                f"✅ **Kuzatuvga olindi!**\n\n"
                f"👤 {get_display_name(entity_obj)} (`{entity_obj.id}`)\n"
                f"✨ **Custom Emoji ID:** `{emoji_id_param}`\n"
                f"⚡️ *Live storiylari darhol tekshiriladi.*"
            )
        except Exception as add_target_error:
            await event.edit(f"❌ Xatolik yuz berdi: {add_target_error}")

    elif command == ".stop":
        if len(tokens) < 2:
            await event.edit("❌ **Ishlatish:** `.stop <id/@username>`")
            return
        target_param = tokens[1]
        try:
            target_identity = int(target_param) if target_param.lstrip('-').isdigit() else target_param
            entity_obj = await client.get_entity(target_identity)
            active_targets = db.get("story_targets", {})
            if str(entity_obj.id) in active_targets:
                del active_targets[str(entity_obj.id)]
                save_database(db)
                await event.edit(f"🛑 **Kuzatuv to'xtatildi:** {get_display_name(entity_obj)} (`{entity_obj.id}`)")
            else:
                await event.edit("⚠️ Bu foydalanuvchi kuzatuv ro'yxatida topilmadi.")
        except Exception as stop_error:
            await event.edit(f"❌ Xatolik: {stop_error}")

    elif command == ".stat":
        active_targets = db.get("story_targets", {})
        if not active_targets:
            await event.edit("📊 Hozirda kuzatuvda hech kim yo'q.")
            return
            
        summary_text = f"📊 **Kuzatuvdagi Storylar ({len(active_targets)} ta):**\n\n"
        for uid_key, target_data in active_targets.items():
            user_title = target_data.get("name", "Noma'lum")
            custom_emoji_ref = target_data.get("emoji_id")
            summary_text += f"👤 **Ism:** {user_title}\n🆔 **ID:** `{uid_key}`\n✨ **Emoji ID:** `{custom_emoji_ref}`\n-------------------\n"
        await event.edit(summary_text)

    elif command == ".on":
        ONLINE_CHAT_ID = event.chat_id
        ONLINE_START_TIME = time.time()
        
        if ONLINE_TASK is None or ONLINE_TASK.done():
            ONLINE_TASK = asyncio.create_task(always_online_loop())
            
        await event.edit("🟢 **24/7 Online rejimi yoqildi!**\n📍 Har 30 soniyada ushbu chat orqali online signali yangilanadi.")

    elif command == ".off":
        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
        ONLINE_CHAT_ID = None
        ONLINE_START_TIME = None
        await event.edit("🔴 **24/7 Online rejimi to'xtatildi.**")

    elif command == ".read":
        AUTO_READ_ENABLED = True
        await event.edit("👀 **Auto-Read rejimi yoqildi!**\nBarcha shaxsiy chatlardan kelgan xabarlar kelishi bilan darhol o'qilgan qilinadi.")

    elif command == ".unread":
        AUTO_READ_ENABLED = False
        await event.edit("🙈 **Auto-Read rejimi to'xtatildi.**")

    elif command == ".info":
        system_uptime = format_duration(time.time() - BOT_START_TIME)
        
        if ONLINE_START_TIME:
            online_duration = format_duration(time.time() - ONLINE_START_TIME)
            online_status_desc = f"🟢 **Faol** ({online_duration})"
        else:
            online_status_desc = "🔴 **O'chiq**"

        auto_read_status_desc = "🟢 **Yoqilgan**" if AUTO_READ_ENABLED else "🔴 **O'chirilgan**"
        stories_count = len(db.get('story_targets', {}))

        await event.edit(
            f"ℹ️ **Tizim va Modullar Holati:**\n\n"
            f"⏳ **Bot ishlash vaqti (Uptime):** {system_uptime}\n"
            f"📶 **24/7 Online holati:** {online_status_desc}\n"
            f"👀 **Auto-Read holati:** {auto_read_status_desc}\n"
            f"📸 **Kuzatuvdagi Storylar:** {stories_count} ta"
        )

# ==================== [HTTP WEB SERVER VA YUKLANISH] ====================
async def handle_ping_web(request):
    return web.Response(text="Bot is running smoothly")

async def main():
    await client.start()
    
    server_app = web.Application()
    server_app.router.add_get('/', handle_ping_web)
    server_runner = web.AppRunner(server_app)
    await server_runner.setup()
    await web.TCPSite(server_runner, '0.0.0.0', PORT).start()
    
    asyncio.create_task(story_monitoring_loop())
    print("Barcha 3 ta modul muvaffaqiyatli ishga tushirildi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
