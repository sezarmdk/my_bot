import asyncio
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import SendMessageTypingAction
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.functions import PingDelayDisconnectRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
PORT = int(os.environ.get("PORT", 8080))

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_TASK = None
ONLINE_RUNNING = False
AUTO_READ_ENABLED = False

# 1 soniya ham uzilmasligi uchun 4 soniyalik soket tekshiruvi
FAST_PING_INTERVAL = 4

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

async def uninterrupted_online_worker():
    """Soket darajasidagi uzluksiz 4s online saqlash mexanizmi"""
    global ONLINE_RUNNING
    step = 0
    while ONLINE_RUNNING:
        try:
            # 1. Telegram soketini majburiy tirik ushlash (MTProto Protocol Ping)
            await client(PingDelayDisconnectRequest(ping_id=int(time.time()), disconnect_delay=35))

            # 2. Navbatma-navbat engil faol harakat yuborish
            if step % 2 == 0:
                await client(UpdateStatusRequest(offline=False))
            else:
                try:
                    await client(SetTypingRequest(peer="me", action=SendMessageTypingAction()))
                except Exception:
                    pass

            step += 1
            await asyncio.sleep(FAST_PING_INTERVAL)

        except FloodWaitError as fwe:
            logging.warning(f"FloodWait: {fwe.seconds}s kutilmoqda...")
            await asyncio.sleep(fwe.seconds + 1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Keep-Alive xatosi: {e}")
            await asyncio.sleep(2)

@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_START_TIME, ONLINE_TASK, ONLINE_RUNNING, AUTO_READ_ENABLED

    try:
        text = (event.raw_text or "").strip()
        if not text.startswith("."):
            return

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()

        # ==================== [.on] ====================
        if cmd == ".on":
            if ONLINE_RUNNING:
                await event.edit("ℹ️ **Uzluksiz 4s Online rejimi allaqachon faol!**")
                return

            ONLINE_RUNNING = True
            ONLINE_START_TIME = time.time()
            if ONLINE_TASK and not ONLINE_TASK.done():
                ONLINE_TASK.cancel()
            ONLINE_TASK = asyncio.create_task(uninterrupted_online_worker())
            await event.edit("⚡️ **Uzluksiz 100% Online yoqildi!**\n🛰 Usul: *4s MTProto Socket Keep-Alive*")

        # ==================== [.off] ====================
        elif cmd == ".off":
            if ONLINE_RUNNING:
                ONLINE_RUNNING = False
                if ONLINE_TASK and not ONLINE_TASK.done():
                    ONLINE_TASK.cancel()
                ONLINE_TASK = None
                ONLINE_START_TIME = None
                try:
                    await client(UpdateStatusRequest(offline=True))
                except Exception:
                    pass
                await event.edit("🔴 **Online rejim to'xtatildi.**")
            else:
                await event.edit("ℹ️ Online rejim faol emas.")

        # ==================== [.autoread] ====================
        elif cmd == ".autoread":
            AUTO_READ_ENABLED = True
            await event.edit("🟢 **Auto-Read (Avto-o'qish) yoqildi!**")

        # ==================== [.unread] ====================
        elif cmd == ".unread":
            AUTO_READ_ENABLED = False
            await event.edit("🔴 **Auto-Read to'xtatildi.**")

        # ==================== [.info] ====================
        elif cmd in [".info", ".stat"]:
            uptime = format_duration(time.time() - BOT_START_TIME)
            on_st = f"🟢 Faol ({format_duration(time.time() - ONLINE_START_TIME)})" if ONLINE_START_TIME else "🔴 O'chiq"
            rd_st = "🟢 Yoqilgan" if AUTO_READ_ENABLED else "🔴 O'chiq"

            msg = (
                f"⚡️ **UNINTERRUPTED 24/7 ONLINE USERBOT** ⚡️\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ **Uptime:** {uptime}\n"
                f"📶 **Onlayn:** {on_st} *(4s Socket Keep-Alive)*\n"
                f"👁 **Auto-Read:** {rd_st}\n"
                f"🛠 **Buyruqlar:** `.on`, `.off`, `.autoread`, `.unread`, `.info`\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            await event.edit(msg)

    except Exception as err:
        logging.error(f"Buyruq xatoligi: {err}")

@client.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if AUTO_READ_ENABLED and event.is_private:
        try:
            await event.mark_read()
        except Exception:
            pass

async def handle_ping(request):
    return web.Response(text="Uninterrupted Online Bot is Running")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/ping', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    await client.start()
    logging.info("Userbot muvaffaqiyatli ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
