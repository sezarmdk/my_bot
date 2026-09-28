import asyncio
import json
import os
import random
import string
import time

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import CheckUsernameRequest
from telethon.errors import FloodWaitError, UsernameInvalidError, UsernameOccupiedError

API_ID = 32261789
API_HASH = "06254a37741c127fd669909f57e67168"
SESSION_STR = os.environ.get("SESSION_STRING", "")

MIN_DELAY = 3.5
MAX_DELAY = 6.5
BATCH_SIZE = 40
BATCH_PAUSE_MIN = 60
BATCH_PAUSE_MAX = 120

PROGRESS_FILE = "progress.json"
AVAILABLE_FILE = "available.txt"
TAKEN_FILE = "taken.txt"
ERRORS_FILE = "errors.txt"
TARGET_FILE = "log_target.txt"

def get_target():
    if os.path.exists(TARGET_FILE):
        try:
            with open(TARGET_FILE, "r") as f:
                val = f.read().strip()
                if val:
                    try:
                        return int(val)
                    except ValueError:
                        return val
        except Exception:
            pass
    return "me"

def set_target(val):
    with open(TARGET_FILE, "w") as f:
        f.write(str(val).strip())

STATS = {
    "available": 0,
    "taken": 0,
    "errors": 0,
    "current_username": "—",
    "last_available": "—",
    "start_time": time.time(),
    "current_delay": MIN_DELAY
}

def generate_combinations():
    letters = string.ascii_lowercase
    combos = []
    for main in letters:
        for odd in letters:
            if odd == main:
                continue
            for pos in range(5):
                chars = [main] * 5
                chars[pos] = odd
                combos.append("".join(chars))
    return combos

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_progress(done_set):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(sorted(done_set), f)

def append_line(path, text):
    with open(path, "a") as f:
        f.write(text + "\n")

client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)

async def send_log(text):
    target = get_target()
    try:
        await client.send_message(target, text)
    except Exception as e:
        if target != "me":
            try:
                await client.send_message("me", f"⚠️ Log xatosi: `{e}`\nXabar: {text}")
            except Exception:
                pass

async def check_one(username):
    for attempt in range(2):
        try:
            result = await client(CheckUsernameRequest(username=username))
            if result is True:
                return "available"
            else:
                return "taken"
        except (UsernameOccupiedError, UsernameInvalidError):
            # Telegram band yoki taqiqlangan deb hisoblasa, bu bo'sh emas
            return "taken"
        except FloodWaitError as e:
            wait_time = e.seconds + random.uniform(5, 10)
            await send_log(f"⚠️ **FloodWait:** `{wait_time:.0f}s` kutilmoqda...")
            await asyncio.sleep(wait_time)
            continue
        except Exception as e:
            err_str = str(e).upper()
            # Fragment auksionida yoki band bo'lsa
            if "PURCHASE" in err_str or "OCCUPIED" in err_str or "INVALID" in err_str:
                return "taken"
            await asyncio.sleep(3)
            if attempt == 1:
                return "error"
            continue
    return "error"

