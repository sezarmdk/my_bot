import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import (
    ReactionEmoji, ReactionCustomEmoji, MessageEntityCustomEmoji
)
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
        print(f"Log kanal xatosi: {e}")
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
                            if s.id not in viewed_list:
                                await client(ReadStoriesRequest(peer=ent, max_id=s.id))
                                
                                react_type = info.get("type", "emoji")
                                react_val = str(info.get("val", "❤️"))
                                
                                # Reaksiyani to'g'ri shakllantirish
                                if react_type == "custom" or react_val.isdigit():
                                    reaction = [ReactionCustomEmoji(document_id=int(react_val))]
                                else:
                                    reaction = [ReactionEmoji(emoticon=react_val)]
                                
                                try:
                                    await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=reaction))
                                except Exception as err:
                                    print(f"Custom reaksiya xatosi: {err}, standart reaksiya sinab ko'rilmoqda...")
                                    try:
                                        await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=[ReactionEmoji(emoticon='❤️')]))
                                    except: pass

                                viewed_list.append(s.id)
                                save_data(db)
                                
                                name = get_display_name(ent)
                                username = f"@{ent.username}" if hasattr(ent, 'username') and ent.username else "Mavjud emas"
                                time_str = get_uz_time().strftime('%Y-%m-%d %H:%M:%S')
                                
                                log_text = (
                                    f"🔥 **Storyga Reaksiya Bosildi!**\n\n"
                                    f"👤 **Foydalanuvchi:** {name}\n"
                                    f"🔗 **Username/ID:** `{username}` (`{ent.id}`)\n"
                                    f"✨ **Reaksiya turi:** `{react_type}`\n"
                                    f"🆔 **Emoji Document ID / Belgisi:** `{react_val}`\n"
                                    f"📊 **Story ID:** `{s.id}`\n"
                                    f"⏰ **Vaqti:** `{time_str}`"
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
    
    # 1. Emoji ID sini aniqlash uchun yordamchi buyruq: .id <emoji>
    if txt.startswith(".id") or txt.startswith(".emoji"):
        if event.message.entities:
            found_ids = []
            for e in event.message.entities:
                if isinstance(e, MessageEntityCustomEmoji):
                    found_ids.append(str(e.document_id))
            if found_ids:
                await event.edit(f"✨ **Premium Emoji ID(lar):**\n" + "\n".join([f"`{x}`" for x in found_ids]))
                return
        await event.edit("❌ Premium emoji topilmadi. Xabarga premium emoji qo'shib `.id ✨` deb yozing.")
        return

    # 2. .story buyrug'i
    if txt.startswith(".story"):
        parts = txt.split()
        if len(parts) < 2:
            await event.edit("❌ **Ishlatish:**\n`.story <ID> <premium_emoji>` yoki `.story <ID> <emoji_id>`")
            return
            
        target_arg = parts[1]
        
        try:
            ent = await client.get_entity(int(target_arg) if target_arg.lstrip('-').isdigit() else target_arg)
            
            react_type = "emoji"
            react_val = "❤️"
            
            # Xabardagi Custom Emoji entity tekshirish
            custom_id = None
            if event.message.entities:
                for ent_item in event.message.entities:
                    if isinstance(ent_item, MessageEntityCustomEmoji):
                        custom_id = str(ent_item.document_id)
                        break
            
            if custom_id:
                react_type = "custom"
                react_val = custom_id
            elif len(parts) > 2:
                extra = parts[2].strip()
                if extra.isdigit():
                    react_type = "custom"
                    react_val = extra
                else:
                    react_type = "emoji"
                    react_val = extra

            db.setdefault("story_targets", {})[str(ent.id)] = {
                "type": react_type,
                "val": react_val,
                "name": get_display_name(ent)
            }
            save_data(db)
            
            await event.edit(
                f"✅ **Muvaffaqiyatli Saqlandi!**\n\n"
                f"👤 **Foydalanuvchi:** {get_display_name(ent)} (`{ent.id}`)\n"
                f"✨ **Reaksiya Turi:** `{react_type}`\n"
                f"🔑 **Document ID / Qiymat:** `{react_val}`"
            )
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    # 3. .stop buyrug'i
    elif txt.startswith(".stop"):
        parts = txt.split()
        if len(parts) < 2:
            await event.edit("❌ Ishlatish: `.stop <user_id>`")
            return
        target_arg = parts[1]
        try:
            ent = await client.get_entity(int(target_arg) if target_arg.lstrip('-').isdigit() else target_arg)
            targets = db.get("story_targets", {})
            if str(ent.id) in targets:
                del targets[str(ent.id)]
                save_data(db)
                await event.edit(f"🛑 **Kuzatuv to'xtatildi:** {get_display_name(ent)} (`{ent.id}`)")
            else:
                await event.edit("⚠️ Bu ID ro'yxatda yo'q.")
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    # 4. .stat buyrug'i
    elif txt.startswith(".stat"):
        targets = db.get("story_targets", {})
        if not targets:
            await event.edit("📊 Hozirda kuzatuvda hech kim yo'q.")
            return
            
        text = f"📊 **Kuzatuvdagi Storylar ({len(targets)} ta):**\n\n"
        for uid, info in targets.items():
            name = info.get("name", "Noma'lum")
            rtype = info.get("type")
            rval = info.get("val")
            text += f"👤 **Ism:** {name}\n🆔 **ID:** `{uid}`\n✨ **Turi:** `{rtype}`\n🔑 **Emoji ID:** `{rval}`\n-------------------\n"
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
    print("Story Bot muvaffaqiyatli ishga tushdi!")

with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
