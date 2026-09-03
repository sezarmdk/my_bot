import asyncio
import os
import time
import string
import random
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
HUNTER_TASKS = []
NAME_QUEUE = asyncio.Queue()

TOTAL_COMBOS = 1872
CHECKED_COUNT = 0
FOUND_COUNT = 0
FOUND_BOTS = []

FAST_PING_INTERVAL = 4
STREAM_DELAY = 1.2

client1 = TelegramClient(StringSession(SESSION_1), API_ID, API_HASH) if SESSION_1 else TelegramClient("ob_session_1", API_ID, API_HASH)
client2 = TelegramClient(StringSession(SESSION_2), API_ID, API_HASH) if SESSION_2 else None

def generate_combinations():
    letters = string.ascii_lowercase
    all_chars = string.ascii_lowercase + string.digits
    combos = []

    # 1. Shakl: t_6bot, a_zbot
    for c1 in letters:
        for c2 in all_chars:
            combos.append(f"{c1}_{c2}bot")

    # 2. Shakl: t5_bot, az_bot
    for c1 in letters:
        for c2 in all_chars:
            combos.append(f"{c1}{c2}_bot")

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

async def wait_botfather_reply(cli, last_msg_id, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        messages = await cli.get_messages("@BotFather", limit=3)
        for m in messages:
            if m.id > last_msg_id and not m.out:
                return m
        await asyncio.sleep(0.5)
    return None

async def stream_hunter_worker(cli, worker_name):
    global HUNTER_RUNNING, CHECKED_COUNT, FOUND_COUNT, FOUND_BOTS
    bot_father = "@BotFather"

    while HUNTER_RUNNING:
        try:
            # 1. Boshlang'ich newbot yuborish
            m = await cli.send_message(bot_father, "/newbot")
            resp = await wait_botfather_reply(cli, m.id, timeout=12)

            if not resp or "Alright, a new bot" not in (resp.raw_text or ""):
                await asyncio.sleep(3)
                continue

            # 2. Bot nomi berish
            m = await cli.send_message(bot_father, f"Master_{random.randint(100, 999)}")
            resp = await wait_botfather_reply(cli, m.id, timeout=12)

            if not resp or "Good. Now let's choose a username" not in (resp.raw_text or ""):
                await asyncio.sleep(3)
                continue

            # 3. Faqat username yuborish oqimi (hech qanday conversation blokirovkasisiz)
            while HUNTER_RUNNING:
                target_username = await NAME_QUEUE.get()
                CHECKED_COUNT += 1

                m = await cli.send_message(bot_father, target_username)
                resp = await wait_botfather_reply(cli, m.id, timeout=8)
                resp_text = resp.raw_text if resp else ""

                if "Done! Congratulations" in resp_text:
                    FOUND_COUNT += 1
                    FOUND_BOTS.append(f"@{target_username}")
                    alert = (
                        f"🎉 **CHIZIQLI BOT TOPILDI VA YARATILDI!** 🎉\n\n"
                        f"🤖 **Username:** `@{target_username}`\n"
                        f"👤 **Oluvchi:** {worker_name}\n"
                        f"📦 **Ma'lumot:**\n\n{resp_text}"
                    )
                    await cli.send_message("me", alert)
                    logging.info(f"[{worker_name}] TOPILDI: @{target_username}")
                    NAME_QUEUE.task_done()
                    break

                elif not resp:
                    logging.warning(f"[{worker_name}] BotFather javob bermadi, qayta ulanmoqda...")
                    NAME_QUEUE.task_done()
                    break

                else:
                    logging.info(f"[{worker_name}] Band: @{target_username}")
                    NAME_QUEUE.task_done()
                    await asyncio.sleep(STREAM_DELAY)

        except FloodWaitError as fe:
            logging.warning(f"[{worker_name}] FloodWait: {fe.seconds}s kutish zarur")
            await asyncio.sleep(fe.seconds + 2)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"[{worker_name}] Worker xatosi: {e}")
            await asyncio.sleep(3)

def setup_client_handlers(cli):
    @cli.on(events.NewMessage(outgoing=True))
    async def handle_commands(event):
        global ONLINE_START_TIME, ONLINE_TASK, ONLINE_RUNNING
        global AUTO_READ_ENABLED, HUNTER_RUNNING, HUNTER_TASKS
        global CHECKED_COUNT, FOUND_COUNT, TOTAL_COMBOS

        try:
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
                    await event.edit("ℹ️ **Qidiruv allaqachon ketmoqda!**")
                    return

                combos = generate_combinations()
                TOTAL_COMBOS = len(combos)
                CHECKED_COUNT = 0
                while not NAME_QUEUE.empty():
                    NAME_QUEUE.get_nowait()
                for c in combos:
                    await NAME_QUEUE.put(c)

                HUNTER_RUNNING = True
                HUNTER_TASKS = [asyncio.create_task(stream_hunter_worker(client1, "Profil-1"))]
                if client2 and client2.is_connected():
                    HUNTER_TASKS.append(asyncio.create_task(stream_hunter_worker(client2, "Profil-2")))

                acc_num = 2 if (client2 and client2.is_connected()) else 1
                await event.edit(
                    f"🚀 **Chiziqli Bot Ovchi boshlandi!**\n\n"
                    f"👥 **Faol profillar:** {acc_num} ta\n"
                    f"🔢 **Kombinatsiyalar:** {TOTAL_COMBOS:,} ta\n"
                    f"⚡️ Bloklanishsiz mustaqil rejimda tekshirilmoqda."
                )

            elif cmd == ".unhunt":
                if HUNTER_RUNNING:
                    HUNTER_RUNNING = False
                    for t in HUNTER_TASKS:
                        t.cancel()
                    HUNTER_TASKS = []
                    while not NAME_QUEUE.empty():
                        NAME_QUEUE.get_nowait()
                    await event.edit("🛑 **Bot ovchi to'xtatildi.**")
                else:
                    await event.edit("ℹ️ Qidiruv faol emas.")

            elif cmd in [".stat", ".info"]:
                on_st = "🟢 Faol" if ONLINE_RUNNING else "🔴 O'chiq"
                hunt_st = "🟢 Qidirilmoqda..." if HUNTER_RUNNING else "🔴 To'xtatilgan"
                acc_num = 2 if (client2 and client2.is_connected()) else 1
                percent = (CHECKED_COUNT / TOTAL_COMBOS * 100) if TOTAL_COMBOS > 0 else 0
                remaining = max(0, TOTAL_COMBOS - CHECKED_COUNT)

                msg = (
                    f"📊 **BOT OVCHI STATISTIKASI:**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 **Holat:** {hunt_st}\n"
                    f"👥 **Ishlayotgan profillar:** {acc_num} ta\n"
                    f"🔢 **Jami kombinatsiyalar:** `{TOTAL_COMBOS:,}` ta\n"
                    f"🔍 **Tekshirildi:** `{CHECKED_COUNT:,}` ta ({percent:.2f}%)\n"
                    f"⏳ **Qoldi:** `{remaining:,}` ta\n"
                    f"🏆 **Topildi:** `{FOUND_COUNT}` ta\n"
                    f"📶 **24/7 Onlayn:** {on_st}\n"
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

        except Exception as err:
            logging.error(f"Buyruq xatoligi: {err}")

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
    return web.Response(text="Non-blocking Hunter is Running")

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
