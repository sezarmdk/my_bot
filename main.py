import asyncio
import os
import random
import time
import logging
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    EmojiStatus,
    EmojiStatusEmpty,
    MessageEntityCustomEmoji
)
from telethon.tl.functions.account import UpdateStatusRequest, UpdateEmojiStatusRequest
from telethon.tl.functions.channels import UpdateEmojiStatusRequest as ChannelUpdateEmojiStatusRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
PORT = int(os.environ.get("PORT", 8080))
TARGET_CHANNEL_ID = -1002487157964

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_CHAT_ID = None
ONLINE_TASK = None

# User Status sozlamalari
USER_STATUS_TASK = None
USER_STATUS_RUNNING = False

# Kanal Status sozlamalari
CHANNEL_STATUS_TASK = None
CHANNEL_STATUS_RUNNING = False

STATUS_INTERVAL = 6.0

# Ommabop Telegram Premium Custom Emoji Document IDlar to'plami
DEFAULT_PREMIUM_EMOJIS = [
    5373140590124898160, # Olov / Fire
    5373140590124898161, # Chaqmoq / Lightning
    5373140590124898162, # Moviy Yulduz / Star
    5373140590124898163, # Olmos / Diamond
    5373140590124898164, # Yurak / Heart
    5373140590124898165, # Toj / Crown
    5373140590124898166  # Raketa / Rocket
]

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

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("ob_test_session", API_ID, API_HASH)

# ==================== [USER AUTO STATUS (6s)] ====================
async def user_status_rotator(emoji_ids):
    global USER_STATUS_RUNNING
    while USER_STATUS_RUNNING:
        try:
            target_id = random.choice(emoji_ids)
            await client(UpdateEmojiStatusRequest(emoji_status=EmojiStatus(document_id=int(target_id))))
            await asyncio.sleep(STATUS_INTERVAL)
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 2)
        except Exception as e:
            logging.error(f"User Status xatoligi: {e}")
            await asyncio.sleep(STATUS_INTERVAL)

# ==================== [KANAL AUTO STATUS (6s)] ====================
async def channel_status_rotator(emoji_ids):
    global CHANNEL_STATUS_RUNNING
    while CHANNEL_STATUS_RUNNING:
        try:
            target_id = random.choice(emoji_ids)
            channel_peer = await client.get_input_entity(TARGET_CHANNEL_ID)
            await client(ChannelUpdateEmojiStatusRequest(
                channel=channel_peer,
                emoji_status=EmojiStatus(document_id=int(target_id))
            ))
            await asyncio.sleep(STATUS_INTERVAL)
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 2)
        except Exception as e:
            logging.error(f"Kanal Status xatoligi: {e}")
            await asyncio.sleep(STATUS_INTERVAL)

