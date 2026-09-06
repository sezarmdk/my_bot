import asyncio
import os
import time
import json
import logging
from datetime import datetime, timezone, timedelta
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
    GetPeerStoriesRequest,
    GetPinnedStoriesRequest
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_1 = os.environ.get("SESSION_STRING")
PORT = int(os.environ.get("PORT", 8080))

DATA_FILE = "story_data.json"
UZB_TZ = timezone(timedelta(hours=5))

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
        "6762269524": {"emoji_id": "5474531384687091878", "name": "𝗸𝗵𝗮𝗺𝗿oz"},
        "6425818276": {"emoji_id": "5474531384687091878", "name": "-"},
        "2117668225": {"emoji_id": "5474531384687091878", "name": "Berdiyorov"},
        "6771229865": {"emoji_id": "5474531384687091878", "name": "𝑃𝑎𝑟𝑖𝑧𝑜𝑑𝑎"},
        "8750101205": {"emoji_id": "5474531384687091878", "name": "Бeрдиёров"},
        "1802315819": {"emoji_id": "5469770542288478598", "name": "Farangiz Tuychiyeva"},
        "8726838128": {"name": "khamroz"},
        "5998202318": {"name": "‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌⁠‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌‌Fayoz..."},
        "7438053481": {"name": "Hoff"},
        "1883697098": {"name": "🕸️"},
        "1571540159": {"name": "Blitz nemis tili markazi"}
    },
    "viewed_stories": {}
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

def get_current_time():
    return datetime.now(UZB_TZ).strftime('%H:%M:%S')

async def send_log(text: str):
    target = APP_DATA.get("log_channel", "me")
    try:
        if isinstance(target, str) and (target.startswith("-100") or target.isdigit()):
            target_entity = int(target)
        else:
            target_entity = target
        await client.send_message(target_entity, text)
    except Exception as err:
        logging.warning(f"Log jo'natish xatosi: {err}")
        try:
            await client.send_message("me", f"⚠️ **Log (Kanalga yetmadi):**\n{text}")
        except Exception:
            pass

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

async def send_story_reaction(entity, story_id, emoji_id):
    # 1. Agar emoji_id bo'lsa
    if emoji_id:
        try:
            react_obj = ReactionCustomEmoji(document_id=int(emoji_id))
            await client(SendReactionRequest(peer=entity, story_id=story_id, reaction=react_obj))
            return True, f"🌟 Custom (`{emoji_id}`)"
        except FloodWaitError:
            raise
        except Exception as e:
            logging.warning(f"Custom emoji xatosi ({emoji_id}): {e}. Standart yurakka o'tilmoqda.")

    # 2. Standart yurak
    try:
        react_obj = ReactionEmoji(emoticon="❤️")
        await client(SendReactionRequest(peer=entity, story_id=story_id, reaction=react_obj))
        return True, "❤️ Like"
    except FloodWaitError:
        raise
    except Exception as e:
        return False, str(e)

# --- INDIVIDUAL TARGET UCHUN AUTO KUZATUVCHI ---
async def check_target_stories(target_id_str, info):
    try:
        target_id = int(target_id_str)
        entity = await client.get_input_entity(target_id)
        res = await client(GetPeerStoriesRequest(peer=entity))

        if not res or not getattr(res, "stories", None) or not res.stories.stories:
            return

        seen_list = APP_DATA["viewed_stories"].setdefault(target_id_str, [])
        emoji_id = info.get("emoji_id")
        target_name = info.get("name", str(target_id))

        for story in res.stories.stories:
            s_id = story.id
            if s_id not in seen_list:
                try:
                    await client(ReadStoriesRequest(peer=entity, max_id=s_id))
                    success, react_info = await send_story_reaction(entity, s_id, emoji_id)
                    if success:
                        seen_list.append(s_id)
                        APP_DATA["viewed_stories"][target_id_str] = list(set(seen_list))
                        save_data(APP_DATA)

                        log_msg = (
                            f"⚡️ **YANGI STORY ANIQLANDI VA KO'RILDI!**\n\n"
                            f"👤 **Manba:** `{target_name}`\n"
                            f"🆔 **ID:** `{target_id}`\n"
                            f"🎬 **Story ID:** `{s_id}`\n"
                            f"🔥 **Reaksiya:** {react_info}\n"
                            f"⏱ **Vaqt:** `{get_current_time()}` (Toshkent)"
                        )
                        await send_log(log_msg)
                        logging.info(f"Ko'rildi: {target_name} -> Story #{s_id}")
                except FloodWaitError as fe:
                    logging.warning(f"FloodWait: {fe.seconds}s kutilmoqda")
                    await asyncio.sleep(fe.seconds + 2)
                except Exception:
                    pass

    except FloodWaitError as fe:
        await asyncio.sleep(fe.seconds + 2)
    except Exception:
        pass

