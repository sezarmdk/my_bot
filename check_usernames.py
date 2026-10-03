import asyncio
import os
import time
import socket
from datetime import datetime
import pytz

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.network import ConnectionTCPFull
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.messages import ReadHistoryRequest
from telethon.tl.functions.channels import ReadHistoryRequest as ChannelReadHistoryRequest
from telethon.tl.functions import PingRequest

API_ID = 32261789
API_HASH = "06254a37741c127fd669909f57e67168"
SESSION_STR = os.environ.get("SESSION_STRING", "")

# Maxsus ultra-tezkor soket klassi (TCP buferini o'chiradi)
class FastConnectionTCP(ConnectionTCPFull):
    def _create_socket(self, *args, **kwargs):
        sock = super()._create_socket(*args, **kwargs)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            pass
        return sock

client = TelegramClient(
    StringSession(SESSION_STR),
    API_ID,
    API_HASH,
    connection=FastConnectionTCP,
    connection_retries=None,
    auto_reconnect=True,
    retry_delay=1,
    request_retries=10
)

ACTIVE_CHAT = None
CLOCK_RUNNING = False
UZ_TZ = pytz.timezone("Asia/Tashkent")

# 1. ULTRA-TEZKOR AVTO-O'QISH (Instant Raw Read)
@client.on(events.NewMessage(incoming=True))
async def instant_read_handler(event):
    try:
        if event.is_channel:
            await client(ChannelReadHistoryRequest(
                channel=event.input_chat,
                max_id=event.id
            ))
        else:
            await client(ReadHistoryRequest(
                peer=event.input_chat,
                max_id=event.id
            ))
    except Exception:
        try:
            await event.mark_read()
        except Exception:
            pass

# 2. AGRESSIV 24/7 ONLINE
async def keep_online_worker():
    while True:
        try:
            if client.is_connected():
                await client(UpdateStatusRequest(offline=False))
        except Exception:
            pass
        await asyncio.sleep(25)

# 3. 15 SONIYALIK SOAT
async def clock_worker():
    global CLOCK_RUNNING, ACTIVE_CHAT
    while CLOCK_RUNNING and ACTIVE_CHAT is not None:
        try:
            now_str = datetime.now(UZ_TZ).strftime("%H:%M:%S")
            msg = await client.send_message(ACTIVE_CHAT, f"⏰ `{now_str}`")
            await asyncio.sleep(0.3)
            await msg.delete()
        except Exception:
            pass
        await asyncio.sleep(15)

# ================= BUYRUQLAR =================

@client.on(events.NewMessage)
async def commands_handler(event):
    global ACTIVE_CHAT, CLOCK_RUNNING

    if not event.out and event.sender_id != (await client.get_me()).id:
        return

    txt = (event.raw_text or "").strip()

    if txt == ".ping":
        # Soket buferidan tozalangan to'g'ridan-to'g'ri MTProto ping
        t0 = time.perf_counter()
        await client(PingRequest(ping_id=1))
        t1 = time.perf_counter()
        latency = (t1 - t0) * 1000

        await event.edit(f"⚡ **Turbo Pong!** `{latency:.2f} ms`\n🟢 TCP_NODELAY & Zero-Queue faol.")

    elif txt == ".on":
        ACTIVE_CHAT = event.chat_id
        if not CLOCK_RUNNING:
            CLOCK_RUNNING = True
            asyncio.create_task(clock_worker())
        try:
            m = await event.reply("✅ **Avto-soat faollashdi!**")
            await asyncio.sleep(2)
            await m.delete()
            await event.delete()
        except Exception:
            pass

    elif txt == ".off":
        CLOCK_RUNNING = False
        ACTIVE_CHAT = None
        try:
            m = await event.reply("⏹ **Avto-soat to'xtatildi.**")
            await asyncio.sleep(2)
            await m.delete()
            await event.delete()
        except Exception:
            pass

async def main():
    if not SESSION_STR:
        print("XATOLIK: SESSION_STRING topilmadi!")
        return
    await client.start()
    asyncio.create_task(keep_online_worker())
    print(">>> ZERO-LATENCY USERBOT ISHGA TUSHDI <<<")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
