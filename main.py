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
from telethon.tl.functions.messages import SetTypingRequest, GetDialogFiltersRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
PORT = int(os.environ.get("PORT", 8080))

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_TASK = None
ONLINE_RUNNING = False

# Eng xavfsiz va uzilishsiz interval: 7 soniya
HEARTBEAT_INTERVAL = 7

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

async def ultra_heartbeat_worker():
    """Triple-Action Heartbeat: Telegram serverida mutlaq uzilishsiz onlayn ushlab turish"""
    global ONLINE_RUNNING
    while ONLINE_RUNNING:
        try:
            # 1-harakat: Rasmiy Onlayn statusi
            status_coro = client(UpdateStatusRequest(offline=False))

            # 2-harakat: Saqlangan xabarlarda yozmoqda (typing) simulyatsiyasi
            typing_coro = client(SetTypingRequest(
                peer="me",
                action=SendMessageTypingAction()
            ))

            # 3-harakat: Papkalar keshini so'rash (Ilova ochiq va faol ekanligining to'g'ridan-to'g'ri isboti)
            ping_coro = client(GetDialogFiltersRequest())

            # Uchalasi parallel bajariladi — server hech qachon shubhalanmaydi
            await asyncio.gather(status_coro, typing_coro, ping_coro, return_exceptions=True)

            await asyncio.sleep(HEARTBEAT_INTERVAL)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Heartbeat xatosi: {e}")
            await asyncio.sleep(3)

@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_START_TIME, ONLINE_TASK, ONLINE_RUNNING

    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()

    # ==================== [.on] ====================
    if cmd == ".on":
        if ONLINE_RUNNING:
            await event.edit("ℹ️ **Ultra 100% Online rejim allaqachon faol!**")
            return

        ONLINE_RUNNING = True
        ONLINE_START_TIME = time.time()
        ONLINE_TASK = asyncio.create_task(ultra_heartbeat_worker())
        await event.edit("⚡️ **Ultra 24/7 Uzluksiz Online yoqildi!**\n🛰 Usul: *Triple-Action Heartbeat (7s)*")

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
            await event.edit("ℹ️ Online rejim faol emas edi.")

    # ==================== [.info] ====================
    elif cmd in [".info", ".stat"]:
        uptime = format_duration(time.time() - BOT_START_TIME)
        status_text = f"🟢 Faol ({format_duration(time.time() - ONLINE_START_TIME)})" if ONLINE_START_TIME else "🔴 O'chiq"

        msg = (
            f"⚡️ **ULTRA ONLINE USERBOT (V2)** ⚡️\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ **Bot Uptime:** {uptime}\n"
            f"📶 **Onlayn Holati:** {status_text}\n"
            f"🛰 **Rejim:** Triple-Action Heartbeat (7s)\n"
            f"🛠 **Buyruqlar:** `.on`, `.off`, `.info`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await event.edit(msg)

async def handle_ping(request):
    return web.Response(text="Ultra 24/7 Userbot is Active")

async def main():
    await client.start()

    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/ping', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    logging.info("Ultra Userbot muvaffaqiyatli ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
