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
PORT = int(os.environ.get("PORT", 8080))

DATA_FILE = "story_data.json"

DEFAULT_BACKUP = {
    "log_channel": os.environ.get("LOG_CHANNEL", "me"),
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
        "7438053481": {"name": "Hoff"},
        "1883697098": {"name": "🕸️"}
    },
    "viewed_stories": {
        "7066878581": [234],
        "8171643760": [143, 144],
        "8328563840": [55],
        "1802315819": [413],
        "8726838128": [1],
        "6771229865": [362, 363, 364, 365, 366, 367, 368, 369],
        "8747110408": [143, 144, 145, 146, 147, 149, 154],
        "6235865301": [265],
        "7438053481": [76]
    }
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "log_channel" not in data:
                    data["log_channel"] = DEFAULT_BACKUP["log_channel"]
                return data
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

client = TelegramClient(StringSession(SESSION_1), API_ID, API_HASH) if SESSION_1 else TelegramClient("ob_session_1", API_ID, API_HASH)

async def send_log(text: str):
    target = APP_DATA.get("log_channel", "me")
    try:
        # Raqamli kanal ID bo'lsa int formatga keltirish
        if isinstance(target, str) and (target.startswith("-100") or target.isdigit()):
            target_entity = int(target)
        else:
            target_entity = target
        await client.send_message(target_entity, text)
    except Exception as err:
        logging.warning(f"Log kanalga ({target}) yuborib bo'lmadi: {err}. Saved Messages ga tashlanmoqda.")
        try:
            await client.send_message("me", f"⚠️ **Log xatosi (Kanalga yetmadi):**\n{text}")
        except Exception:
            pass

# --- 24/7 ONLINE VORKER ---
async def ping_worker():
    global ONLINE_RUNNING
    step = 0
    while ONLINE_RUNNING:
        try:
            await client(PingDelayDisconnectRequest(ping_id=int(time.time()), disconnect_delay=35))
            if step % 2 == 0:
                await client(UpdateStatusRequest(offline=False))
            else:
                try:
                    await client(SetTypingRequest(peer="me", action=SendMessageTypingAction()))
                except Exception:
                    pass
        except Exception:
            pass
        step += 1
        await asyncio.sleep(FAST_PING_INTERVAL)

# --- XATOSIZ REAKSIYA YUBORISH (UNIVERSAL TL-OBJECT) ---
async def send_reaction_safe(entity, story_id, emoji_id):
    try:
        if emoji_id:
            reaction_obj = [ReactionCustomEmoji(document_id=int(emoji_id))]
        else:
            reaction_obj = [ReactionEmoji(emoticon="❤️")]

        await client(SendReactionRequest(
            peer=entity,
            story_id=story_id,
            reaction=reaction_obj
        ))
        return True, (f"🌟 Custom (`{emoji_id}`)" if emoji_id else "❤️ Like")
    except Exception as e:
        return False, str(e)

# --- ULTRA-FAST STORY KUZATUVCHISI ---
async def story_watcher_worker():
    while True:
        try:
            targets = APP_DATA.get("story_targets", {})
            if not targets:
                await asyncio.sleep(4)
                continue

            for target_id_str, info in list(targets.items()):
                try:
                    target_id = int(target_id_str)
                    entity = await client.get_input_entity(target_id)
                    res = await client(GetPeerStoriesRequest(peer=entity))

                    if not res or not getattr(res, "stories", None) or not res.stories.stories:
                        continue

                    seen_list = APP_DATA["viewed_stories"].setdefault(target_id_str, [])
                    emoji_id = info.get("emoji_id")
                    target_name = info.get("name", str(target_id))

                    # Barcha mavjud faol storilarni birma-bir tekshirish
                    for story in res.stories.stories:
                        s_id = story.id
                        if s_id not in seen_list:
                            # 1. Ko'rilgan deb belgilash
                            await client(ReadStoriesRequest(peer=entity, max_id=s_id))
                            seen_list.append(s_id)
                            APP_DATA["viewed_stories"][target_id_str] = list(set(seen_list))
                            save_data(APP_DATA)

                            # 2. Reaksiya qo'yish (xatoliklarsiz)
                            success, react_info = await send_reaction_safe(entity, s_id, emoji_id)

                            status_icon = "🔥" if success else "⚠️"
                            log_msg = (
                                f"⚡️ **YANGI STORY ANIQLANDI VA KO'RILDI!**\n\n"
                                f"👤 **Manba:** `{target_name}`\n"
                                f"🆔 **ID:** `{target_id}`\n"
                                f"🎬 **Story ID:** `{s_id}`\n"
                                f"{status_icon} **Reaksiya:** {react_info}\n"
                                f"⏱ **Vaqt:** `{datetime.now().strftime('%H:%M:%S')}`"
                            )
                            await send_log(log_msg)
                            logging.info(f"Ko'rildi: {target_name} ({target_id}) -> Story #{s_id}")
                            await asyncio.sleep(0.5)

                except FloodWaitError as fe:
                    await asyncio.sleep(fe.seconds + 1)
                except Exception as ex:
                    logging.debug(f"Target {target_id_str} xatosi: {ex}")

                await asyncio.sleep(0.8)

            await asyncio.sleep(2.0)

        except Exception as e:
            logging.error(f"Kuzatuv siklida xatolik: {e}")
            await asyncio.sleep(4)

