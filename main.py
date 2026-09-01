import asyncio
import json
import os
import random
import time
import logging
from datetime import datetime, timezone, timedelta
from aiohttp import web, ClientSession
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    ReactionEmoji,
    EmojiStatus,
    EmojiStatusEmpty,
    MessageEntityCustomEmoji
)
from telethon.tl.functions.account import UpdateStatusRequest, UpdateEmojiStatusRequest
from telethon.tl.functions.stories import (
    GetPeerStoriesRequest,
    ReadStoriesRequest,
    SendReactionRequest
)
from telethon.utils import get_display_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", -1004327250392))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
PORT = int(os.environ.get("PORT", 8080))

BOT_START_TIME = time.time()
ONLINE_START_TIME = None
ONLINE_CHAT_ID = None
ONLINE_TASK = None

AUTO_READ_ENABLED = False
SEEALL_ENABLED = True
EFFECT_TARGET_CHATS = set()

AUTO_STATUS_TASK = None
AUTO_STATUS_RUNNING = False
STATUS_INTERVAL = 6.0

TRACKED_CHATS = {}
ACTIVE_TRACKS = set()

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

DATA_STORAGE = {
    "story_targets": {},
    "viewed_stories": {}
}
STORAGE_MSG_ID = None

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("ob_test_session", API_ID, API_HASH)

async def init_storage():
    global DATA_STORAGE, STORAGE_MSG_ID
    try:
        async for msg in client.iter_messages("me", search="#STORY_BOT_BACKUP", limit=1):
            if msg.raw_text:
                raw_json = msg.raw_text.replace("#STORY_BOT_BACKUP\n", "")
                DATA_STORAGE = json.loads(raw_json)
                STORAGE_MSG_ID = msg.id
                return
        created_msg = await client.send_message("me", f"#STORY_BOT_BACKUP\n{json.dumps(DATA_STORAGE, ensure_ascii=False)}")
        STORAGE_MSG_ID = created_msg.id
    except Exception as e:
        logging.error(f"Xotira xatosi: {e}")

async def sync_storage():
    global DATA_STORAGE, STORAGE_MSG_ID
    try:
        content = f"#STORY_BOT_BACKUP\n{json.dumps(DATA_STORAGE, ensure_ascii=False)}"
        if STORAGE_MSG_ID:
            await client.edit_message("me", STORAGE_MSG_ID, content)
        else:
            msg = await client.send_message("me", content)
            STORAGE_MSG_ID = msg.id
    except Exception as e:
        logging.error(f"Sync xatosi: {e}")

async def notify_log_channel(text, file=None):
    try:
        if file:
            await client.send_file(LOG_CHANNEL_ID, file, caption=text)
        else:
            await client.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        logging.error(f"Log kanal xatosi: {e}")

async def ask_gemini_ai(prompt_text, system_instruction=None):
    if not GEMINI_KEY:
        return "⚠️ Gemini API kaliti topilmadi! Render'dagi Environment Variables bo'limiga GEMINI_API_KEY o'zgaruvchisini qo'shing."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    sys_inst = system_instruction or "Sen foydalanuvchining shaxsiy aqlli yordamchisisan. Har qanday savolga o'zbek tilida aniq, tushunarli va do'stona javob ber."
    
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "systemInstruction": {"parts": [{"text": sys_inst}]}
    }
    
    try:
        async with ClientSession() as session:
            async with session.post(url, json=payload, timeout=25) as resp:
                data = await resp.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                elif "error" in data:
                    return f"⚠️ AI Xatolik: {data['error'].get('message', 'Noma\\'lum xato')}"
                return "⚠️ AI javob bera olmadi."
    except Exception as e:
        return f"⚠️ Ulanish xatosi: {e}"

async def check_stories():
    targets = DATA_STORAGE.get("story_targets", {})
    for uid_str, info in list(targets.items()):
        try:
            uid = int(uid_str) if uid_str.lstrip("-").isdigit() else uid_str
            peer = await client.get_input_entity(uid)
            full_user = await client.get_entity(uid)
            
            res = await client(GetPeerStoriesRequest(peer=peer))
            if hasattr(res, "stories") and res.stories:
                viewed = DATA_STORAGE.setdefault("viewed_stories", {}).setdefault(str(uid_str), [])
                new_sids = []
                for st in res.stories.stories:
                    sid = getattr(st, "id", None)
                    if sid and sid not in viewed:
                        new_sids.append(sid)
                        viewed.append(sid)
                        try:
                            await client(SendReactionRequest(peer=peer, story_id=sid, reaction=[ReactionEmoji(emoticon="❤️")]))
                        except Exception:
                            pass
                        
                        u_name = get_display_name(full_user) or info.get("name", "Target")
                        now_s = get_uz_time().strftime("%H:%M:%S")
                        await notify_log_channel(
                            f"👁 **Tezkor Story ko'rildi va ❤️ bosildi!**\n"
                            f"👤 **Foydalanuvchi:** {u_name} (`{uid_str}`)\n"
                            f"🆔 **Story ID:** `{sid}`\n"
                            f"🕒 **Vaqt:** {now_s}"
                        )
                if new_sids:
                    await client(ReadStoriesRequest(peer=peer, max_id=max(new_sids)))
                    await sync_storage()
        except Exception:
            pass
        await asyncio.sleep(0.5)

