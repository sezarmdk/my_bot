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
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", -1003669608470))
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

async def notify(text):
    try:
        return await client.send_message(CHANNEL_ID, text)
    except Exception as e:
        print(f"Kanalga yuborish xatosi: {e}")
        return None

async def parse_target_arg(arg):
    if arg.lstrip('-').isdigit():
        return int(arg)
    return arg

# Story kuzatish va mos emoji bilan like bosish loopi
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
                                
                                # Reaksiyani aniqlash (Emoji ID yoki oddiy emoji matni)
                                try:
                                    if reaction_val.isdigit():
                                        # Agar raqam bo'lsa - Premium Custom Emoji ID
                                        reaction = ReactionCustomEmoji(document_id=int(reaction_val))
                                    else:
                                        # Agar oddiy belgi bo'lsa (masalan 🔥, ❤️)
                                        reaction = ReactionEmoji(emoticon=reaction_val)
                                        
                                    await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=reaction))
                                except Exception as err:
                                    print(f"Reaksiya bosish xatosi: {err}")
                                    # Xatolik bo'lsa standart yurak bosib ketadi
                                    try:
                                        await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=ReactionEmoji(emoticon='❤️')) )
                                    except: pass

                                viewed_list.append(s.id)
                                save_data(db)
                                await notify(f"💖 **Story ko'rildi va reaksiya bosildi!**\n👤 {get_display_name(ent)}\n🆔 `{ent.id}`\n✨ Reaksiya: {reaction_val}\n⏰ {get_uz_time().strftime('%H:%M:%S')}")
                except Exception as e:
                    pass
                await asyncio.sleep(2)
        except Exception as e:
            pass
        await asyncio.sleep(20)

@client.on(events.NewMessage(from_users="me"))
async def commands(event):
    global db
    txt = event.raw_text.strip()
    parts = txt.split(maxsplit=2)
    cmd = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else ""
    emoji_arg = parts[2] if len(parts) > 2 else "❤️"  # Standart yurak

    if cmd == ".story" and arg:
        try:
            target_query = await parse_target_arg(arg)
            ent = await client.get_entity(target_query)
            
            db.setdefault("story_targets", {})[str(ent.id)] = emoji_arg
            save_data(db)
            await event.edit(f"📸 **Story kuzatuviga qo'shildi:**\n👤 {get_display_name(ent)} (`{ent.id}`)\n✨ Reaksiya: `{emoji_arg}`")
        except Exception as e: await event.edit(f"❌ Xato: {e}")

    elif cmd == ".stop" and arg:
        try:
            target_query = await parse_target_arg(arg)
            ent = await client.get_entity(target_query)
            targets = db.get("story_targets", {})
            if str(ent.id) in targets:
                del targets[str(ent.id)]
                save_data(db)
                await event.edit(f"🛑 **Story kuzatuvidan to'xtatildi:** {get_display_name(ent)}")
            else:
                await event.edit("⚠️ Bu ID story ro'yxatida yo'q.")
        except Exception as e: await event.edit(f"❌ Xato: {e}")

    elif cmd == ".stat":
        count = len(db.get("story_targets", {}))
        await event.edit(f"📊 **Story Bot Holati:**\n📸 Kuzatuvdagilar soni: `{count} ta`")

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
    print("Modulli Story Bot muvaffaqiyatli ishga tushdi!")

with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
