import asyncio
import os
import csv
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

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("ob_test_session", API_ID, API_HASH)

# ==================== [TELEPATHY EXPORT ENGINE] ====================
async def telepathy_export_members(chat_entity, event):
    """Telepathy-Community: Guruh a'zolarini CSV formatga tushirish"""
    file_name = f"telepathy_members_{chat_entity.id}.csv"
    await event.edit(f"⏳ **Telepathy:** `{chat_entity.title}` a'zolari eksport qilinmoqda...")
    
    with open(file_name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["User ID", "First Name", "Last Name", "Username", "Phone", "Is Bot", "Is Premium"])
        
        async for user in client.iter_participants(chat_entity):
            writer.writerow([
                user.id,
                user.first_name or "",
                user.last_name or "",
                f"@{user.username}" if user.username else "",
                f"+{user.phone}" if user.phone else "",
                user.bot,
                getattr(user, "premium", False)
            ])
            
    await event.delete()
    await client.send_file(
        event.chat_id,
        file_name,
        caption=f"📊 **Telepathy Eksport:** `{chat_entity.title}` a'zolari ro'yxati."
    )
    if os.path.exists(file_name):
        os.remove(file_name)

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

    # 1. .on (24/7 Doimiy Online)
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

    # 2. .off
    elif cmd == ".off":
        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
            ONLINE_TASK = None
            ONLINE_START_TIME = None
            await event.edit("🔴 **Online signal toxtatildi.**")
        else:
            await event.edit("ℹ️ Online rejimi faol emas edi.")

    # 3. .telepathy <guruh/@link> (Telepathy-Community funksiyasi)
    elif cmd in [".telepathy", ".export"]:
        target_chat = arg if arg else event.chat_id
        try:
            chat_entity = await client.get_entity(target_chat)
            if not isinstance(chat_entity, (Channel, Chat)):
                await event.edit("❌ Bu buyruq faqat guruhlar uchun ishlaydi.")
                return
            await telepathy_export_members(chat_entity, event)
        except Exception as e:
            await event.edit(f"❌ Telepathy Xatolik: `{e}`")

    # 4. .osint <id/@username> (telegram-osint-lib + tgsint-bot + Awesome-Lists)
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

        await event.edit("🔍 **OSINT modullari ishga tushirilmoqda...**")
        try:
            entity = await client.get_entity(target_val)
            
            # Agar guruh yoki kanal bo'lsa
            if isinstance(entity, (Channel, Chat)):
                c_title = getattr(entity, "title", "Noma'lum")
                c_id = entity.id
                c_user = f"@{entity.username}" if getattr(entity, "username", None) else "Yopiq"
                c_count = getattr(entity, "participants_count", "Noma'lum")
                
                res_text = (
                    f"📡 **TELEGRAM OSINT (Guruh/Kanal)**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏷 **Nomi:** `{c_title}`\n"
                    f"🆔 **ID:** `{c_id}`\n"
                    f"🔗 **Username:** {c_user}\n"
                    f"👥 **A'zolar:** `{c_count}`\n\n"
                    f"🛠 **Telepathy Eksport:** `.telepathy {entity.id}`\n"
                    f"🌐 [TGStat Analitika](https://tgstat.com/channel/@{entity.username})\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                await event.edit(res_text, link_preview=False)
                return

            if not isinstance(entity, User):
                await event.edit("⚠️ Profil aniqlanmadi.")
                return

            # telegram-osint-lib moduli: MTProto xususiyatlari
            full_data = await client(GetFullUserRequest(entity.id))
            full_user_obj = getattr(full_data, "full_user", full_data)

            u_id = entity.id
            u_first = getattr(entity, "first_name", "") or ""
            u_last = getattr(entity, "last_name", "") or ""
            u_name = f"{u_first} {u_last}".strip() or "Noma'lum"
            username = f"@{entity.username}" if getattr(entity, "username", None) else "Mavjud emas"
            phone = f"+{entity.phone}" if getattr(entity, "phone", None) else "Yashiringan"
            bio = getattr(full_user_obj, "about", None) or "Mavjud emas"
            
            photo_obj = getattr(entity, "photo", None)
            dc_id = getattr(photo_obj, "dc_id", "Mavjud emas") if photo_obj else "Mavjud emas"
            
            is_premium = "Ha ⭐️" if getattr(entity, "premium", False) else "Yo'q"
            is_bot = "Ha 🤖" if getattr(entity, "bot", False) else "Yo'q"
            is_scam = "HA (SCAM) ⚠️" if getattr(entity, "scam", False) else "Yo'q"
            is_restricted = "Ha 🚫" if getattr(entity, "restricted", False) else "Yo'q"

            # tgsint-bot moduli: Common chats
            common_titles = []
            try:
                common_chats_res = await client(GetCommonChatsRequest(user_id=entity.id, max_id=0, limit=100))
                common_titles = [c.title for c in common_chats_res.chats]
            except Exception:
                pass
            common_str = ", ".join(common_titles) if common_titles else "Umumiy guruhlar yo'q"

            # Awesome-Telegram-OSINT & The-Osint-Toolbox havolalari
            q_param = entity.username if getattr(entity, "username", None) else str(u_id)
            db_telesint = f"https://telesint.io/search?id={u_id}"
            db_tgstat = f"https://tgstat.com/user/{entity.username}" if getattr(entity, "username", None) else f"https://tgstat.com/search?q={u_id}"
            db_telemetr = f"https://telemetr.io/en/channels?search={q_param}"
            db_lyzem = f"https://lyzem.com/search?q={q_param}"
            db_intelx = f"https://intelx.io/?s={u_id}"

            report = (
                f"🛰 **5-IN-1 TELEGRAM OSINT TAHLILI** 🛰\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Ism:** `{u_name}`\n"
                f"🆔 **ID:** `{u_id}`\n"
                f"🔗 **Username:** {username}\n"
                f"📞 **Telefon:** `{phone}`\n"
                f"🌐 **DataCenter (DC):** `{dc_id}`\n"
                f"⭐️ **Premium:** {is_premium} | 🤖 **Bot:** {is_bot}\n"
                f"⚠️ **Scam:** {is_scam} | 🚫 **Cheklov:** {is_restricted}\n"
                f"📝 **Bio:** {bio}\n\n"
                f"👥 **Umumiy guruhlar ({len(common_titles)} ta):**\n"
                f"_{common_str}_\n\n"
                f"🗄 **Awesome-OSINT Repozitoriy Shlyuzlari:**\n"
                f"• [Telesint Global Chat DB]({db_telesint})\n"
                f"• [TGStat Indeksi]({db_tgstat})\n"
                f"• [Telemetr Global Search]({db_telemetr})\n"
                f"• [Lyzem Xabarlar Qidiruvi]({db_lyzem})\n"
                f"• [Intelligence X Search]({db_intelx})\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            await event.edit(report, link_preview=False)

        except Exception as e:
            await event.edit(f"❌ OSINT Xatolik: `{e}`")

    # 5. .info
    elif cmd in [".info", ".stat"]:
        uptime = format_duration(time.time() - BOT_START_TIME)
        on_desc = f"🟢 Faol ({format_duration(time.time() - ONLINE_START_TIME)})" if ONLINE_START_TIME else "🔴 Ochiq"
        
        stat_text = (
            f"📊 **OSINT USERBOT HOLATI:**\n\n"
            f"⏳ **Uptime:** {uptime}\n"
            f"📶 **24/7 Online Rejim:** {on_desc}\n"
            f"🔍 **Mavjud buyruqlar:**\n"
            f"• `.osint <id/@username>` — Profil/Guruh tahlili\n"
            f"• `.telepathy` — Guruh a'zolarini CSV faylga tushirish\n"
            f"• `.on` / `.off` — 24/7 onlayn signali"
        )
        await event.edit(stat_text)

async def handle_ping_web(request):
    return web.Response(text="OSINT Userbot is running 24/7")

async def main():
    await client.start()

    app = web.Application()
    app.router.add_get('/', handle_ping_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    logging.info("5-in-1 OSINT Userbot muvaffaqiyatli ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
