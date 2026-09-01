import asyncio
import json
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User, Channel, Chat
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetCommonChatsRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
PORT = int(os.environ.get("PORT", 8080))

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_CHAT_ID = None
ONLINE_TASK = None

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

def calculate_account_age(user_id):
    """telegram-osint-lib asosidagi ID xaritalash algoritmi"""
    if user_id < 100000000: return "2013 — 2015 (Juda eski)"
    elif user_id < 250000000: return "2015 — 2016"
    elif user_id < 500000000: return "2017 — 2018"
    elif user_id < 1000000000: return "2018 — 2020"
    elif user_id < 2000000000: return "2021 — 2022"
    elif user_id < 5000000000: return "2022 — 2023"
    elif user_id < 7000000000: return "2024 — 2025"
    else: return "2025 — 2026 (Yangi)"

OSINT_CACHE = {}
STORAGE_MSG_ID = None

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("ob_test_session", API_ID, API_HASH)

async def init_osint_storage():
    global OSINT_CACHE, STORAGE_MSG_ID
    try:
        async for msg in client.iter_messages("me", search="#OSINT_SUITE_DB", limit=1):
            if msg.raw_text:
                raw_json = msg.raw_text.replace("#OSINT_SUITE_DB\n", "")
                OSINT_CACHE = json.loads(raw_json)
                STORAGE_MSG_ID = msg.id
                return
        created_msg = await client.send_message("me", f"#OSINT_SUITE_DB\n{json.dumps(OSINT_CACHE, ensure_ascii=False)}")
        STORAGE_MSG_ID = created_msg.id
    except Exception as e:
        logging.error(f"Baza xatosi: {e}")

async def save_to_osint_db(user_id, data):
    global OSINT_CACHE, STORAGE_MSG_ID
    try:
        OSINT_CACHE[str(user_id)] = {
            "time": get_uz_time().strftime("%Y-%m-%d %H:%M:%S"),
            "data": data
        }
        content = f"#OSINT_SUITE_DB\n{json.dumps(OSINT_CACHE, ensure_ascii=False, indent=2)}"
        if STORAGE_MSG_ID:
            await client.edit_message("me", STORAGE_MSG_ID, content)
        else:
            msg = await client.send_message("me", content)
            STORAGE_MSG_ID = msg.id
    except Exception as e:
        logging.error(f"Sinxronlash xatosi: {e}")

