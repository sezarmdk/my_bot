import asyncio
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    ReactionEmoji,
    EmojiStatus,
    EmojiStatusEmpty,
    MessageEntityCustomEmoji
)
from telethon.tl.functions.account import UpdateStatusRequest, UpdateEmojiStatusRequest
from telethon.tl.functions.stories import (
    GetPeerStoriesRequest,
    ReadStoriesRequest,
    SendReactionRequest
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

# Auto-Status sozlamalari
AUTO_STATUS_TASK = None
AUTO_STATUS_RUNNING = False
STATUS_INTERVAL = 1.8  # 1.8 soniya oraliq

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
    return ", ".join(parts) if parts else "0 soniya"

DEFAULT_BACKUP = {
    "story_targets": {
        "7066878581": {"name": "elnur"},
        "72113653": {"name": "dovud"},
        "7888175146": {"name": "Blitz Samarqand"},
        "1763288488": {"name": "Мирзайев"},
        "6586461357": {"name": "   шохрух   "},
        "8171643760": {"name": "Xumoyun"},
        "8328563840": {"name": "Бунёд"},
        "1684342835": {"name": "N n"},
        "1472444196": {"name": "Mohinur"},
        "8747110408": {"name": "copa"},
        "6235865301": {"name": "   3"},
        "6762269524": {"name": "khamroz"},
        "6425818276": {"name": "-"},
        "2117668225": {"name": "Berdiyorov"},
        "6771229865": {"name": "Parizoda"},
        "8750101205": {"name": "Бердиёров"},
        "1802315819": {"name": "Farangiz Tuychiyeva"},
        "8726838128": {"name": "khamroz"}
    },
    "viewed_stories": {
        "7066878581": [234],
        "8171643760": [143],
        "8328563840": [55],
        "1802315819": [413],
        "8726838128": [1]
    }
}

DATA_STORAGE = DEFAULT_BACKUP.copy()
STORAGE_MSG_ID = None

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("ob_test_session", API_ID, API_HASH)

async def init_storage():
    global DATA_STORAGE, STORAGE_MSG_ID
    try:
        async for msg in client.iter_messages("me", search="#STORY_BOT_BACKUP", limit=1):
            if msg.raw_text:
                raw_json = msg.raw_text.replace("#STORY_BOT_BACKUP\n", "")
                DATA_STORAGE = json.loads(raw_json)
                STORAGE_MSG_ID = msg.id
                return
        created_msg = await client.send_message("me", f"#STORY_BOT_BACKUP\n{json.dumps(DATA_STORAGE, ensure_ascii=False)}")
        STORAGE_MSG_ID = created_msg.id
    except Exception as e:
        print(f"Xotira xatosi: {e}")

async def sync_storage():
    global DATA_STORAGE, STORAGE_MSG_ID
    try:
        content = f"#STORY_BOT_BACKUP\n{json.dumps(DATA_STORAGE, ensure_ascii=False)}"
        if STORAGE_MSG_ID:
            await client.edit_message("me", STORAGE_MSG_ID, content)
        else:
            msg = await client.send_message("me", content)
            STORAGE_MSG_ID = msg.id
    except Exception as e:
        print(f"Sync xatosi: {e}")

async def notify_log_channel(text):
    try:
        await client.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        print(f"Log kanal xatosi: {e}")

# ==================== [STORY MONITORING] ====================
async def process_single_target(uid_str, info):
    try:
        uid = int(uid_str) if uid_str.lstrip("-").isdigit() else uid_str
        peer_entity = await client.get_input_entity(uid)
        entity_full = await client.get_entity(uid)
        
        stories_result = await client(GetPeerStoriesRequest(peer=peer_entity))
        
        if hasattr(stories_result, "stories") and stories_result.stories:
            viewed_list = DATA_STORAGE.setdefault("viewed_stories", {}).setdefault(str(uid_str), [])
            new_sids = []

            for story_item in stories_result.stories.stories:
                sid = getattr(story_item, "id", None)
                if not sid:
                    continue

                if sid not in viewed_list:
                    new_sids.append(sid)
                    viewed_list.append(sid)

                    try:
                        await client(SendReactionRequest(
                            peer=peer_entity,
                            story_id=sid,
                            reaction=[ReactionEmoji(emoticon="❤️")]
                        ))
                    except Exception as like_err:
                        print(f"Layk xatosi ({uid_str} -> {sid}): {like_err}")

                    user_title = get_display_name(entity_full) or info.get("name", "Noma'lum")
                    now_str = get_uz_time().strftime("%H:%M:%S")
                    await notify_log_channel(
                        f"👁 **Yangi Story ko'rildi va Layk bosildi!** ❤️\n"
                        f"👤 **Foydalanuvchi:** {user_title} (`{uid_str}`)\n"
                        f"🆔 **Story ID:** `{sid}`\n"
                        f"🕒 **Vaqt:** {now_str}"
                    )
                    await asyncio.sleep(random.uniform(1.0, 2.0))

            if new_sids:
                max_sid = max(new_sids)
                await client(ReadStoriesRequest(peer=peer_entity, max_id=max_sid))
                await sync_storage()

    except Exception:
        pass

async def story_monitoring_loop():
    while True:
        try:
            targets = DATA_STORAGE.get("story_targets", {})
            for uid_str, info in list(targets.items()):
                await process_single_target(uid_str, info)
                await asyncio.sleep(1.0)
        except Exception as e:
            print(f"Monitoring sikli xatosi: {e}")
        await asyncio.sleep(15)

# ==================== [AUTO STATUS DVIJOKI (1.8s)] ====================
async def auto_status_rotator(emoji_ids, is_random=False):
    global AUTO_STATUS_RUNNING
    idx = 0
    while AUTO_STATUS_RUNNING:
        try:
            if is_random:
                target_id = random.choice(emoji_ids)
            else:
                target_id = emoji_ids[idx % len(emoji_ids)]
                idx += 1

            doc_id_int = int(target_id)
            await client(UpdateEmojiStatusRequest(
                emoji_status=EmojiStatus(document_id=doc_id_int)
            ))
            await asyncio.sleep(STATUS_INTERVAL)

        except FloodWaitError as fe:
            print(f"FloodWait: {fe.seconds}s kutilmoqda...")
            await asyncio.sleep(fe.seconds + 1)
        except Exception as e:
            print(f"Status xatosi: {e}")
            await asyncio.sleep(STATUS_INTERVAL)

# ==================== [BUYRUQLAR ROUTER] ====================
@client.on(events.NewMessage(outgoing=True))
async def handle_userbot_commands(event):
    global ONLINE_START_TIME, ONLINE_CHAT_ID, ONLINE_TASK, AUTO_READ_ENABLED
    global AUTO_STATUS_TASK, AUTO_STATUS_RUNNING, DATA_STORAGE
    
    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        return

    parts = text.split()
    command = parts[0].lower()

    # 1. .story <id/username>
    if command == ".story":
        if len(parts) < 2:
            await event.edit("❌ **Ishlatish:** `.story <id/@username>`\nMisol: `.story 12345678`")
            return
        
        target = parts[1]
        try:
            target_peer = int(target) if target.lstrip("-").isdigit() else target
            entity = await client.get_entity(target_peer)
            user_id_str = str(entity.id)
            user_name = get_display_name(entity) or "Target"
            
            targets = DATA_STORAGE.setdefault("story_targets", {})
            targets[user_id_str] = {"name": user_name}
            await sync_storage()
            
            await event.edit(f"✅ **Kuzatuvga qo'shildi:**\n👤 `{user_name}` (`{user_id_str}`)")
        except Exception as e:
            await event.edit(f"❌ Foydalanuvchi topilmadi: `{e}`")

    # 2. .stop <id/username>
    elif command == ".stop":
        if len(parts) < 2:
            await event.edit("❌ **Ishlatish:** `.stop <id/@username>`")
            return
        
        target = parts[1]
        try:
            target_peer = int(target) if target.lstrip("-").isdigit() else target
            entity = await client.get_entity(target_peer)
            user_id_str = str(entity.id)
            user_name = get_display_name(entity) or "Target"
            
            targets = DATA_STORAGE.get("story_targets", {})
            if user_id_str in targets:
                del targets[user_id_str]
                await sync_storage()
                await event.edit(f"🗑 **Kuzatuvdan olib tashlandi:**\n👤 `{user_name}` (`{user_id_str}`)")
            else:
                await event.edit(f"⚠️ `{user_name}` kuzatuvda mavjud emas.")
        except Exception as e:
            await event.edit(f"❌ Xatolik: `{e}`")

    # 3. .status <emojilar> (RANDOM - 1.8s)
    elif command == ".status":
        custom_emoji_ids = []
        if event.entities:
            for entity in event.entities:
                if isinstance(entity, MessageEntityCustomEmoji):
                    custom_emoji_ids.append(int(entity.document_id))

        if not custom_emoji_ids:
            auto_stat_desc = f"🟢 Faol ({STATUS_INTERVAL}s Random)" if AUTO_STATUS_RUNNING else "🔴 O'chiq"
            await event.edit(
                f"ℹ️ **Random Auto-Status yoqish:** `.status ⚡️ 🔥 👑`\n"
                f"*(Telegram Premium maxsus emojilari bilan)*\n"
                f"🎭 **Holati:** {auto_stat_desc}\n"
                f"🗑 **O'chirish:** `.unstatus`"
            )
            return

        if AUTO_STATUS_RUNNING and AUTO_STATUS_TASK:
            AUTO_STATUS_RUNNING = False
            AUTO_STATUS_TASK.cancel()

        AUTO_STATUS_RUNNING = True
        AUTO_STATUS_TASK = asyncio.create_task(auto_status_rotator(custom_emoji_ids, is_random=True))
        await event.edit(f"🎲 **Random Auto-Status yoqildi!** `{len(custom_emoji_ids)}` ta Premium emoji har {STATUS_INTERVAL}s da tasodifiy almashadi.")

    # 4. .emoji <emojilar> (KETMA-KET - 1.8s)
    elif command == ".emoji":
        custom_emoji_ids = []
        if event.entities:
            for entity in event.entities:
                if isinstance(entity, MessageEntityCustomEmoji):
                    custom_emoji_ids.append(int(entity.document_id))

        if not custom_emoji_ids:
            await event.edit("❌ **Xatolik:** Faqat **Telegram Premium** maxsus stiker/emojilaridan foydalaning!")
            return

        if AUTO_STATUS_RUNNING and AUTO_STATUS_TASK:
            AUTO_STATUS_RUNNING = False
            AUTO_STATUS_TASK.cancel()

        AUTO_STATUS_RUNNING = True
        AUTO_STATUS_TASK = asyncio.create_task(auto_status_rotator(custom_emoji_ids, is_random=False))
        await event.edit(f"🔤 **Ketma-ket Auto-Status yoqildi!** `{len(custom_emoji_ids)}` ta Premium emoji har {STATUS_INTERVAL}s da navbatma-navbat almashadi.")

    # 5. .unstatus (TO'XTATISH VA TOZALASH)
    elif command in [".unstatus", ".unstat"]:
        if AUTO_STATUS_RUNNING and AUTO_STATUS_TASK:
            AUTO_STATUS_RUNNING = False
            AUTO_STATUS_TASK.cancel()

        try:
            await client(UpdateEmojiStatusRequest(emoji_status=EmojiStatusEmpty()))
            await event.edit("🗑 **Auto-Status to'xtatildi va profil emoji statusi olib tashlandi.**")
        except Exception as e:
            await event.edit(f"❌ Xatolik: `{e}`")

    # 6. .online
    elif command == ".online":
        if not ONLINE_TASK or ONLINE_TASK.done():
            ONLINE_START_TIME = time.time()
            ONLINE_CHAT_ID = event.chat_id
            
            async def online_keep_alive():
                while True:
                    try:
                        await client(UpdateStatusRequest(offline=False))
                    except Exception:
                        pass
                    await asyncio.sleep(120)

            ONLINE_TASK = asyncio.create_task(online_keep_alive())
            await event.edit("🟢 **24/7 Doimiy Online rejimi yoqildi.**")
        else:
            await event.edit("ℹ️ Online rejimi allaqachon ishlab turibdi.")

    # 7. .offline
    elif command == ".offline":
        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
            ONLINE_TASK = None
            ONLINE_START_TIME = None
            await event.edit("🔴 **Online rejimi to'xtatildi.**")
        else:
            await event.edit("ℹ️ Online rejimi faol emas edi.")

    # 8. .autoread
    elif command == ".autoread":
        AUTO_READ_ENABLED = True
        await event.edit("👁 **Auto-Read rejimi yoqildi.**")

    # 9. .unread
    elif command == ".unread":
        AUTO_READ_ENABLED = False
        await event.edit("🙈 **Auto-Read rejimi to'xtatildi.**")

    # 10. .info
    elif command == ".info":
        system_uptime = format_duration(time.time() - BOT_START_TIME)

        if ONLINE_START_TIME:
            online_duration = format_duration(time.time() - ONLINE_START_TIME)
            online_status_desc = f"🟢 **Faol** ({online_duration})"
        else:
            online_status_desc = "🔴 **O'chiq**"

        auto_read_status_desc = "🟢 **Yoqilgan**" if AUTO_READ_ENABLED else "🔴 **O'chirilgan**"
        auto_stat_desc = f"🟢 **Faol ({STATUS_INTERVAL}s)**" if AUTO_STATUS_RUNNING else "🔴 **O'chiq**"
        stories_count = len(DATA_STORAGE.get('story_targets', {}))

        await event.edit(
            f"ℹ️ **Tizim va Modullar Holati:**\n\n"
            f"⏳ **Bot ishlash vaqti (Uptime):** {system_uptime}\n"
            f"📶 **24/7 Online holati:** {online_status_desc}\n"
            f"🎭 **Auto Emoji Status:** {auto_stat_desc}\n"
            f"👁 **Auto-Read holati:** {auto_read_status_desc}\n"
            f"📸 **Kuzatuvdagi Storylar:** {stories_count} ta"
        )

@client.on(events.NewMessage(incoming=True))
async def auto_read_incoming(event):
    if AUTO_READ_ENABLED:
        try:
            await event.mark_read()
        except Exception:
            pass

async def handle_ping_web(request):
    return web.Response(text="Bot is running smoothly")

async def main():
    await client.start()
    await init_storage()

    server_app = web.Application()
    server_app.router.add_get('/', handle_ping_web)
    server_runner = web.AppRunner(server_app)
    await server_runner.setup()
    await web.TCPSite(server_runner, '0.0.0.0', PORT).start()

    asyncio.create_task(story_monitoring_loop())
    print("Ultra tezkor Story bot ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