# --- BUYRUQLAR ISHLOVCHISI ---
@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_RUNNING, ONLINE_TASK, AUTO_READ_ENABLED, APP_DATA

    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        return

    parts = text.split()
    cmd = parts[0].lower()

    # 1. .setlog — LOG KANALNI BELGILASH
    if cmd == ".setlog":
        if len(parts) > 1:
            target_log = parts[1]
            try:
                ent = await client.get_entity(int(target_log) if target_log.lstrip("-").isdigit() else target_log)
                APP_DATA["log_channel"] = ent.id
                save_data(APP_DATA)
                await event.edit(f"✅ **Log kanali muvaffaqiyatli saqlandi:**\n📢 `{getattr(ent, 'title', ent.id)}` (`{ent.id}`)")
                await send_log("🔔 **Ushbu kanal muvaffaqiyatli Story Bot LOG kanali qilib belgilandi!**")
            except Exception as e:
                await event.edit(f"❌ Kanalni aniqlab bo'lmadi: {e}")
        else:
            # Agar chat ichida shunchaki .setlog yozilsa
            current_chat = await event.get_chat()
            APP_DATA["log_channel"] = current_chat.id
            save_data(APP_DATA)
            await event.edit(f"✅ **Ushbu chat/kanal LOG kanali qilib belgilandi:**\n`{getattr(current_chat, 'title', current_chat.id)}`")

    # 2. .story — KUZATUVGA OLISH
    elif cmd == ".story":
        target = None
        emoji_id = None

        if event.is_reply:
            reply = await event.get_reply_message()
            target = await reply.get_sender()
            if len(parts) > 1:
                emoji_id = parts[1]
        elif len(parts) > 1:
            query = parts[1]
            try:
                target = await client.get_entity(int(query) if query.lstrip("-").isdigit() else query)
            except Exception as e:
                await event.edit(f"❌ Manzil topilmadi: {e}")
                return
            if len(parts) > 2:
                emoji_id = parts[2]
        else:
            target = await event.get_chat()

        if not target:
            await event.edit("❌ Obyekt topilmadi!")
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

        # Kuzatuvga olingan zahoti faol storilarini darhol tekshirish
        try:
            entity = await client.get_input_entity(target)
            res = await client(GetPeerStoriesRequest(peer=entity))
            if res and getattr(res, "stories", None) and res.stories.stories:
                for story in res.stories.stories:
                    if story.id not in APP_DATA["viewed_stories"][t_id]:
                        await client(ReadStoriesRequest(peer=entity, max_id=story.id))
                        await send_reaction_safe(entity, story.id, emoji_id)
                        APP_DATA["viewed_stories"][t_id].append(story.id)
                save_data(APP_DATA)
        except Exception:
            pass

        react_str = f"Maxsus Emoji (`{emoji_id}`)" if emoji_id else "❤️ Like"
        await event.edit(
            f"🎯 **Kuzatuvga muvaffaqiyatli olindi!**\n\n"
            f"👤 **Nomi:** `{t_name}`\n"
            f"🆔 **ID:** `{t_id}`\n"
            f"🔥 **Reaksiya:** {react_str}\n"
            f"⚡️ Mavjud va yangi barcha storilar soniyalar ichida ko'rib boriladi."
        )
        await send_log(f"➕ **Kuzatuvga qo'shildi:** `{t_name}` (`{t_id}`) | Reaksiya: {react_str}")

    # 3. .unstory — KUZATUVDAN O'CHIRISH
    elif cmd == ".unstory":
        target_id = None
        if event.is_reply:
            reply = await event.get_reply_message()
            target_id = str(reply.sender_id)
        elif len(parts) > 1:
            query = parts[1]
            try:
                e = await client.get_entity(int(query) if query.lstrip("-").isdigit() else query)
                target_id = str(e.id)
            except Exception:
                target_id = query
        else:
            target_id = str(event.chat_id)

        if target_id in APP_DATA["story_targets"]:
            removed_name = APP_DATA["story_targets"][target_id].get("name", target_id)
            del APP_DATA["story_targets"][target_id]
            save_data(APP_DATA)
            await event.edit(f"🗑 **Kuzatuvdan o'chirildi:** `{removed_name}` (`{target_id}`)")
            await send_log(f"➖ **Kuzatuvdan olib tashlandi:** `{removed_name}` (`{target_id}`)")
        else:
            await event.edit("ℹ️ Ushbu profil/kanal kuzatuv ro'yxatida topilmadi.")

    # 4. .stat / .info — KUZATUV RO'YXATINI ANIQLIK BILAN CHIQARISH
    elif cmd in [".stat", ".info"]:
        targets = APP_DATA.get("story_targets", {})
        viewed = APP_DATA.get("viewed_stories", {})
        log_ch = APP_DATA.get("log_channel", "me")

        on_st = "🟢 Faol" if ONLINE_RUNNING else "🔴 O'chiq"
        read_st = "🟢 Faol" if AUTO_READ_ENABLED else "🔴 O'chiq"

        channels = []
        users = []

        for tid, data in targets.items():
            name = data.get("name", "Noma'lum")
            em_id = data.get("emoji_id")
            em_badge = f"🌟 `{em_id}`" if em_id else "❤️ Like"
            v_count = len(viewed.get(tid, []))

            line = f"├ 👤 **{name}**\n│  └ 🆔 `{tid}` | {em_badge} | 👁 `{v_count}` ta"
            
            # Agar ID -100 bilan boshlansa yoki kanal bo'lsa
            if tid.startswith("-100") or tid.startswith("-"):
                channels.append(line.replace("👤", "📢"))
            else:
                users.append(line)

        section_users = "\n".join(users) if users else "*(Foydalanuvchilar yo'q)*"
        section_channels = "\n".join(channels) if channels else "*(Kanallar yo'q)*"

        msg = (
            f"📋 **STORY BOT NAZORAT PANELI**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 **Jami kuzatuvda:** `{len(targets)}` ta manba\n"
            f"📡 **Log kanali:** `{log_ch}`\n"
            f"📶 **24/7 Doimiy Online:** {on_st}\n"
            f"📖 **Xabarlarni Auto-Read:** {read_st}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **FOYDALANUVCHILAR:**\n"
            f"{section_users}\n\n"
            f"📢 **KANALLAR:**\n"
            f"{section_channels}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛠 **Tezkor buyruqlar:**\n"
            f"• `.setlog @kanal` — Log kanalni almashtirish\n"
            f"• `.story [link/id] [emoji_id]` — Kuzatuvga olish\n"
            f"• `.unstory [link/id]` — Kuzatuvdan chiqarish\n"
            f"• `.on` / `.off` — 24/7 Online\n"
            f"• `.autoread` / `.unread` — Xabarlarni o'qish\n"
            f"• `.backup` — Ma'lumotlarni nusxalash"
        )
        await event.edit(msg)

    # 5. .backup
    elif cmd == ".backup":
        dump = json.dumps(APP_DATA, ensure_ascii=False)
        await event.edit(f"#STORY_BOT_BACKUP\n`{dump}`")

    # 6. .on / .off
    elif cmd == ".on":
        if ONLINE_RUNNING:
            await event.edit("ℹ️ 24/7 Online allaqachon faol.")
            return
        ONLINE_RUNNING = True
        ONLINE_TASK = asyncio.create_task(ping_worker())
        await event.edit("🟢 **24/7 Doimiy Online rejimi yoqildi!**")

    elif cmd == ".off":
        if ONLINE_RUNNING:
            ONLINE_RUNNING = False
            if ONLINE_TASK and not ONLINE_TASK.done():
                ONLINE_TASK.cancel()
            await event.edit("🔴 **24/7 Doimiy Online to'xtatildi.**")
        else:
            await event.edit("ℹ️ Online rejim o'chiq edi.")

    # 7. .autoread / .unread
    elif cmd == ".autoread":
        AUTO_READ_ENABLED = True
        await event.edit("🟢 **Xabarlarni avtomatik o'qish (Auto-Read) yoqildi!**")

    elif cmd == ".unread":
        AUTO_READ_ENABLED = False
        await event.edit("🔴 **Xabarlarni avtomatik o'qish to'xtatildi.**")

# AUTO-READ ISHLOVCHISI
@client.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if AUTO_READ_ENABLED and event.is_private:
        try:
            await event.mark_read()
        except Exception:
            pass

# RENDER PING HTTP SERVISI
async def handle_http_ping(request):
    return web.Response(text="Story Bot Pro is Active")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_http_ping)
    app.router.add_get('/ping', handle_http_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    await client.start()
    asyncio.create_task(story_watcher_worker())

    await send_log("💎 **Mukammal Story Watcher Pro ishga tushdi va faol kuzatuvda!**")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
