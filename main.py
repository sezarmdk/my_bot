import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import ReactionCustomEmoji, ReactionEmoji
from telethon.tl.functions.stories import (
    GetPeerStoriesRequest, ReadStoriesRequest, SendReactionRequest
)
from telethon.utils import get_display_name

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
LOG_CHANNEL_ID = -1004327250392
PORT = int(os.environ.get("PORT", 8080))

UZ_TZ = timezone(timedelta(hours=5))
def get_uz_time(): return datetime.now(UZ_TZ)

DB_FILE = 'story_bot_db.json'

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"story_targets": {}, "viewed_stories": {}}

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_data()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def notify_log(text):
    try:
        await client.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        print(f"Log xatosi: {e}")

async def check_stories():
    while True:
        try:
            targets = list(db.get("story_targets", {}).items())
            for uid_str, info in targets:
                try:
                    uid = int(uid_str) if uid_str.lstrip('-').isdigit() else uid_str
                    ent = await client.get_entity(uid)
                    res = await client(GetPeerStoriesRequest(peer=ent))
                    
                    if hasattr(res, 'stories') and res.stories:
                        for s in res.stories.stories:
                            viewed_list = db.setdefault("viewed_stories", {}).setdefault(str(ent.id), [])
                            if s.id not in viewed_list:
                                await client(ReadStoriesRequest(peer=ent, max_id=s.id))
                                
                                emoji_id = str(info.get("emoji_id"))
                                try:
                                    await client(SendReactionRequest(
                                        peer=ent,
                                        story_id=s.id,
                                        reaction=ReactionCustomEmoji(document_id=int(emoji_id))
                                    ))
                                except Exception:
                                    try:
                                        await client(SendReactionRequest(
                                            peer=ent,
                                            story_id=s.id,
                                            reaction=ReactionEmoji(emoticon='❤️')
                                        ))
                                    except Exception: pass

                                viewed_list.append(s.id)
                                save_data(db)
                                
                                name = get_display_name(ent)
                                username = f"@{ent.username}" if getattr(ent, 'username', None) else "Mavjud emas"
                                time_str = get_uz_time().strftime('%Y-%m-%d %H:%M:%S')
                                
                                log_text = (
                                    f"🔥 **Storyga Reaksiya Bosildi!**\n\n"
                                    f"👤 **Foydalanuvchi:** {name}\n"
                                    f"🔗 **Username:** {username}\n"
                                    f"🆔 **ID:** `{ent.id}`\n"
                                    f"✨ **Emoji ID:** `{emoji_id}`\n"
                                    f"📊 **Story ID:** `{s.id}`\n"
                                    f"⏰ **Vaqti:** `{time_str}`"
                                )
                                await notify_log(log_text)
                except Exception: pass
                await asyncio.sleep(2)
        except Exception: pass
        await asyncio.sleep(10)

@client.on(events.NewMessage(outgoing=True))
async def handle_commands(event):
    global db
    txt = event.raw_text or ""
    if not txt.startswith("."):
        return

    parts = txt.strip().split()
    cmd = parts[0]

    if cmd == ".ping":
        await event.edit("🏓 **Pong! Bot faol ishlayapti.**")

    elif cmd == ".story":
        if len(parts) < 3:
            await event.edit("❌ **Ishlatish:** `.story <id/@username> <emoji_id>`")
            return
        
        target_arg = parts[1]
        emoji_id_arg = parts[2]
        
        if not emoji_id_arg.isdigit():
            await event.edit("❌ **Xato:** Emoji ID faqat raqamlardan iborat bo'lishi kerak!")
            return

        try:
            ent = await client.get_entity(int(target_arg) if target_arg.lstrip('-').isdigit() else target_arg)
            
            if str(ent.id) in db.get("viewed_stories", {}):
                db["viewed_stories"][str(ent.id)] = []

            db.setdefault("story_targets", {})[str(ent.id)] = {
                "emoji_id": emoji_id_arg,
                "name": get_display_name(ent)
            }
            save_data(db)
            
            await event.edit(
                f"✅ **Kuzatuvga olindi!**\n\n"
                f"👤 {get_display_name(ent)} (`{ent.id}`)\n"
                f"✨ **Custom Emoji ID:** `{emoji_id_arg}`"
            )
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    elif cmd == ".stop":
        if len(parts) < 2:
            await event.edit("❌ **Ishlatish:** `.stop <id/@username>`")
            return
        target_arg = parts[1]
        try:
            ent = await client.get_entity(int(target_arg) if target_arg.lstrip('-').isdigit() else target_arg)
            targets = db.get("story_targets", {})
            if str(ent.id) in targets:
                del targets[str(ent.id)]
                save_data(db)
                await event.edit(f"🛑 **To'xtatildi:** {get_display_name(ent)} (`{ent.id}`)")
            else:
                await event.edit("⚠️ Bu foydalanuvchi topilmadi.")
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    elif cmd == ".stat":
        targets = db.get("story_targets", {})
        if not targets:
            await event.edit("📊 Hozirda kuzatuvda hech kim yo'q.")
            return
            
        text = f"📊 **Kuzatuvdagilar ({len(targets)} ta):**\n\n"
        for uid, info in targets.items():
            name = info.get("name", "Noma'lum")
            emoji_id = info.get("emoji_id")
            text += f"👤 **Ism:** {name}\n🆔 **ID:** `{uid}`\n✨ **Emoji ID:** `{emoji_id}`\n-------------------\n"
        await event.edit(text)

async def handle_ping_web(request):
    return web.Response(text="OK")

async def main():
    await client.start()
    
    app = web.Application()
    app.router.add_get('/', handle_ping_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    
    asyncio.create_task(check_stories())
    print("Bot muvaffaqiyatli ishga tushdi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
