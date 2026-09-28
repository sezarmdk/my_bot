import asyncio
import os
import time
from datetime import datetime
import pytz

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateStatusRequest

API_ID = 32261789
API_HASH = "06254a37741c127fd669909f57e67168"
SESSION_STR = os.environ.get("SESSION_STRING", "")

client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)

ACTIVE_CHAT = None
CLOCK_RUNNING = False
UZ_TZ = pytz.timezone("Asia/Tashkent")

# 1. Barcha kelgan yangi xabarlarni avtomatik o'qilgan qilish
@client.on(events.NewMessage(incoming=True))
async def auto_read_handler(event):
    try:
        await event.mark_read()
    except Exception:
        pass

# 2. Doimiy Onlayn ushlab turuvchi fon jarayoni
async def keep_online_worker():
    while True:
        try:
            await client(UpdateStatusRequest(offline=False))
        except Exception:
            pass
        await asyncio.sleep(45)

# 3. Har 15 soniyada soat tashlab, o'sha zahoti o'chiradigan fon vazifasi
async def clock_worker():
    global CLOCK_RUNNING, ACTIVE_CHAT
    while CLOCK_RUNNING and ACTIVE_CHAT is not None:
        try:
            now_str = datetime.now(UZ_TZ).strftime("%H:%M:%S")
            msg = await client.send_message(ACTIVE_CHAT, f"⏰ `{now_str}`")
            await asyncio.sleep(0.5)
            await msg.delete()
        except Exception as e:
            print(f"Clock xatolik: {e}")
        await asyncio.sleep(15)

# ================= BUYRUQLAR =================

@client.on(events.NewMessage)
async def commands_handler(event):
    global ACTIVE_CHAT, CLOCK_RUNNING

    # Faqat o'zingiz yozgan buyruqlarni qabul qiladi
    if not event.out and event.sender_id != (await client.get_me()).id:
        return

    txt = (event.raw_text or "").strip()

    if txt == ".on":
        ACTIVE_CHAT = event.chat_id
        if not CLOCK_RUNNING:
            CLOCK_RUNNING = True
            asyncio.create_task(clock_worker())
        try:
            m = await event.reply("✅ **Avto-soat faollashdi!** Har 15 soniyada tashlanib, darhol o'chiriladi.")
            await asyncio.sleep(3)
            await m.delete()
            await event.delete()
        except Exception:
            pass

    elif txt == ".off":
        CLOCK_RUNNING = False
        ACTIVE_CHAT = None
        try:
            m = await event.reply("⏹ **Avto-soat to'xtatildi.**")
            await asyncio.sleep(3)
            await m.delete()
            await event.delete()
        except Exception:
            pass

    elif txt == ".ping":
        s = time.time()
        m = await event.reply("⚡ Ping...")
        diff = (time.time() - s) * 1000
        await m.edit(f"🏓 **Pong!** `{diff:.2f} ms`\n🟢 Auto Read & Auto Online faol.")

async def main():
    if not SESSION_STR:
        print("XATOLIK: SESSION_STRING topilmadi!")
        return
    await client.start()
    asyncio.create_task(keep_online_worker())
    print(">>> USERBOT ISHGA TUSHDI <<<")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
