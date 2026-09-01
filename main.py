import asyncio
import json
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from aiohttp import web, ClientSession
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetCommonChatsRequest
from telethon.utils import get_display_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", -1004327250392))
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

OSINT_CACHE = {}
STORAGE_MSG_ID = None

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("ob_test_session", API_ID, API_HASH)

async def init_osint_storage():
    global OSINT_CACHE, STORAGE_MSG_ID
    try:
        async for msg in client.iter_messages("me", search="#OSINT_DATABASE", limit=1):
            if msg.raw_text:
                raw_json = msg.raw_text.replace("#OSINT_DATABASE\n", "")
                OSINT_CACHE = json.loads(raw_json)
                STORAGE_MSG_ID = msg.id
                return
        created_msg = await client.send_message("me", f"#OSINT_DATABASE\n{json.dumps(OSINT_CACHE, ensure_ascii=False)}")
        STORAGE_MSG_ID = created_msg.id
    except Exception as e:
        logging.error(f"OSINT baza xatosi: {e}")

async def save_to_osint_db(user_id, data):
    global OSINT_CACHE, STORAGE_MSG_ID
    try:
        OSINT_CACHE[str(user_id)] = {
            "last_updated": get_uz_time().strftime("%Y-%m-%d %H:%M:%S"),
            "data": data
        }
        content = f"#OSINT_DATABASE\n{json.dumps(OSINT_CACHE, ensure_ascii=False, indent=2)}"
        if STORAGE_MSG_ID:
            await client.edit_message("me", STORAGE_MSG_ID, content)
        else:
            msg = await client.send_message("me", content)
            STORAGE_MSG_ID = msg.id
    except Exception as e:
        logging.error(f"Baza sinxronlash xatosi: {e}")

async def fetch_name_history(target_id):
    """SangMata bot orqali ismlar va usernamelar tarixini so'rash"""
    history_report = "Tarixiy yozuvlar topilmadi."
    try:
        async with client.conversation("@SangMata_beta_bot", timeout=5) as conv:
            await conv.send_message(f"/search_id {target_id}")
            resp = await conv.get_response()
            if resp and resp.text:
                history_report = resp.text.strip()
    except Exception:
        try:
            async with client.conversation("@SangMataInfo_bot", timeout=5) as conv:
                await conv.send_message(f"{target_id}")
                resp = await conv.get_response()
                if resp and resp.text:
                    history_report = resp.text.strip()
        except Exception:
            history_report = "Ismlar arxivi servisi javob bermadi yoki cheklov mavjud."
    return history_report