async def checker_worker():
    await asyncio.sleep(3)
    all_combos = generate_combinations()
    done = load_progress()
    remaining = [u for u in all_combos if u not in done]

    total_all = len(all_combos)
    counter = 0

    await send_log(
        f"🚀 **Tekshiruv davom etmoqda (Aniq rejim)!**\n"
        f"📊 Jami: `{total_all}` | Tekshirilgan: `{len(done)}` | Qolgan: `{len(remaining)}`"
    )

    for username in remaining:
        counter += 1
        STATS["current_username"] = username
        status = await check_one(username)

        if status == "available":
            link = f"https://t.me/{username}"
            append_line(AVAILABLE_FILE, link)
            STATS["available"] += 1
            STATS["last_available"] = f"@{username}"
            msg_text = (
                f"🎯 **BO'SH USERNAME TOPILDI!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 @{username}\n"
                f"🔗 {link}\n"
                f"⚡ Hoziroq band qiling!"
            )
            await send_log(msg_text)
            if get_target() != "me":
                try:
                    await client.send_message("me", msg_text)
                except Exception:
                    pass
        elif status == "taken":
            append_line(TAKEN_FILE, f"t.me/{username}")
            STATS["taken"] += 1
            if STATS["taken"] % 25 == 0:
                await send_log(f"📌 Tekshirildi: 25 ta band (@{username} gacha)")
        else:
            append_line(ERRORS_FILE, f"t.me/{username}")
            STATS["errors"] += 1

        done.add(username)
        save_progress(done)

        delay = random.uniform(STATS["current_delay"], STATS["current_delay"] + (MAX_DELAY - MIN_DELAY))
        await asyncio.sleep(delay)

        if counter % BATCH_SIZE == 0 and counter != len(remaining):
            pause = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            await send_log(f"☕ Tanaffus: `{pause:.0f} soniya`...")
            await asyncio.sleep(pause)

    await send_log("🏁 **Barcha usernamelar tekshirib yakunlandi!**")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.log(?:\s+(.+))?$"))
async def handle_set_log(event):
    arg = event.pattern_match.group(1)
    if not arg:
        current = get_target()
        await event.edit(f"📍 **Log manzili:** `{current}`\nO'zgartirish: `.log @kanal`")
        return

    arg = arg.strip()
    try:
        val = int(arg)
    except ValueError:
        val = arg

    try:
        entity = await client.get_entity(val)
        set_target(val)
        name = getattr(entity, 'title', getattr(entity, 'username', str(val)))
        await event.edit(f"✅ **Log kanali belgilandi:** {name} (`{val}`)")
        await client.send_message(val, "🔔 **Ushbu kanal bot logi sifatida tanlandi!**")
    except Exception as e:
        await event.edit(f"❌ Xatolik: `{e}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.stat$"))
async def handle_stat(event):
    all_combos = generate_combinations()
    total = len(all_combos)
    done_set = load_progress()
    checked = len(done_set)
    left = total - checked

    percent = (checked / total) * 100 if total > 0 else 100
    bar_len = 10
    filled = int(percent / 10)
    bar = "█" * filled + "░" * (bar_len - filled)

    uptime_sec = int(time.time() - STATS["start_time"])
    hours = uptime_sec // 3600
    mins = (uptime_sec % 3600) // 60

    text = f"""📊 **CHECKER NAZORAT PANELI**
━━━━━━━━━━━━━━━━━━━━
📈 **Progress:** `[{bar}] {percent:.1f}%`
🎯 **Jami:** `{total} ta` | ✅ **Tekshirildi:** `{checked} ta` | ⏳ **Qoldi:** `{left} ta`
━━━━━━━━━━━━━━━━━━━━
🟢 **Bo'sh:** `{STATS['available']} ta`
🔴 **Band:** `{STATS['taken']} ta`
⚠️ **Xatolik:** `{STATS['errors']} ta`
━━━━━━━━━━━━━━━━━━━━
📍 **Log kanali:** `{get_target()}`
🔍 **Tekshirilmoqda:** `@{STATS['current_username']}`
⭐️ **Oxirgi bo'sh:** `{STATS['last_available']}`
⏱ **Vaqt:** `{hours} soat, {mins} daqiqa`
━━━━━━━━━━━━━━━━━━━━"""
    await event.edit(text)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
async def handle_ping(event):
    s = time.time()
    msg = await event.edit("⚡ **Pinging...**")
    diff = (time.time() - s) * 1000
    await msg.edit(f"🏓 **Pong!**\n⚡ **Tezlik:** `{diff:.2f} ms`")

async def main():
    if not SESSION_STR:
        print("XATOLIK: SESSION_STRING kiritilmagan!")
        return
    await client.start()
    asyncio.create_task(checker_worker())
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
