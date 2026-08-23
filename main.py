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
    return {
        "story_targets": {}, 
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
            for uid_str, info in list(db.get("story_targets", {}).items()):
                try:
                    uid = int(uid_str) if uid_str.lstrip('-').isdigit() else uid_str
                    ent = await client.get_entity(uid)
                    res = await client(GetPeerStoriesRequest(peer=ent))
                    
                    if hasattr(res, 'stories') and res.stories:
                        for s in res.stories.stories:
                            viewed_list = db.setdefault("viewed_stories", {}).setdefault(str(ent.id), [])
                            
                            # Hali baza ko'rilmagan bo'lsa (eski yoki yangi farqi yo'q, live bo'lsa kifoya)
                            if s.id not in viewed_list:
                                await client(ReadStoriesRequest(peer=ent, max_id=s.id))
                                
                                emoji_id = str(info.get("emoji_id"))
                                
                                # SendReactionRequest uchun to'g'ri format (obyekt ko'rinishida)
                                reaction_obj = ReactionCustomEmoji(document_id=int(emoji_id))
                                
                                reaction_success = False
                                try:
                                    await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=reaction_obj))
                                    reaction_success = True
                                except Exception as err:
                                    print(f"Custom reaksiya xatosi: {err}")
                                    try:
                                        await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=ReactionEmoji(emoticon='❤️')))
                                        reaction_success = True
                                    except Exception as fallback_err:
                                        print(f"Standart reaksiya ham o'tmadi: {fallback_err}")

                                if reaction_success:
                                    viewed_list.append(s.id)
                                    save_data(db)
                                    
                                    name = get_display_name(ent)
                                    username = f"@{ent.username}" if hasattr(ent, 'username') and ent.username else "Mavjud emas"
                                    time_str = get_uz_time().strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    log_text = (
                                        f"🔥 **Storyga Reaksiya Bosildi!**\n\n"
                                        f"👤 **Foydalanuvchi:** {name}\n"
                                        f"🔗 **Username:** {username}\n"
                                        f"🆔 **User ID:** `{ent.id}`\n"
                                        f"✨ **Custom Emoji ID:** `{emoji_id}`\n"
                                        f"📊 **Story ID:** `{s.id}`\n"
                                        f"⏰ **Vaqti:** `{time_str}`"
                                    )
                                    await notify_log(log_text)
                except Exception as e:
                    pass
                await asyncio.sleep(2)
        except Exception as e:
            pass
        await asyncio.sleep(10)

@client.on(events.NewMessage(from_users="me"))
async def commands(event):
    global db
    txt = event.raw_text.strip()
    parts = txt.split(maxsplit=2)
    cmd = parts[0] if parts else ""
    
    if cmd == ".story":
        if len(parts) < 3:
            await event.edit("❌ **Xato!** Ishlatish:\n`.story <username_yoki_id> <custom_emoji_id>`\n\n*Misol:* `.story @username 5470341014352136000`")
            return
            
        target_arg = parts[1]
        emoji_id_arg = parts[2].strip()
        
        if not emoji_id_arg.isdigit():
            await event.edit("❌ Custom Emoji ID faqat raqamlardan iborat bo'lishi kerak!")
            return
        
        try:
            ent = await client.get_entity(int(target_arg) if target_arg.lstrip('-').isdigit() else target_arg)
            
            # Yangitdan qo'shilganda eski ko'rilganlar tarixini tozalaymiz (qayta reaksiyani tekshirishi uchun)
            if str(ent.id) in db.get("viewed_stories", {}):
                db["viewed_stories"][str(ent.id)] = []

            db.setdefault("story_targets", {})[str(ent.id)] = {
                "emoji_id": emoji_id_arg,
                "name": get_display_name(ent)
            }
            save_data(db)
            
            await event.edit(
                f"✅ **Kuzatuvga Qo'shildi!**\n\n"
                f"👤 **Foydalanuvchi:** {get_display_name(ent)} (`{ent.id}`)\n"
                f"✨ **Custom Emoji ID:** `{emoji_id_arg}`\n"
                f"⚡️ *Hozirgi barcha aktiv storiylariga darhol reaksiya bosiladi.*"
            )
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    elif cmd == ".stop":
        if len(parts) < 2:
            await event.edit("❌ Ishlatish: `.stop <user_id_yoki_username>`")
            return
        target_arg = parts[1]
        try:
            ent = await client.get_entity(int(target_arg) if target_arg.lstrip('-').isdigit() else target_arg)
            targets = db.get("story_targets", {})
            if str(ent.id) in targets:
                del targets[str(ent.id)]
                save_data(db)
                await event.edit(f"🛑 **Muvaffaqiyatli to'xtatildi:** {get_display_name(ent)} (`{ent.id}`)")
            else:
                await event.edit("⚠️ Bu foydalanuvchi kuzatuv ro'yxatida topilmadi.")
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    elif cmd == ".stat":
        targets = db.get("story_targets", {})
        if not targets:
            await event.edit("📊 Hozirda kuzatuvda hech kim yo'q.")
            return
            
        text = f"📊 **Kuzatuvdagi Storylar ({len(targets)} ta):**\n\n"
        for uid, info in targets.items():
            name = info.get("name", "Noma'lum")
            emoji_id = info.get("emoji_id")
            text += f"👤 **Ism:** {name}\n🆔 **ID:** `{uid}`\n✨ **Emoji ID:** `{emoji_id}`\n-------------------\n"
        await event.edit(text)

async def handle_ping(request):
    return web.Response(text="Bot is running")

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
    print("Story Bot ishga tushdi!")

with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