async def story_watcher_worker():
    while True:
        try:
            targets = APP_DATA.get("story_targets", {})
            if targets:
                tasks = [check_target_stories(tid, info) for tid, info in list(targets.items())]
                await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(2.0)

        except Exception as e:
            logging.error(f"Watcher xatosi: {e}")
            await asyncio.sleep(3)

@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_RUNNING, ONLINE_TASK, AUTO_READ_ENABLED, APP_DATA

    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        return

    parts = text.split()
    cmd = parts[0].lower()

    # 1. .allstory — FLOODWAIT VA SOXTA O'TIB KETISHLARSIZ XATOSIZ REAKSIYA
    if cmd == ".allstory":
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

        if not emoji_id and t_id in APP_DATA["story_targets"]:
            emoji_id = APP_DATA["story_targets"][t_id].get("emoji_id")

        await event.edit(f"🔍 **`{t_name}` ning barcha arxiv va faol storilari tekshirilmoqda...**")

        entity = await client.get_input_entity(target)
        all_story_ids = set()

        # Faol storilar
        try:
            p_res = await client(GetPeerStoriesRequest(peer=entity))
            if p_res and getattr(p_res, "stories", None) and p_res.stories.stories:
                for s in p_res.stories.stories:
                    all_story_ids.add(s.id)
        except Exception:
            pass

        # Arxivlangan (Pinned/Highlights) storilar
        offset_id = 0
        while True:
            try:
                pinned_res = await client(GetPinnedStoriesRequest(peer=entity, offset_id=offset_id, limit=50))
                if not pinned_res or not pinned_res.stories:
                    break
                for s in pinned_res.stories:
                    all_story_ids.add(s.id)
                offset_id = pinned_res.stories[-1].id
                if len(pinned_res.stories) < 50:
                    break
            except Exception:
                break

        total = len(all_story_ids)
        if total == 0:
            await event.edit(f"ℹ️ **`{t_name}` da birorta ham faol yoki arxiv story topilmadi.**")
            return

        sorted_ids = sorted(list(all_story_ids))
        success_count = 0
        react_label = f"🌟 (`{emoji_id}`)" if emoji_id else "❤️ Like"

        seen_list = APP_DATA["viewed_stories"].setdefault(t_id, [])

        for idx, s_id in enumerate(sorted_ids, 1):
            retry_attempts = 3
            reaction_ok = False

            while retry_attempts > 0:
                try:
                    # O'qish
                    await client(ReadStoriesRequest(peer=entity, max_id=s_id))
                    # Reaksiya berish
                    ok, _ = await send_story_reaction(entity, s_id, emoji_id)
                    if ok:
                        reaction_ok = True
                        success_count += 1
                        if s_id not in seen_list:
                            seen_list.append(s_id)
                    break

                except FloodWaitError as fe:
                    wait_sec = fe.seconds
                    for remaining in range(wait_sec, 0, -5):
                        try:
                            await event.edit(
                                f"⏳ **Telegram cheklovi (FloodWait)!**\n\n"
                                f"👤 **Manba:** `{t_name}`\n"
                                f"🎬 **Story:** `{idx}/{total}` ta\n"
                                f"⚠️ **Telegram serveri kutishni talab qildi:** `{remaining} soniya`..."
                            )
                        except Exception:
                            pass
                        await asyncio.sleep(min(remaining, 5))
                    retry_attempts -= 1

                except Exception as ex:
                    logging.warning(f"Story #{s_id} da xatolik: {ex}")
                    await asyncio.sleep(1)
                    retry_attempts -= 1

            # Har bir story yangilanishini xabarda ko'rsatish
            pct = (idx / total) * 100
            try:
                await event.edit(
                    f"⚡️ **STORILARGA REAKSIYA BOSILMOQDA...**\n\n"
                    f"👤 **Manba:** `{t_name}` (`{t_id}`)\n"
                    f"🎬 **Jami:** `{total}` ta story\n"
                    f"✅ **Muvaffaqiyatli:** `{success_count}` ta\n"
                    f"📊 **Jarayon:** `{idx}/{total}` ({pct:.1f}%)\n"
                    f"🔥 **Reaksiya:** {react_label}\n"
                    f"🆔 **Hozirgi ID:** `#{s_id}`"
                )
            except Exception:
                pass

            # Server bilan barqaror ishlash uchun xavfsiz pauza (Anti-Spam)
            await asyncio.sleep(1.3)

        save_data(APP_DATA)
        await event.edit(
            f"🎉 **`.allstory` TO'LIQ VA ANIQ YAKUNLANDI!**\n\n"
            f"👤 **Manba:** `{t_name}` (`{t_id}`)\n"
            f"✅ **Haqiqatda bosilgan reaksiyalar:** `{success_count}/{total}` ta\n"
            f"🔥 **Reaksiya turi:** {react_label}\n"
            f"⏱ **Vaqt:** `{get_current_time()}`"
        )
        await send_log(f"💥 **.allstory hisoboti:** `{t_name}` ning `{success_count}/{total}` ta storilariga to'liq reaksiya qo'yildi!")

    # 2. .setlog
    elif cmd == ".setlog":
        if len(parts) > 1:
            target_log = parts[1]
            try:
                ent = await client.get_entity(int(target_log) if target_log.lstrip("-").isdigit() else target_log)
                APP_DATA["log_channel"] = ent.id
                save_data(APP_DATA)
                await event.edit(f"✅ **Log kanali belgilandi:**\n📢 `{getattr(ent, 'title', ent.id)}` (`{ent.id}`)")
                await send_log("🔔 **Ushbu kanal muvaffaqiyatli Story Bot LOG kanali qilib belgilandi!**")
            except Exception as e:
                await event.edit(f"❌ Kanal topilmadi: {e}")
        else:
            current_chat = await event.get_chat()
            APP_DATA["log_channel"] = current_chat.id
            save_data(APP_DATA)
            await event.edit(f"✅ **Ushbu chat/kanal LOG kanali qilib belgilandi:**\n`{getattr(current_chat, 'title', current_chat.id)}`")

    # 3. .story
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

        APP_DATA["story_targets"][t_id] = {"name": t_name}
        if emoji_id:
            APP_DATA["story_targets"][t_id]["emoji_id"] = str(emoji_id)

        if t_id not in APP_DATA["viewed_stories"]:
            APP_DATA["viewed_stories"][t_id] = []

        save_data(APP_DATA)
        asyncio.create_task(check_target_stories(t_id, APP_DATA["story_targets"][t_id]))

        react_str = f"Maxsus Emoji (`{emoji_id}`)" if emoji_id else "❤️ Like"
        await event.edit(
            f"🎯 **Kuzatuvga olindi!**\n\n"
            f"👤 **Nomi:** `{t_name}`\n"
            f"🆔 **ID:** `{t_id}`\n"
            f"🔥 **Reaksiya:** {react_str}\n"
            f"⚡️ Yangi story soniyalar ichida avtomatik ushlanadi."
        )
        await send_log(f"➕ **Kuzatuvga qo'shildi:** `{t_name}` (`{t_id}`) | {react_str}")

    # 4. .unstory
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
            await event.edit(f"🗑 **Kuzatuvdan chiqarildi:** `{removed_name}` (`{target_id}`)")
            await send_log(f"➖ **Kuzatuvdan olib tashlandi:** `{removed_name}` (`{target_id}`)")
        else:
            await event.edit("ℹ️ Ushbu manzil kuzatuv ro'yxatida yo'q.")

    # 5. .stat / .info
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
            f"📖 **Auto-Read:** {read_st}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **FOYDALANUVCHILAR:**\n"
            f"{section_users}\n\n"
            f"📢 **KANALLAR:**\n"
            f"{section_channels}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛠 **Buyruqlar:**\n"
            f"• `.allstory [link/id]` — Barcha arxiv/faol storilarga like\n"
            f"• `.story [link/id] [emoji_id]` — Tezkor kuzatuv\n"
            f"• `.unstory [link/id]` — Kuzatuvdan chiqarish\n"
            f"• `.setlog @kanal` — Log kanalni o'rnatish\n"
            f"• `.on` / `.off` — 24/7 Online\n"
            f"• `.autoread` / `.unread` — Xabarlarni o'qish\n"
            f"• `.backup` — Zaxira nusxa"
        )
        await event.edit(msg)

    # 6. .backup
    elif cmd == ".backup":
        dump = json.dumps(APP_DATA, ensure_ascii=False)
        await event.edit(f"#STORY_BOT_BACKUP\n`{dump}`")

    # 7. .on / .off
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

    # 8. .autoread / .unread
    elif cmd == ".autoread":
        AUTO_READ_ENABLED = True
        await event.edit("🟢 **Auto-Read yoqildi!**")

    elif cmd == ".unread":
        AUTO_READ_ENABLED = False
        await event.edit("🔴 **Auto-Read to'xtatildi.**")

@client.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if AUTO_READ_ENABLED and event.is_private:
        try:
            await event.mark_read()
        except Exception:
            pass

async def handle_http_ping(request):
    return web.Response(text="Story Bot Pro Anti-Flood is Active")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_http_ping)
    app.router.add_get('/ping', handle_http_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    await client.start()
    asyncio.create_task(story_watcher_worker())

    await send_log("💎 **Story Bot Pro (Anti-Flood va Haqiqiy Reaksiya Nazorati) faollashdi!**")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
