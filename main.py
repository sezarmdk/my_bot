import asyncio
import os
import time
import string
import random
import itertools
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
SESSION_1 = os.environ.get("SESSION_STRING")
SESSION_2 = os.environ.get("SESSION_STRING_2")
PORT = int(os.environ.get("PORT", 8080))

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_TASK = None
ONLINE_RUNNING = False
AUTO_READ_ENABLED = False

HUNTER_RUNNING = False
HUNTER_TASK = None
NAME_QUEUE = asyncio.Queue()

TOTAL_COMBOS = 46656
CHECKED_COUNT = 0
FOUND_COUNT = 0
FOUND_BOTS = []

FAST_PING_INTERVAL = 4
STREAM_DELAY = 1.2  # Ban/FloodWait tushmasligi uchun optimal oraliq

client1 = TelegramClient(StringSession(SESSION_1), API_ID, API_HASH) if SESSION_1 else TelegramClient("ob_session_1", API_ID, API_HASH)
client2 = TelegramClient(StringSession(SESSION_2), API_ID, API_HASH) if SESSION_2 else None

def generate_combinations():
    chars = string.ascii_lowercase + string.digits
    combos = [''.join(p) + 'bot' for p in itertools.product(chars, repeat=3)]
    random.shuffle(combos)
    return combos

async def ping_account(cli, name, step):
    try:
        await cli(PingDelayDisconnectRequest(ping_id=int(time.time()), disconnect_delay=35))
        if step % 2 == 0:
            await cli(UpdateStatusRequest(offline=False))
        else:
            try:
                await cli(SetTypingRequest(peer="me", action=SendMessageTypingAction()))
            except Exception:
                pass
    except Exception:
        pass

async def multi_online_worker():
    global ONLINE_RUNNING
    step = 0
    while ONLINE_RUNNING:
        tasks = [ping_account(client1, "Akkaunt-1", step)]
        if client2 and client2.is_connected():
            tasks.append(ping_account(client2, "Akkaunt-2", step))
        await asyncio.gather(*tasks, return_exceptions=True)
        step += 1
        await asyncio.sleep(FAST_PING_INTERVAL)

async def stream_hunter_worker(cli, worker_name):
    """Faqat bitta /newbot berib, to'xtovsiz username oqimini yuboruvchi dvijok"""
    global HUNTER_RUNNING, CHECKED_COUNT, FOUND_COUNT, FOUND_BOTS
    bot_father = "@BotFather"

    while HUNTER_RUNNING:
        try:
            async with cli.conversation(bot_father, timeout=20) as conv:
                # 1. Boshlanishida eski holatni tozalash va yangi bot ochish
                await conv.send_message("/cancel")
                await conv.get_response()

                await conv.send_message("/newbot")
                r1 = await conv.get_response()

                if "Alright, a new bot" not in r1.raw_text:
                    await asyncio.sleep(2)
                    continue

                # 2. Botga boshlang'ich ixtiyoriy nom berish
                await conv.send_message(f"Master_{random.randint(100, 999)}")
                r2 = await conv.get_response()

                if "Good. Now let's choose a username" not in r2.raw_text:
                    await asyncio.sleep(2)
                    continue

                # 3. DOIMIY OQIM SIKLI: BotFather username so'rab turgan holatda ketma-ket yuborish
                while HUNTER_RUNNING:
                    target_username = await NAME_QUEUE.get()
                    CHECKED_COUNT += 1

                    await conv.send_message(target_username)
                    resp = await conv.get_response()
                    resp_text = resp.raw_text or ""

                    # Agar muvaffaqiyatli yaratilsa (bo'sh username topilsa)
                    if "Done! Congratulations" in resp_text:
                        FOUND_COUNT += 1
                        FOUND_BOTS.append(f"@{target_username}")
                        alert = (
                            f"🎉 **3-HARFLI BOT TOPILDI VA YARATILDI!** 🎉\n\n"
                            f"🤖 **Username:** `@{target_username}`\n"
                            f"👤 **Oluvchi:** {worker_name}\n"
                            f"📦 **BotFather Ma'lumotlari:**\n\n{resp_text}"
                        )
                        await cli.send_message("me", alert)
                        logging.info(f"[{worker_name}] TOPILDI: @{target_username}")
                        NAME_QUEUE.task_done()
                        # Yangi bot yaratilgani uchun tashqi siklga chiqib yana /newbot bilan boshlaydi
                        break

                    # Agar username band bo'lsa, BotFather o'zi qaytadan yuborishni kutadi
                    elif "already taken" in resp_text:
                        logging.info(f"[{worker_name}] Band: @{target_username}")
                        NAME_QUEUE.task_done()
                        await asyncio.sleep(STREAM_DELAY)

                    # Agar boshqa biror kutilmagan javob bersa
                    else:
                        logging.warning(f"[{worker_name}] Kutilmagan javob: {resp_text[:50]}")
                        NAME_QUEUE.task_done()
                        await conv.send_message("/cancel")
                        await conv.get_response()
                        break

        except FloodWaitError as fe:
            logging.warning(f"[{worker_name}] FloodWait: {fe.seconds}s kutilmoqda...")
            await asyncio.sleep(fe.seconds + 2)
        except asyncio.TimeoutError:
            logging.warning(f"[{worker_name}] Timeout! BotFather bilan qayta bog'lanilmoqda...")
            try:
                await cli.send_message(bot_father, "/cancel")
            except Exception:
                pass
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"[{worker_name}] Xatolik: {e}")
            await asyncio.sleep(2)

