import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import (
    ReactionEmoji, ReactionCustomEmoji
)
from telethon.tl.functions.stories import (
    GetPeerStoriesRequest, ReadStoriesRequest, SendReactionRequest
)
from telethon.utils import get_display_name

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
LOG_CHANNEL_ID = -1004327250392  # Siz bergan log kanal IDsi
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
    return {
        "story_targets": {},  # { "user_id": "emoji_or_id" }
        "viewed_stories": {}
    }

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_data()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def notify_log(text):
    try:
        return await client.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        print(f"Log kanalga yuborish xatosi: {e}")
        return None

async def check_stories():
    while True:
        try:
            for uid_str, reaction_val in list(db.get("story_targets", {}).items()):
                try:
                    uid = int(uid_str) if uid_str.lstrip('-').isdigit() else uid_str
                    ent = await client.get_entity(uid)
                    res = await client(GetPeerStoriesRequest(peer=ent))
                    
                    if hasattr(res, 'stories'):
                        for s in res.stories.stories:
                            viewed_list = db.setdefault("viewed_stories", {}).setdefault(str(ent.id), [])
                            if s.id not in viewed_list:
                                await client(ReadStoriesRequest(peer=ent, max_id=s.id))
                                
                                # Reaksiyani aniqlash
                                try:
                                    if reaction_val.isdigit():
                                        reaction = ReactionCustomEmoji(document_id=int(reaction_val))
                                    else:
                                        reaction = ReactionEmoji(emoticon=reaction_val)
                                        
                                    await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=reaction))
                                except Exception as err:
                                    print(f"Reaksiya xatosi: {err}")
                                    try:
                                        await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=ReactionEmoji(emoticon='❤️')))
                                    except: pass

                                viewed_list.append(s.id)
                                save_data(db)
                                
                                # Log kanalga batafsil yuborish
                                name = get_display_name(ent)
                                username = f"@{ent.username}" if hasattr(ent, 'username') and ent.username else "Mavjud emas"
                                time_str = get_uz_time().strftime('%Y-%m-%d %H:%M:%S')
                                
                                log_text = (
                                    f"📸 **Yangi Story Kuzatildi va Reaksiya Bosildi!**\n\n"
                                    f"👤 **Foydalanuvchi:** {name}\n"
                                    f"🔗 **Username:** {username}\n"
                                    f"🆔 **ID:** `{ent.id}`\n"
                                    f"✨ **Bosilgan reaksiya:** `{reaction_val}`\n"
                                    f"📊 **Story ID:** `{s.id}`\n"
                                    f"⏰ **Vaqti:** {time_str}"
                                )
                                await notify_log(log_text)
                except Exception as e:
                    pass
                await asyncio.sleep(2)
        except Exception as e:
            pass
        await asyncio.sleep(15)

@client.on(events.NewMessage(from_users="me"))
async def commands(event):
    global db
    txt = event.raw_text.strip()
    
    # Agar xabar reply (javob) qilingan bo'lsa, o'sha odamni olish
    reply = await event.get_reply_message()
    
    parts = txt.split(maxsplit=2)
    cmd = parts[0] if parts else ""
    
    if cmd == ".story":
        arg = parts[1] if len(parts) > 1 else ""
        emoji_arg = parts[2] if len(parts) > 2 else "❤️"
        
        try:
            target = None
            if reply and not arg:
                target = reply.sender_id
            elif arg.lstrip('-').isdigit():
                target = int(arg)
            elif arg:
                target = arg
            else:
                await event.edit("❌ Foydalanuvchi username yoki ID sini yozing (yoki xabarga reply qiling).")
                return

            ent = await client.get_entity(target)
            db.setdefault("story_targets", {})[str(ent.id)] = emoji_arg
            save_data(db)
            await event.edit(f"✅ **Muvaffaqiyatli qo'shildi!**\n👤 {get_display_name(ent)} (`{ent.id}`)\n✨ Reaksiya: `{emoji_arg}`")
        except Exception as e:
            await event.edit(f"❌ Xatolik yuz berdi: {e}")

    elif cmd == ".stop":
        arg = parts[1] if len(parts) > 1 else ""
        try:
            target = reply.sender_id if (reply and not arg) else (int(arg) if arg.lstrip('-').isdigit() else arg)
            ent = await client.get_entity(target)
            targets = db.get("story_targets", {})
            if str(ent.id) in targets:
                del targets[str(ent.id)]
                save_data(db)
                await event.edit(f"🛑 **To'xtatildi:** {get_display_name(ent)}")
            else:
                await event.edit("⚠️ Bu foydalanuvchi kuzatuv ro'yxatida topilmadi.")
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    elif cmd == ".stat":
        targets = db.get("story_targets", {})
        count = len(targets)
        text = f"📊 **Story Bot Statistikasi:**\n📸 Kuzatuvdagilar: `{count} ta`\n\n"
        for uid in targets:
            text += f"• `ID: {uid}` | Reaksiya: `{targets[uid]}`\n"
        await event.edit(text)

async def handle_ping(request):
    return web.Response(text="Bot is running perfectly")

async def run_web():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

async def main():
    await client.start()
    asyncio.create_task(run_web())
    asyncio.create_task(check_stories())
    print("Mukammal Story Bot ishga tushdi!")

with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