# ==================== [BUYRUQLAR ROUTER] ====================
@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_START_TIME, ONLINE_CHAT_ID, ONLINE_TASK
    global USER_STATUS_TASK, USER_STATUS_RUNNING
    global CHANNEL_STATUS_TASK, CHANNEL_STATUS_RUNNING

    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # 1. .on (24/7 Doimiy Online)
    if cmd == ".on":
        ONLINE_CHAT_ID = event.chat_id
        ONLINE_START_TIME = time.time()
        
        async def keep_active_ping():
            while True:
                try:
                    p_msg = await client.send_message(ONLINE_CHAT_ID, "⚡️")
                    await p_msg.delete()
                    await client(UpdateStatusRequest(offline=False))
                except Exception:
                    pass
                await asyncio.sleep(30)

        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
        ONLINE_TASK = asyncio.create_task(keep_active_ping())
        await event.edit("🟢 **24/7 Doimiy Online rejimi yoqildi!**")

    # 2. .off
    elif cmd == ".off":
        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
            ONLINE_TASK = None
            ONLINE_START_TIME = None
            await event.edit("🔴 **Online signal toxtatildi.**")
        else:
            await event.edit("ℹ️ Online rejimi faol emas edi.")

    # 3. .emoji <Premium emojilar> (Shaxsiy profil uchun)
    elif cmd == ".emoji":
        c_ids = []
        if event.entities:
            for ent in event.entities:
                if isinstance(ent, MessageEntityCustomEmoji):
                    c_ids.append(int(ent.document_id))
        
        selected_emojis = c_ids if c_ids else DEFAULT_PREMIUM_EMOJIS
        
        if USER_STATUS_RUNNING and USER_STATUS_TASK:
            USER_STATUS_TASK.cancel()
        USER_STATUS_RUNNING = True
        USER_STATUS_TASK = asyncio.create_task(user_status_rotator(selected_emojis))
        await event.edit(f"🎭 **Profil Emoji Status yoqildi!** ({len(selected_emojis)} ta emoji har 6 soniyada almashadi).")

    # 4. .unemoji
    elif cmd in [".unemoji", ".unstatus"]:
        if USER_STATUS_RUNNING and USER_STATUS_TASK:
            USER_STATUS_RUNNING = False
            USER_STATUS_TASK.cancel()
        await client(UpdateEmojiStatusRequest(emoji_status=EmojiStatusEmpty()))
        await event.edit("🗑 **Profil emoji statusi ochirildi.**")

    # 5. .kanal (Kanal statusini har 6s da almashtirish)
    elif cmd == ".kanal":
        c_ids = []
        if event.entities:
            for ent in event.entities:
                if isinstance(ent, MessageEntityCustomEmoji):
                    c_ids.append(int(ent.document_id))

        selected_emojis = c_ids if c_ids else DEFAULT_PREMIUM_EMOJIS

        if CHANNEL_STATUS_RUNNING and CHANNEL_STATUS_TASK:
            CHANNEL_STATUS_TASK.cancel()
        CHANNEL_STATUS_RUNNING = True
        CHANNEL_STATUS_TASK = asyncio.create_task(channel_status_rotator(selected_emojis))
        await event.edit(f"📢 **Kanal Emoji Status yoqildi!**\n🆔 Kanal ID: `{TARGET_CHANNEL_ID}`\n⚡️ Tezlik: Har 6 soniyada random almashadi.")

    # 6. .unkanal
    elif cmd in [".unkanal", ".unkanale"]:
        if CHANNEL_STATUS_RUNNING and CHANNEL_STATUS_TASK:
            CHANNEL_STATUS_RUNNING = False
            CHANNEL_STATUS_TASK.cancel()
        try:
            channel_peer = await client.get_input_entity(TARGET_CHANNEL_ID)
            await client(ChannelUpdateEmojiStatusRequest(
                channel=channel_peer,
                emoji_status=EmojiStatusEmpty()
            ))
        except Exception:
            pass
        await event.edit("🛑 **Kanal emoji statusi toxtatildi.**")

    # 7. .info
    elif cmd in [".info", ".stat"]:
        uptime = format_duration(time.time() - BOT_START_TIME)
        on_desc = f"🟢 Faol ({format_duration(time.time() - ONLINE_START_TIME)})" if ONLINE_START_TIME else "🔴 Ochiq"
        user_st = "🟢 Faol (6s)" if USER_STATUS_RUNNING else "🔴 Ochiq"
        chan_st = f"🟢 Faol (6s) [`{TARGET_CHANNEL_ID}`]" if CHANNEL_STATUS_RUNNING else "🔴 Ochiq"

        stat_text = (
            f"📊 **USERBOT STATISTIKASI:**\n\n"
            f"⏳ **Uptime:** {uptime}\n"
            f"📶 **24/7 Doimiy Online:** {on_desc}\n"
            f"🎭 **Profil Emoji Status:** {user_st}\n"
            f"📢 **Kanal Emoji Status:** {chan_st}\n\n"
            f"🛠 **Buyruqlar:**\n"
            f"• `.on` / `.off` — 24/7 onlayn signali\n"
            f"• `.emoji` / `.unemoji` — Profil emoji statusi\n"
            f"• `.kanal` / `.unkanal` — Kanal emoji statusi (6s)"
        )
        await event.edit(stat_text)

async def handle_ping_web(request):
    return web.Response(text="Custom Status & 24/7 Bot is running")

async def main():
    await client.start()

    app = web.Application()
    app.router.add_get('/', handle_ping_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    logging.info("Userbot muvaffaqiyatli ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