async def start_hunter_tasks():
    global HUNTER_RUNNING
    HUNTER_RUNNING = True
    tasks = [asyncio.create_task(stream_hunter_worker(client1, "Profil-1"))]
    if client2 and client2.is_connected():
        tasks.append(asyncio.create_task(stream_hunter_worker(client2, "Profil-2")))
    return tasks

def setup_client_handlers(cli):
    @cli.on(events.NewMessage(outgoing=True))
    async def handle_commands(event):
        global ONLINE_START_TIME, ONLINE_TASK, ONLINE_RUNNING
        global AUTO_READ_ENABLED, HUNTER_RUNNING, HUNTER_TASK
        global CHECKED_COUNT, FOUND_COUNT, TOTAL_COMBOS

        text = (event.raw_text or "").strip()
        if not text.startswith("."):
            return

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd == ".on":
            if ONLINE_RUNNING:
                await event.edit("ℹ️ Online rejim allaqachon faol.")
                return
            ONLINE_RUNNING = True
            ONLINE_START_TIME = time.time()
            ONLINE_TASK = asyncio.create_task(multi_online_worker())
            await event.edit("🟢 **24/7 Doimiy Online yoqildi!**")

        elif cmd == ".off":
            if ONLINE_RUNNING:
                ONLINE_RUNNING = False
                if ONLINE_TASK and not ONLINE_TASK.done():
                    ONLINE_TASK.cancel()
                await event.edit("🔴 **Online rejim to'xtatildi.**")
            else:
                await event.edit("ℹ️ Online rejim o'chiq edi.")

        elif cmd == ".hunt":
            if HUNTER_RUNNING:
                await event.edit("ℹ️ **Oqimli qidiruv jarayoni allaqachon ketmoqda!**")
                return

            combos = generate_combinations()
            TOTAL_COMBOS = len(combos)
            CHECKED_COUNT = 0
            for c in combos:
                await NAME_QUEUE.put(c)

            tasks = await start_hunter_tasks()
            HUNTER_TASK = asyncio.gather(*tasks)
            acc_num = 2 if (client2 and client2.is_connected()) else 1
            await event.edit(
                f"🚀 **Oqimli Bot Ovchi ishga tushdi!**\n\n"
                f"👥 **Faol profillar:** {acc_num} ta\n"
                f"🔢 **Kombinatsiyalar:** {TOTAL_COMBOS:,} ta\n"
                f"⚡️ **Rejim:** Uzluksiz oqim (faqat username yuboriladi, ortiqcha buyruqlarsiz)\n"
                f"🎯 Bo'sh nom topilsa token Saqlangan xabarlarga yuboriladi."
            )

        elif cmd == ".unhunt":
            if HUNTER_RUNNING:
                HUNTER_RUNNING = False
                while not NAME_QUEUE.empty():
                    NAME_QUEUE.get_nowait()
                    NAME_QUEUE.task_done()
                if HUNTER_TASK:
                    HUNTER_TASK.cancel()
                await event.edit("🛑 **Bot ovchi to'xtatildi.**")
            else:
                await event.edit("ℹ️ Qidiruv faol emas edi.")

        elif cmd in [".stat", ".info"]:
            on_st = "🟢 Faol" if ONLINE_RUNNING else "🔴 O'chiq"
            hunt_st = "🟢 Oqimli qidirilmoqda..." if HUNTER_RUNNING else "🔴 To'xtatilgan"
            acc_num = 2 if (client2 and client2.is_connected()) else 1
            percent = (CHECKED_COUNT / TOTAL_COMBOS * 100) if TOTAL_COMBOS > 0 else 0
            remaining = max(0, TOTAL_COMBOS - CHECKED_COUNT)

            msg = (
                f"📊 **OQIMLI BOT OVCHI STATISTIKASI:**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **Holat:** {hunt_st}\n"
                f"👥 **Ishlayotgan profillar:** {acc_num} ta\n"
                f"🔢 **Jami kombinatsiyalar:** `{TOTAL_COMBOS:,}` ta\n"
                f"🔍 **Tekshirildi:** `{CHECKED_COUNT:,}` ta ({percent:.2f}%)\n"
                f"⏳ **Qoldi:** `{remaining:,}` ta\n"
                f"🏆 **Topildi va olindi:** `{FOUND_COUNT}` ta\n"
                f"📶 **24/7 Doimiy Online:** {on_st}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🛠 **Buyruqlar:** `.hunt`, `.unhunt`, `.stat`, `.on`, `.off`"
            )
            await event.edit(msg)

        elif cmd == ".autoread":
            AUTO_READ_ENABLED = True
            await event.edit("🟢 **Auto-Read yoqildi!**")

        elif cmd == ".unread":
            AUTO_READ_ENABLED = False
            await event.edit("🔴 **Auto-Read o'chirildi.**")

    @cli.on(events.NewMessage(incoming=True))
    async def handle_incoming(event):
        if AUTO_READ_ENABLED and event.is_private:
            try:
                await event.mark_read()
            except Exception:
                pass

setup_client_handlers(client1)
if client2:
    setup_client_handlers(client2)

async def handle_ping(request):
    return web.Response(text="Stream Hunter is Active")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/ping', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    await client1.start()
    if client2:
        try:
            await client2.start()
        except Exception as e:
            logging.error(f"2-akkaunt xatosi: {e}")

    await asyncio.gather(
        client1.run_until_disconnected(),
        client2.run_until_disconnected() if client2 else asyncio.sleep(0)
    )

if __name__ == "__main__":
    asyncio.run(main())
