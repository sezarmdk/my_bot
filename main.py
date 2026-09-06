import asyncio
import os
import time
import json
import logging
from datetime import datetime
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    SendMessageTypingAction,
    ReactionEmoji,
    ReactionCustomEmoji
)
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.functions import PingDelayDisconnectRequest
from telethon.tl.functions.stories import (
    ReadStoriesRequest,
    SendReactionRequest,
    GetPeerStoriesRequest
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_1 = os.environ.get("SESSION_STRING")
SESSION_2 = os.environ.get("SESSION_STRING_2")
LOG_CHANNEL = os.environ.get("LOG_CHANNEL", "me")
PORT = int(os.environ.get("PORT", 8080))

DATA_FILE = "story_data.json"

# Foydalanuvchi taqdim etgan boshlang'ich zaxira (BACKUP)
DEFAULT_BACKUP = {
    "story_targets": {
        "7066878581": {"emoji_id": "5474531384687091878", "name": "𝗲𝗹𝗻𝘂𝗿"},
        "72113653": {"emoji_id": "5474531384687091878", "name": "️ㅤdovud"},
        "7888175146": {"emoji_id": "5469770542288478598", "name": "Blitz Samarqand"},
        "1763288488": {"emoji_id": "5474531384687091878", "name": "Мирзайев"},
        "6586461357": {"emoji_id": "5474531384687091878", "name": "ㅤㅤㅤш о х р у х ⁷"},
        "8171643760": {"emoji_id": "5474531384687091878", "name": "Xumoyun"},
        "8328563840": {"emoji_id": "5474531384687091878", "name": "Бунёд"},
        "1472444196": {"emoji_id": "5469770542288478598", "name": "Mohinur"},
        "8747110408": {"name": "сора"},
        "6235865301": {"emoji_id": "5474531384687091878", "name": "ㅤㅤㅤㅤㅤㅤㅤЗ"},
        "6762269524": {"emoji_id": "5474531384687091878", "name": "𝗸𝗵𝗮𝗺𝗿𝗼𝘇"},
        "6425818276": {"emoji_id": "5474531384687091878", "name": "-"},
        "2117668225": {"emoji_id": "5474531384687091878", "name": "Berdiyorov"},
        "6771229865": {"emoji_id": "5474531384687091878", "name": "𝑃𝑎𝑟𝑖𝑧𝑜𝑑𝑎"},
        "8750101205": {"emoji_id": "5474531384687091878", "name": "Бeрдиёров"},
        "1802315819": {"emoji_id": "5469770542288478598", "name": "Farangiz Tuychiyeva"},
        "8726838128": {"name": "khamroz"},
        "5998202318": {"name": "‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌⁠‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌Fayoz..."},
        "7438053481": {"name": "Hoff"}
    },
    "viewed_stories": {
        "7066878581": [234],
        "8171643760": [143, 144],
        "8328563840": [55],
        "1802315819": [413],
        "8726838128": [1],
        "6771229865": [362, 363, 364, 365, 366, 367, 368, 369],
        "8747110408": [143, 144, 145, 146, 147, 149],
        "6235865301": [265],
        "8750101205": [],
        "5998202318": [],
        "7438053481": [76],
        "72113653": [],
        "1763288488": [],
        "6586461357": [],
        "6762269524": [],
        "6425818276": [],
        "2117668225": [],
        "7888175146": [],
        "1472444196": []
    }
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_BACKUP

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ma'lumot saqlash xatosi: {e}")

APP_DATA = load_data()

ONLINE_RUNNING = False
ONLINE_TASK = None
AUTO_READ_ENABLED = False
FAST_PING_INTERVAL = 4

client1 = TelegramClient(StringSession(SESSION_1), API_ID, API_HASH) if SESSION_1 else TelegramClient("ob_session_1", API_ID, API_HASH)
client2 = TelegramClient(StringSession(SESSION_2), API_ID, API_HASH) if SESSION_2 else None

async def send_log(text: str):
    try:
        await client1.send_message(LOG_CHANNEL, text)
    except Exception:
        pass

# --- 24/7 DOIMIY ONLINE ---
async def ping_account(cli, step):
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
        tasks = [ping_account(client1, step)]
        if client2 and client2.is_connected():
            tasks.append(ping_account(client2, step))
        await asyncio.gather(*tasks, return_exceptions=True)
        step += 1
        await asyncio.sleep(FAST_PING_INTERVAL)

# --- ULTRA-FAST STORY KUZATUVCHISI VA LIKE BOSUVCHI ---
async def story_watcher_worker():
    while True:
        try:
            targets = APP_DATA.get("story_targets", {})
            if not targets:
                await asyncio.sleep(5)
                continue

            for target_id_str, info in list(targets.items()):
                try:
                    target_id = int(target_id_str)
                    entity = await client1.get_input_entity(target_id)
                    res = await client1(GetPeerStoriesRequest(peer=entity))

                    if not res or not res.stories:
                        continue

                    seen_list = APP_DATA["viewed_stories"].setdefault(target_id_str, [])
                    emoji_id = info.get("emoji_id")
                    target_name = info.get("name", str(target_id))

                    for story in res.stories.stories:
                        s_id = story.id
                        if s_id not in seen_list:
                            # 1. Darhol ko'rilgan deb belgilash
                            await client1(ReadStoriesRequest(peer=entity, max_id=s_id))
                            seen_list.append(s_id)
                            APP_DATA["viewed_stories"][target_id_str] = list(set(seen_list))
                            save_data(APP_DATA)

                            # 2. Reaksiya (Like / Emoji) bosish
                            try:
                                if emoji_id:
                                    reaction = [ReactionCustomEmoji(document_id=int(emoji_id))]
                                else:
                                    reaction = [ReactionEmoji(emoticon="❤️")]

                                await client1(SendReactionRequest(
                                    peer=entity,
                                    story_id=s_id,
                                    reaction=reaction
                                ))
                                react_desc = f"Maxsus Emoji ({emoji_id})" if emoji_id else "❤️"
                            except Exception as re_err:
                                react_desc = f"Ko'rildi (Reaksiya xatosi: {re_err})"

                            log_msg = (
                                f"⚡️ **YANGI STORY KO'RILDI VA LIKE BOSILDI!**\n\n"
                                f"👤 **Manba:** `{target_name}` (`{target_id}`)\n"
                                f"🆔 **Story ID:** `{s_id}`\n"
                                f"🔥 **Reaksiya:** {react_desc}\n"
                                f"⏱ **Vaqt:** `{datetime.now().strftime('%H:%M:%S')}`"
                            )
                            await send_log(log_msg)
                            logging.info(f"Story ko'rildi: {target_name} -> ID: {s_id}")

                except FloodWaitError as fe:
                    await asyncio.sleep(fe.seconds + 1)
                except Exception:
                    pass

                await asyncio.sleep(1.0)  # Har bir kuzatuvdagi manba oralig'ida tezkor tekshiruv

            await asyncio.sleep(3.0)  # Tsikl oralig'i (soniyalar ichida ushlash uchun)

        except Exception as e:
            logging.error(f"Watcher sikl xatosi: {e}")
            await asyncio.sleep(5)

# --- BUYRUQLAR ISHLOVCHISI ---
def setup_client_handlers(cli):
    @cli.on(events.NewMessage(outgoing=True))
    async def handle_commands(event):
        global ONLINE_RUNNING, ONLINE_TASK, AUTO_READ_ENABLED, APP_DATA

        text = (event.raw_text or "").strip()
        if not text.startswith("."):
            return

        parts = text.split()
        cmd = parts[0].lower()

        # 1. .story — KUZATUVGA QO'SHISH (ODAM YOKI KANAL)
        if cmd == ".story":
            target = None
            emoji_id = None

            # Reply orqali
            if event.is_reply:
                reply = await event.get_reply_message()
                target = await reply.get_sender()
                if len(parts) > 1:
                    emoji_id = parts[1]
            # ID yoki Username orqali
            elif len(parts) > 1:
                query = parts[1]
                try:
                    target = await cli.get_entity(int(query) if query.lstrip("-").isdigit() else query)
                except Exception as e:
                    await event.edit(f"❌ Manzilni topib bo'lmadi: {e}")
                    return
                if len(parts) > 2:
                    emoji_id = parts[2]
            else:
                target = await event.get_chat()

            if not target:
                await event.edit("❌ Foydalanuvchi yoki kanal topilmadi!")
                return

            t_id = str(target.id)
            t_name = getattr(target, 'title', None) or getattr(target, 'first_name', None) or str(target.id)

            APP_DATA["story_targets"][t_id] = {
                "name": t_name
            }
            if emoji_id:
                APP_DATA["story_targets"][t_id]["emoji_id"] = str(emoji_id)

            if t_id not in APP_DATA["viewed_stories"]:
                APP_DATA["viewed_stories"][t_id] = []

            save_data(APP_DATA)

            emoji_desc = f"Custom Emoji: `{emoji_id}`" if emoji_id else "Standart ❤️ Like"
            await event.edit(
                f"✅ **Kuzatuvga olindi!**\n\n"
                f"🎯 **Nomi:** `{t_name}`\n"
                f"🆔 **ID:** `{t_id}`\n"
                f"💥 **Reaksiya:** {emoji_desc}\n"
                f"⚡️ Story qo'ygan zahoti avtomatik soniyalar ichida ko'rib, like bosiladi."
            )
            await send_log(f"➕ **Kuzatuvga qo'shildi:** `{t_name}` (`{t_id}`)")

        # 2. .unstory — KUZATUVDAN CHIQARISH
        elif cmd == ".unstory":
            target_id = None
            if event.is_reply:
                reply = await event.get_reply_message()
                target_id = str(reply.sender_id)
            elif len(parts) > 1:
                query = parts[1]
                try:
                    e = await cli.get_entity(int(query) if query.lstrip("-").isdigit() else query)
                    target_id = str(e.id)
                except Exception:
                    target_id = query
            else:
                target_id = str(event.chat_id)

            if target_id in APP_DATA["story_targets"]:
                removed_name = APP_DATA["story_targets"][target_id].get("name", target_id)
                del APP_DATA["story_targets"][target_id]
                save_data(APP_DATA)
                await event.edit(f"🗑 **`{removed_name}` (`{target_id}`) kuzatuvdan o'chirildi!**")
                await send_log(f"➖ **Kuzatuvdan olib tashlandi:** `{removed_name}`")
            else:
                await event.edit("ℹ️ Ushbu manzil kuzatuv ro'yxatida yo'q.")

        # 3. .stat / .info — KUZATUV RO'YXATI VA STATISTIKA
        elif cmd in [".stat", ".info"]:
            targets = APP_DATA.get("story_targets", {})
            viewed = APP_DATA.get("viewed_stories", {})

            on_st = "🟢 Faol" if ONLINE_RUNNING else "🔴 O'chiq"
            read_st = "🟢 Faol" if AUTO_READ_ENABLED else "🔴 O'chiq"

            lines = []
            for tid, data in targets.items():
                name = data.get("name", "Noma'lum")
                em_id = data.get("emoji_id")
                em_text = f" | 🌟 `{em_id}`" if em_id else " | ❤️"
                v_count = len(viewed.get(tid, []))
                lines.append(f"• **{name}** (`{tid}`){em_text} — 👁 `{v_count}` ta")

            targets_text = "\n".join(lines) if lines else "*(Hozircha bo'sh)*"

            msg = (
                f"📊 **DOIMIY STORY KUZATUV STATISTIKASI:**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 **Jami kuzatilayotganlar:** `{len(targets)}` ta\n"
                f"📶 **24/7 Doimiy Online:** {on_st}\n"
                f"📖 **Auto-Read:** {read_st}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **Kuzatuvdagi Odamlar va Kanallar:**\n\n"
                f"{targets_text}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🛠 **Buyruqlar:**\n"
                f"• `.story [username/id] [emoji_id]`\n"
                f"• `.unstory [username/id]`\n"
                f"• `.on` / `.off`\n"
                f"• `.autoread` / `.unread`\n"
                f"• `.stat`"
            )
            await event.edit(msg)

        # 4. .backup — ZAXIRANI MATN SIFATIDA CHIQARISH
        elif cmd == ".backup":
            dump = json.dumps(APP_DATA, ensure_ascii=False)
            await event.edit(f"#STORY_BOT_BACKUP\n`{dump}`")

        # 5. ONLINE REJIM
        elif cmd == ".on":
            if ONLINE_RUNNING:
                await event.edit("ℹ️ Online rejim allaqachon faol.")
                return
            ONLINE_RUNNING = True
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

        # 6. AUTO-READ
        elif cmd == ".autoread":
            AUTO_READ_ENABLED = True
            await event.edit("🟢 **Auto-Read yoqildi!**")

        elif cmd == ".unread":
            AUTO_READ_ENABLED = False
            await event.edit("🔴 **Auto-Read o'chirildi.**")

    # KELGAN XABARLARNI O'QISH
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

# --- RENDER UCHUN WEB SERVIS ---
async def handle_ping(request):
    return web.Response(text="Story & Online Bot is Active")

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
            logging.error(f"2-profil xatosi: {e}")

    # Fon xizmati sifatida Ultra-Fast Watcher ishga tushadi
    asyncio.create_task(story_watcher_worker())

    await send_log("🚀 **Story Watcher va Userbot muvaffaqiyatli ishga tushdi!**")

    await asyncio.gather(
        client1.run_until_disconnected(),
        client2.run_until_disconnected() if client2 else asyncio.sleep(0)
    )

if __name__ == "__main__":
    asyncio.run(main())
