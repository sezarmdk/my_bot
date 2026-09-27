import asyncio
import datetime
import json
import os
import random
import string
import time

from telethon import TelegramClient, events
from telethon.tl.functions.account import CheckUsernameRequest
from telethon.errors import FloodWaitError, UsernameInvalidError

# ==== SOZLAMALAR ====
API_ID = 32261789
API_HASH = "06254a37741c127fd669909f57e67168"
SESSION_NAME = "berdiyorov"

MIN_DELAY = 3.0
MAX_DELAY = 6.0
BATCH_SIZE = 40
BATCH_PAUSE_MIN = 60
BATCH_PAUSE_MAX = 120

PROGRESS_FILE = "progress.json"
AVAILABLE_FILE = "available.txt"
TAKEN_FILE = "taken.txt"
ERRORS_FILE = "errors.txt"
# =====================

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

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def check_one(username):
    while True:
        try:
            result = await client(CheckUsernameRequest(username=username))
            return ("available" if result else "taken")
        except UsernameInvalidError:
            return "error"
        except FloodWaitError as e:
            wait_time = e.seconds + random.uniform(5, 15)
            await client.send_message("me", f"⚠️ **FloodWait:** `{wait_time:.0f} soniya` kutilmoqda...")
            await asyncio.sleep(wait_time)
            STATS["current_delay"] = min(STATS["current_delay"] * 1.5, 30.0)
            continue
        except Exception as e:
            await asyncio.sleep(5)
            continue

async def checker_worker():
    await asyncio.sleep(3)  # Bot to'liq ulanib olishi uchun kutish
    all_combos = generate_combinations()
    done = load_progress()
    remaining = [u for u in all_combos if u not in done]

    total_all = len(all_combos)
    counter = 0

    await client.send_message(
        "me",
        f"🚀 **Username Checker to'liq rejimda ishga tushdi!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Jami kombinatsiyalar:** `{total_all} ta`\n"
        f"✅ **Avval tekshirilgan:** `{len(done)} ta`\n"
        f"⏳ **Tekshirilishi kerak:** `{len(remaining)} ta`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Holatni bilish uchun istalgan chatda `.stat` yozishingiz mumkin."
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
            await client.send_message(
                "me",
                f"🎯 **BO'SH USERNAME TOPILDI!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 @{username}\n"
                f"🔗 {link}\n"
                f"⚡ Hoziroq band qiling!"
            )
        elif status == "taken":
            append_line(TAKEN_FILE, f"t.me/{username}")
            STATS["taken"] += 1
            await client.send_message("me", f"❌ Band: `@{username}`")
        else:
            append_line(ERRORS_FILE, f"t.me/{username}")
            STATS["errors"] += 1
            await client.send_message("me", f"⚠️ Xato: `@{username}`")

        done.add(username)
        save_progress(done)

        delay = random.uniform(STATS["current_delay"], STATS["current_delay"] + (MAX_DELAY - MIN_DELAY))
        await asyncio.sleep(delay)

        if counter % BATCH_SIZE == 0 and counter != len(remaining):
            pause = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            await client.send_message("me", f"☕ **{BATCH_SIZE} ta so'rov yakunlandi.** Tanaffus: `{pause:.0f} soniya`...")
            await asyncio.sleep(pause)

    await client.send_message("me", "🏁 **Barcha kombinatsiyalar tekshirildi va yakunlandi!**")

# ================= BUYRUQLAR =================

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

    text = f"""📊 **USERNAME CHECKER NAZORAT PANELI**
━━━━━━━━━━━━━━━━━━━━
📈 **Progress:** `[{bar}] {percent:.1f}%`
🎯 **Jami kombinatsiyalar:** `{total} ta`
✅ **Tekshirildi:** `{checked} ta`
⏳ **Qoldi:** `{left} ta`
━━━━━━━━━━━━━━━━━━━━
🟢 **Sessiya davomida bo'sh:** `{STATS['available']} ta`
🔴 **Band chiqqanlar:** `{STATS['taken']} ta`
⚠️ **Xatoliklar:** `{STATS['errors']} ta`
━━━━━━━━━━━━━━━━━━━━
🔍 **Tekshirilayotgan:** `@{STATS['current_username']}`
⭐️ **Oxirgi bo'sh username:** `{STATS['last_available']}`
⏱ **Uptime:** `{hours} soat, {mins} daqiqa`
⚡ **Kechikish oralig'i:** `{STATS['current_delay']:.1f}s`
━━━━━━━━━━━━━━━━━━━━"""
    await event.edit(text)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ping$"))
async def handle_ping(event):
    s = time.time()
    msg = await event.edit("⚡ **Pinging...**")
    diff = (time.time() - s) * 1000
    await msg.edit(f"🏓 **Pong!**\n⚡ **Tezlik:** `{diff:.2f} ms`\n🚀 **Status:** `Checker Faol`")

async def main():
    print(">>> Username Checker boti ishga tushmoqda... <<<")
    await client.start()
    print(">>> Telegram Client ulandi! <<<")
    # Tekshiruvchini parallel fonda yurgizamiz
    asyncio.create_task(checker_worker())
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