# ==================== [BUYRUQLAR ROUTER] ====================
@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_START_TIME, ONLINE_CHAT_ID, ONLINE_TASK

    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # 1. .on (24/7 Doimiy Online Rejimi)
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
        await event.edit("🟢 **24/7 Faol Signal Online rejimi yoqildi!**")

    # 2. .off (Online rejimni to'xtatish)
    elif cmd == ".off":
        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
            ONLINE_TASK = None
            ONLINE_START_TIME = None
            await event.edit("🔴 **Online signallash toxtatildi.**")
        else:
            await event.edit("ℹ️ Online rejimi faol emas edi.")

    # 3. .osint <id/@username> (FULL TELEGRAM OSINT SUITE)
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

        await event.edit("🛰 **FULL OSINT:** Nishon tahlil qilinmoqda (1/3)...")
        try:
            entity = await client.get_entity(target_val)
            if not isinstance(entity, User):
                await event.edit("⚠️ Ko'rsatilgan manzil shaxsiy profil emas (Guruh yoki Kanal).")
                return

            full = await client(GetFullUserRequest(entity.id))
            u_id = entity.id
            u_first = entity.first_name or ""
            u_last = entity.last_name or ""
            u_name = f"{u_first} {u_last}".strip()
            username = f"@{entity.username}" if entity.username else "Mavjud emas"
            phone = f"+{entity.phone}" if entity.phone else "Yashiringan (Maxfiy)"
            bio = full.about or "Mavjud emas"
            is_premium = "Ha ⭐️" if entity.premium else "Yo'q"
            is_bot = "Ha 🤖" if entity.bot else "Yo'q"
            is_verified = "Ha ✅" if entity.verified else "Yo'q"
            is_scam = "HA (SCAM) ⚠️" if entity.scam else "Yo'q (Ishonchli)"
            dc_id = getattr(entity.photo, 'dc_id', 'Noma\'lum') if entity.photo else "Mavjud emas"

            # 1. Umumiy guruhlar
            common_chats_res = await client(GetCommonChatsRequest(user_id=entity.id, max_id=0, limit=100))
            common_titles = [c.title for c in common_chats_res.chats]
            common_str = ", ".join(common_titles) if common_titles else "Umumiy guruhlar topilmadi"

            # 2. Ismlar va Username tarixi (SangMata & Arxiv)
            await event.edit("🛰 **FULL OSINT:** Ismlar tarixi va global bazalar tekshirilmoqda (2/3)...")
            name_history = await fetch_name_history(u_id)

            # 3. Tashqi OSINT Manbalari havolalari
            tgstat_link = f"https://tgstat.com/user/{entity.username}" if entity.username else f"https://tgstat.com/search?q={u_id}"
            telepathy_link = f"https://telesint.io/search?id={u_id}"
            global_search = f"https://lyzem.com/search?q={u_id}"

            # 4. OSINT Database ga saqlash
            user_data_record = {
                "name": u_name,
                "username": username,
                "phone": phone,
                "dc": dc_id,
                "common_chats": common_titles,
                "history": name_history
            }
            await save_to_osint_db(u_id, user_data_record)

            report = (
                f"🕵️‍♂️ **FULL TELEGRAM OSINT REPORT** 🕵️‍♂️\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Asosiy Ism:** `{u_name}`\n"
                f"🆔 **Telegram ID:** `{u_id}`\n"
                f"🔗 **Username:** {username}\n"
                f"📞 **Telefon:** `{phone}`\n"
                f"⭐️ **Premium:** {is_premium} | **Verified:** {is_verified}\n"
                f"🤖 **Bot:** {is_bot} | **Scam/Fake:** {is_scam}\n"
                f"🌐 **DataCenter (DC):** `{dc_id}`\n"
                f"📝 **Bio/Haqida:** {bio}\n\n"
                f"👥 **Umumiy guruhlar ({len(common_titles)} ta):**\n"
                f"_{common_str}_\n\n"
                f"📜 **Ism va Username Tarixi:**\n"
                f"```{name_history}```\n\n"
                f"🌐 **Global Ochiq Manbalar & Agregatorlar:**\n"
                f"• [TGStat Indeksatsiyasi]({tgstat_link})\n"
                f"• [Telesint Baza Qidiruvi]({telepathy_link})\n"
                f"• [Global Xabarlar & Mentions]({global_search})\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💾 *Ma'lumotlar avtomatik ravishda #OSINT_DATABASE xotirasiga saqlandi.*"
            )
            await event.edit(report, link_preview=False)

        except Exception as e:
            await event.edit(f"❌ OSINT Tahlilda xatolik: `{e}`")

    # 4. .info
    elif cmd in [".info", ".stat"]:
        uptime = format_duration(time.time() - BOT_START_TIME)
        on_desc = f"🟢 Faol ({format_duration(time.time() - ONLINE_START_TIME)})" if ONLINE_START_TIME else "🔴 Ochiq"
        db_count = len(OSINT_CACHE)
        
        stat_text = (
            f"📊 **OSINT USERBOT HOLATI:**\n\n"
            f"⏳ **Uptime:** {uptime}\n"
            f"📶 **24/7 Online Signal:** {on_desc}\n"
            f"🗄 **Bazada saqlangan profillar:** {db_count} ta\n"
            f"🛠 **Asosiy buyruq:** `.osint <id/@username>`"
        )
        await event.edit(stat_text)

async def handle_ping_web(request):
    return web.Response(text="Supreme OSINT Userbot is running 24/7")

async def main():
    await client.start()
    await init_osint_storage()

    app = web.Application()
    app.router.add_get('/', handle_ping_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    logging.info("Full OSINT Userbot muvaffaqiyatli ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