@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_START_TIME, ONLINE_CHAT_ID, ONLINE_TASK

    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # ==================== [.on] ====================
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

    # ==================== [.off] ====================
    elif cmd == ".off":
        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
            ONLINE_TASK = None
            ONLINE_START_TIME = None
            await event.edit("🔴 **Online rejim toxtatildi.**")
        else:
            await event.edit("ℹ️ Online rejimi faol emas edi.")

    # ==================== [.osint] (5-in-1 Engine) ====================
    elif cmd == ".osint":
        reply = await event.get_reply_message()
        target_val = None
        if arg:
            target_val = int(arg) if arg.lstrip("-").isdigit() else arg
        elif reply:
            target_val = reply.sender_id
        else:
            await event.edit("❌ **Ishlatish:** `.osint <id/@username>` yoki xabarga reply qiling.")
            return

        await event.edit("🛰 **5 ta OSINT moduli ishga tushirilmoqda...**")
        try:
            entity = await client.get_entity(target_val)
            if isinstance(entity, (Channel, Chat)):
                # Guruh/Kanal OSINT (Telepathy uslubi)
                c_id = entity.id
                c_title = getattr(entity, 'title', 'Noma\'lum')
                c_user = f"@{entity.username}" if getattr(entity, 'username', None) else "Yopiq (Private)"
                c_members = getattr(entity, 'participants_count', 'Noma\'lum')
                
                c_report = (
                    f"📡 **TELEPATHY CHAT / CHANNEL OSINT** 📡\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷 **Nomi:** `{c_title}`\n"
                    f"🆔 **ID:** `{c_id}`\n"
                    f"🔗 **Username:** {c_user}\n"
                    f"👥 **A'zolar soni:** `{c_members}`\n"
                    f"🌐 [TGStat Analitikasi](https://tgstat.com/channel/@{entity.username})\n"
                    f"🌐 [Telemetr Ko'rsatkichlari](https://telemetr.io/en/channels?search={entity.username})\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                await event.edit(c_report, link_preview=False)
                return

            if not isinstance(entity, User):
                await event.edit("⚠️ Profil aniqlanmadi.")
                return

            # Foydalanuvchi OSINT (telegram-osint-lib + tgsint)
            full_data = await client(GetFullUserRequest(entity.id))
            full_user_obj = getattr(full_data, 'full_user', full_data)
            
            u_id = entity.id
            u_first = getattr(entity, 'first_name', '') or ""
            u_last = getattr(entity, 'last_name', '') or ""
            u_name = f"{u_first} {u_last}".strip() or "Noma'lum"
            username = f"@{entity.username}" if getattr(entity, 'username', None) else "Mavjud emas"
            phone = f"+{entity.phone}" if getattr(entity, 'phone', None) else "Yashiringan"
            bio = getattr(full_user_obj, 'about', None) or "Mavjud emas"
            
            is_premium = "Ha ⭐️" if getattr(entity, 'premium', False) else "Yo'q"
            is_bot = "Ha 🤖" if getattr(entity, 'bot', False) else "Yo'q"
            is_scam = "HA (SCAM) ⚠️" if getattr(entity, 'scam', False) else "Yo'q (Toza)"
            is_verified = "Ha ✅" if getattr(entity, 'verified', False) else "Yo'q"
            is_restricted = "Ha 🚫" if getattr(entity, 'restricted', False) else "Yo'q"
            
            photo_obj = getattr(entity, 'photo', None)
            dc_id = getattr(photo_obj, 'dc_id', 'Mavjud emas') if photo_obj else "Mavjud emas"
            reg_age = calculate_account_age(u_id)

            # Umumiy guruhlar
            common_titles = []
            try:
                common_chats_res = await client(GetCommonChatsRequest(user_id=entity.id, max_id=0, limit=100))
                common_titles = [c.title for c in common_chats_res.chats]
            except Exception:
                pass
            common_str = ", ".join(common_titles) if common_titles else "Umumiy guruhlar topilmadi"

            # Awesome-Telegram-OSINT & The-Osint-Toolbox havolalari
            q_param = entity.username if getattr(entity, 'username', None) else str(u_id)
            db_telesint = f"https://telesint.io/search?id={u_id}"
            db_tgstat = f"https://tgstat.com/user/{entity.username}" if getattr(entity, 'username', None) else f"https://tgstat.com/search?q={u_id}"
            db_telemetr = f"https://telemetr.io/en/channels?search={q_param}"
            db_lyzem = f"https://lyzem.com/search?q={q_param}"
            db_intelx = f"https://intelx.io/?s={u_id}"
            db_google = f"https://www.google.com/search?q=%22t.me/{entity.username}%22" if getattr(entity, 'username', None) else f"https://www.google.com/search?q=%22tg://user?id={u_id}%22"

            report = (
                f"🛰 **TELEGRAM FULL OSINT SUITE (5-in-1)** 🛰\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Ism:** `{u_name}`\n"
                f"🆔 **Telegram ID:** `{u_id}`\n"
                f"🔗 **Username:** {username}\n"
                f"📞 **Telefon:** `{phone}`\n"
                f"📅 **Taxminiy ro'yxat:** `{reg_age}`\n"
                f"🌐 **DataCenter (DC):** `{dc_id}`\n"
                f"⭐️ **Premium:** {is_premium} | **Verified:** {is_verified}\n"
                f"🤖 **Bot:** {is_bot} | ⚠️ **Scam/Fake:** {is_scam} | 🚫 **Cheklov:** {is_restricted}\n"
                f"📝 **Bio:** {bio}\n\n"
                f"👥 **Umumiy guruhlar ({len(common_titles)} ta):**\n"
                f"_{common_str}_\n\n"
                f"🗄 **GLOBAL OSINT BAZALARI (Awesome-OSINT):**\n"
                f"• 🌐 [Telesint Global Chat DB]({db_telesint})\n"
                f"• 📊 [TGStat Channel & Mentions]({db_tgstat})\n"
                f"• 📈 [Telemetr Analytics Engine]({db_telemetr})\n"
                f"• 🔎 [Lyzem Global Search]({db_lyzem})\n"
                f"• 🕵️ [Intelligence X Deep Search]({db_intelx})\n"
                f"• 🌍 [Google Dork Indexer]({db_google})\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💾 *Natija #OSINT_SUITE_DB bazasiga saqlandi.*"
            )
            await event.edit(report, link_preview=False)
            await save_to_osint_db(u_id, {"name": u_name, "username": username, "dc": dc_id, "common": common_titles})

        except Exception as e:
            await event.edit(f"❌ OSINT Xatolik: `{e}`")

    # ==================== [.info] ====================
    elif cmd in [".info", ".stat"]:
        uptime = format_duration(time.time() - BOT_START_TIME)
        on_desc = f"🟢 Faol ({format_duration(time.time() - ONLINE_START_TIME)})" if ONLINE_START_TIME else "🔴 Ochiq"
        db_count = len(OSINT_CACHE)
        
        stat_text = (
            f"📊 **OSINT USERBOT HOLATI:**\n\n"
            f"⏳ **Uptime:** {uptime}\n"
            f"📶 **24/7 Online Signal:** {on_desc}\n"
            f"🗄 **Bazada saqlangan profillar:** {db_count} ta\n"
            f"🛠 **Buyruqlar:** `.osint <id/@user>`, `.on`, `.off`, `.info`"
        )
        await event.edit(stat_text)

async def handle_ping_web(request):
    return web.Response(text="Supreme 5-in-1 OSINT Userbot is running 24/7")

async def main():
    await client.start()
    await init_osint_storage()

    app = web.Application()
    app.router.add_get('/', handle_ping_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    logging.info("5-in-1 OSINT Userbot muvaffaqiyatli ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