async def story_monitoring_loop():
    while True:
        try:
            if DATA_STORAGE.get("story_targets"):
                await check_stories()
        except Exception as e:
            logging.error(f"Story sikl: {e}")
        await asyncio.sleep(4)

async def auto_status_rotator(emoji_ids):
    global AUTO_STATUS_RUNNING
    while AUTO_STATUS_RUNNING:
        try:
            target_id = random.choice(emoji_ids)
            await client(UpdateEmojiStatusRequest(emoji_status=EmojiStatus(document_id=int(target_id))))
            await asyncio.sleep(STATUS_INTERVAL)
        except FloodWaitError as fe:
            await asyncio.sleep(fe.seconds + 2)
        except Exception as e:
            logging.error(f"Status xato: {e}")
            await asyncio.sleep(STATUS_INTERVAL)

@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global ONLINE_START_TIME, ONLINE_CHAT_ID, ONLINE_TASK, AUTO_READ_ENABLED
    global AUTO_STATUS_TASK, AUTO_STATUS_RUNNING, DATA_STORAGE, SEEALL_ENABLED
    global TRACKED_CHATS, ACTIVE_TRACKS, EFFECT_TARGET_CHATS

    text = (event.raw_text or "").strip()
    if not text.startswith("."):
        if event.chat_id in EFFECT_TARGET_CHATS:
            asyncio.create_task(animate_fire_lightning(event))
        return

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

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

    elif cmd == ".off":
        if ONLINE_TASK and not ONLINE_TASK.done():
            ONLINE_TASK.cancel()
            ONLINE_TASK = None
            ONLINE_START_TIME = None
            await event.edit("🔴 **Online signallash to'xtatildi.**")
        else:
            await event.edit("ℹ️ Online rejimi faol emas edi.")

    elif cmd == ".ai":
        reply_to = await event.get_reply_message()
        full_query = arg
        if reply_to and reply_to.text:
            full_query = f"Quyidagi xabarni hisobga olib javob ber:\n\"{reply_to.text}\"\n\nSavol: {arg}" if arg else reply_to.text
        
        if not full_query:
            await event.edit("❌ **Ishlatish:** `.ai <savol>` yoki xabarga reply qilib `.ai`")
            return

        await event.edit("🤖 *Gemini AI o'ylamoqda...*")
        answer = await ask_gemini_ai(full_query)
        await event.edit(f"🤖 **Gemini Yordamchi:**\n\n{answer}")

    elif cmd == ".story":
        if not arg:
            await event.edit("❌ **Ishlatish:** `.story <id/@username>`")
            return
        try:
            target_p = int(arg) if arg.lstrip("-").isdigit() else arg
            ent = await client.get_entity(target_p)
            u_id = str(ent.id)
            u_name = get_display_name(ent) or "Target"
            DATA_STORAGE.setdefault("story_targets", {})[u_id] = {"name": u_name}
            await sync_storage()
            await event.edit(f"✅ **Kuzatuvga qo'shildi:**\n👤 `{u_name}` (`{u_id}`)")
        except Exception as e:
            await event.edit(f"❌ Xatolik: `{e}`")

    elif cmd == ".unstory":
        if not arg:
            await event.edit("❌ **Ishlatish:** `.unstory <id/@username>`")
            return
        try:
            target_p = int(arg) if arg.lstrip("-").isdigit() else arg
            ent = await client.get_entity(target_p)
            u_id = str(ent.id)
            targets = DATA_STORAGE.get("story_targets", {})
            if u_id in targets:
                del targets[u_id]
                await sync_storage()
                await event.edit(f"🗑 **Kuzatuvdan o'chirildi:** `{get_display_name(ent)}`")
            else:
                await event.edit("⚠️ Bu foydalanuvchi kuzatuvda yo'q.")
        except Exception as e:
            await event.edit(f"❌ Xatolik: `{e}`")

    elif cmd == ".track":
        if not arg:
            await event.edit("❌ **Ishlatish:** `.track <id/@username>`")
            return
        try:
            target_p = int(arg) if arg.lstrip("-").isdigit() else arg
            ent = await client.get_entity(target_p)
            c_id = ent.id
            ACTIVE_TRACKS.add(c_id)
            TRACKED_CHATS[c_id] = []
            
            await event.edit(f"⏳ `{get_display_name(ent)}` yozishmalari bazasi yuklanmoqda...")
            async for m in client.iter_messages(c_id, limit=300):
                if m.text:
                    sender = "Men" if m.out else get_display_name(ent)
                    t_str = m.date.astimezone(UZ_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    TRACKED_CHATS[c_id].insert(0, {
                        "id": m.id, "sender": sender, "text": m.text, "time": t_str, "status": "Original"
                    })
            await event.edit(f"🕵️‍♂️ **Real-vaqt kuzatuv boshlandi!**\n👤 `{get_display_name(ent)}`")
        except Exception as e:
            await event.edit(f"❌ Xatolik: `{e}`")

    elif cmd == ".untrack":
        try:
            c_id = event.chat_id
            if arg:
                target_p = int(arg) if arg.lstrip("-").isdigit() else arg
                ent = await client.get_entity(target_p)
                c_id = ent.id

            if c_id in ACTIVE_TRACKS:
                ACTIVE_TRACKS.remove(c_id)
                msgs = TRACKED_CHATS.get(c_id, [])
                file_name = f"chat_track_{c_id}.json"
                with open(file_name, "w", encoding="utf-8") as f:
                    json.dump(msgs, f, ensure_ascii=False, indent=2)
                
                await event.delete()
                await client.send_file(event.chat_id, file_name, caption=f"📁 **Yozishmalar fayli ({len(msgs)} ta xabar):**")
                if os.path.exists(file_name): os.remove(file_name)
            else:
                await event.edit("⚠️ Ushbu chat kuzatuvda emas edi.")
        except Exception as e:
            await event.edit(f"❌ Xatolik: `{e}`")

    elif cmd == ".seeall":
        SEEALL_ENABLED = not SEEALL_ENABLED
        st = "🟢 Yoqildi" if SEEALL_ENABLED else "🔴 O'chirildi"
        await event.edit(f"👁 **SeeAll (Log kanalga saqlash):** {st}")

    elif cmd == ".autoread":
        AUTO_READ_ENABLED = True
        await event.edit("🟢 **Auto-Read yoqildi.**")
    elif cmd == ".unread":
        AUTO_READ_ENABLED = False
        await event.edit("🔴 **Auto-Read to'xtatildi.**")

    elif cmd == ".emoji":
        c_ids = []
        if event.entities:
            for ent in event.entities:
                if isinstance(ent, MessageEntityCustomEmoji):
                    c_ids.append(int(ent.document_id))
        if not c_ids:
            await event.edit("❌ Telegram Premium maxsus emojilarni kiriting (Har 6 soniyada random almashadi).")
            return
        if AUTO_STATUS_RUNNING and AUTO_STATUS_TASK:
            AUTO_STATUS_TASK.cancel()
        AUTO_STATUS_RUNNING = True
        AUTO_STATUS_TASK = asyncio.create_task(auto_status_rotator(c_ids))
        await event.edit(f"🎭 **Auto Emoji Status yoqildi!** ({len(c_ids)} ta emoji har 6 soniyada).")

    elif cmd in [".unemoji", ".unstatus", ".unstat"]:
        if AUTO_STATUS_RUNNING and AUTO_STATUS_TASK:
            AUTO_STATUS_RUNNING = False
            AUTO_STATUS_TASK.cancel()
        await client(UpdateEmojiStatusRequest(emoji_status=EmojiStatusEmpty()))
        await event.edit("🗑 **Emoji status tozalab tashlandi.**")

    elif cmd == ".xabar":
        try:
            target_p = int(arg) if arg.lstrip("-").isdigit() else (arg if arg else event.chat_id)
            ent = await client.get_entity(target_p)
            EFFECT_TARGET_CHATS.add(ent.id)
            await event.edit(f"⚡️🔥 **Maxsus animatsiya yoqildi:** `{get_display_name(ent)}`")
        except Exception as e:
            await event.edit(f"❌ Xatolik: `{e}`")
    elif cmd == ".xabarx":
        c_id = event.chat_id
        if c_id in EFFECT_TARGET_CHATS: EFFECT_TARGET_CHATS.remove(c_id)
        await event.edit("🛑 **Animatsiyali rejim o'chirildi.**")

    elif cmd in [".quote", ".q"]:
        reply = await event.get_reply_message()
        if not reply or not reply.text:
            await event.edit("❌ Matnli xabarga reply qiling!")
            return
        author = get_display_name(await reply.get_sender()) or "Noma'lum"
        q_text = f"╔══════════════════╗\n  ❝ {reply.text} ❞\n  — *{author}*\n╚══════════════════╝"
        await event.edit(q_text)

    elif cmd == ".purge":
        count = int(arg) if arg.isdigit() else 10
        deleted = 0
        async for m in client.iter_messages(event.chat_id, limit=count * 2):
            if m.out:
                await m.delete()
                deleted += 1
                if deleted >= count: break
        del_msg = await client.send_message(event.chat_id, f"🧹 `{deleted}` ta xabaringiz o'chirildi.")
        await asyncio.sleep(2)
        await del_msg.delete()

    elif cmd in [".info", ".stat"]:
        uptime = format_duration(time.time() - BOT_START_TIME)
        on_desc = f"🟢 Faol ({format_duration(time.time() - ONLINE_START_TIME)})" if ONLINE_START_TIME else "🔴 O'chiq"
        st_count = len(DATA_STORAGE.get("story_targets", {}))
        tr_count = len(ACTIVE_TRACKS)
        
        stat_text = (
            f"📊 **USERBOT STATISTIKASI:**\n\n"
            f"⏳ **Uptime:** {uptime}\n"
            f"📶 **24/7 Signal Online:** {on_desc}\n"
            f"🎭 **Auto Emoji Status:** {'🟢 Faol (6s)' if AUTO_STATUS_RUNNING else '🔴 O\\'chiq'}\n"
            f"👁 **Auto-Read:** {'🟢 Yoqilgan' if AUTO_READ_ENABLED else '🔴 O\\'chiq'}\n"
            f"📸 **Kuzatuvdagi Storylar:** {st_count} ta\n"
            f"🕵️‍♂️ **Track qilinayotgan chatlar:** {tr_count} ta\n"
            f"🛡 **SeeAll Log:** {'🟢 Faol' if SEEALL_ENABLED else '🔴 O\\'chiq'}"
        )
        await event.edit(stat_text)

async def animate_fire_lightning(event):
    original_text = event.raw_text
    frames = ["⚡️", "🔥 ⚡️", "⚡️ 🔥 ⚡️", f"🔥 {original_text} 🔥", f"⚡️🔥 {original_text} 🔥⚡️"]
    for f in frames:
        try:
            await event.edit(f)
            await asyncio.sleep(0.3)
        except Exception:
            break

@client.on(events.MessageDeleted)
async def handle_deleted_msgs(event):
    for mid in event.deleted_ids:
        for cid, msgs in TRACKED_CHATS.items():
            for m in msgs:
                if m["id"] == mid:
                    m["status"] = "O'CHIRILDI ❌"
                    m["deleted_at"] = get_uz_time().strftime("%H:%M:%S")
        
        if SEEALL_ENABLED:
            await notify_log_channel(f"🗑 **Xabar o'chirildi!**\n🆔 Xabar ID: `{mid}`\n🕒 Vaqt: `{get_uz_time().strftime('%H:%M:%S')}`")

@client.on(events.MessageEdited)
async def handle_edited_msgs(event):
    if event.chat_id in ACTIVE_TRACKS:
        msgs = TRACKED_CHATS.setdefault(event.chat_id, [])
        msgs.append({
            "id": event.id, "sender": "Edited", "text": f"[Yangi]: {event.text}",
            "time": get_uz_time().strftime("%Y-%m-%d %H:%M:%S"), "status": "TAHRIRLANDI ✏️"
        })
    if SEEALL_ENABLED and event.is_private:
        sender = await event.get_sender()
        name = get_display_name(sender) if sender else "Noma'lum"
        await notify_log_channel(
            f"✏️ **Xabar tahrirlandi!**\n👤 **Kim:** {name}\n📝 **Yangi matn:** {event.text}\n🕒 Vaqt: `{get_uz_time().strftime('%H:%M:%S')}`"
        )

@client.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if AUTO_READ_ENABLED and event.is_private:
        try:
            await event.mark_read()
        except Exception:
            pass

    if event.chat_id in ACTIVE_TRACKS and event.text:
        sender = await event.get_sender()
        s_name = get_display_name(sender) if sender else "User"
        TRACKED_CHATS.setdefault(event.chat_id, []).append({
            "id": event.id, "sender": s_name, "text": event.text,
            "time": get_uz_time().strftime("%Y-%m-%d %H:%M:%S"), "status": "Yangi"
        })

async def handle_ping_web(request):
    return web.Response(text="Supreme Assistant Bot is running 24/7")

async def main():
    await client.start()
    await init_storage()

    app = web.Application()
    app.router.add_get('/', handle_ping_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    asyncio.create_task(story_monitoring_loop())
    logging.info("Supreme Userbot muvaffaqiyatli ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
