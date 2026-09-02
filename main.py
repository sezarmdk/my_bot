import asyncio
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import SendMessageTypingAction
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.messages import SetTypingRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
PORT = int(os.environ.get("PORT", 8080))

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_TASK = None
ONLINE_RUNNING = False

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

async def ultra_online_worker():
    global ONLINE_RUNNING
    while ONLINE_RUNNING:
        try:
            await client(UpdateStatusRequest(offline=False))
            try:
                await client(SetTypingRequest(
                    peer="me",
                    action=SendMessageTypingAction()
                ))
            except Exception:
                pass
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Worker xatosi: {e}")
            await asyncio.sleep(5)

@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_START_TIME, ONLINE_TASK, ONLINE_RUNNING

    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()

    if cmd == ".on":
        if ONLINE_RUNNING:
            await event.edit("ℹ️ **Online rejim allaqachon yoqilgan!**")
            return

        ONLINE_RUNNING = True
        ONLINE_START_TIME = time.time()
        ONLINE_TASK = asyncio.create_task(ultra_online_worker())
        await event.edit("🟢 **100% Doimiy Online yoqildi!**")

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

    elif cmd in [".info", ".stat"]:
        uptime = format_duration(time.time() - BOT_START_TIME)
        status_text = f"🟢 Faol ({format_duration(time.time() - ONLINE_START_TIME)})" if ONLINE_START_TIME else "🔴 O'chiq"

        msg = (
            f"⚡️ **24/7 ONLINE USERBOT** ⚡️\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ **Uptime:** {uptime}\n"
            f"📶 **Status:** {status_text}\n"
            f"🛠 **Buyruqlar:** `.on`, `.off`, `.info`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await event.edit(msg)

async def handle_ping(request):
    return web.Response(text="Bot is running")

async def main():
    await client.start()

    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/ping', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    logging.info("Userbot muvaffaqiyatli ulandi va ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
