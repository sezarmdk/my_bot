import asyncio
import json
import os
import random
import string
import time
from itertools import combinations, product

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import CheckUsernameRequest
from telethon.errors import (
    FloodWaitError,
    UsernameInvalidError,
    UsernameOccupiedError,
    UsernamePurchaseAvailableError
)

# ==== MAKSIMAL OPTIMALLASHTIRILGAN TEZLIK SOZLAMALARI ====
API_ID = 32261789
API_HASH = "06254a37741c127fd669909f57e67168"
SESSION_STR = os.environ.get("SESSION_STRING", "")

# Maksimal chegaradagi kechikish (0.8 - 1.4s)
MIN_DELAY = 0.8
MAX_DELAY = 1.4

# Har 100 ta so'rovda qisqa 15-25 soniyalik dam olish
BATCH_SIZE = 100
BATCH_PAUSE_MIN = 15
BATCH_PAUSE_MAX = 25

PROGRESS_FILE = "progress.json"
AVAILABLE_FILE = "available.txt"
FRAGMENT_FILE = "fragment.txt"
TAKEN_FILE = "taken.txt"
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
    "fragment": 0,
    "taken": 0,
    "errors": 0,
    "current_username": "—",
    "recent_available": [],
    "start_time": time.time(),
    "checked_count": 0,
    "current_min_delay": MIN_DELAY,
    "current_max_delay": MAX_DELAY
}

def generate_combinations():
    letters = string.ascii_lowercase
    combos = []
    for c1, c2 in combinations(letters, 2):
        for p in product([c1, c2], repeat=6):
            if len(set(p)) == 2:
                combos.append("".join(p))
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
    except Exception:
        try:
            await client.send_message("me", text)
        except Exception:
            pass

async def check_one(username):
    for _ in range(2):
        try:
            res = await client(CheckUsernameRequest(username=username))
            return "available" if res is True else "taken"
        except UsernamePurchaseAvailableError:
            return "fragment"
        except (UsernameOccupiedError, UsernameInvalidError):
            return "taken"
        except FloodWaitError as e:
            # FloodWait berilsa, kechikishni vaqtincha xavfsizroq qilamiz
            wait_time = e.seconds + 3
            await send_log(f"⚠️ **FloodWait:** `{wait_time}s` kutilmoqda... Tezlik avtomatik moslanadi.")
            STATS["current_min_delay"] = min(STATS["current_min_delay"] + 0.5, 3.0)
            STATS["current_max_delay"] = min(STATS["current_max_delay"] + 0.5, 4.5)
            await asyncio.sleep(wait_time)
            continue
        except Exception as e:
            err_str = str(e).upper()
            if "PURCHASE" in err_str:
                return "fragment"
            if "OCCUPIED" in err_str or "INVALID" in err_str:
                return "taken"
            await asyncio.sleep(1.5)
            return "error"
    return "error"

def get_stat_message():
    total = 20150
    checked = STATS["checked_count"]
    left = max(0, total - checked)
    percent = (checked / total) * 100 if total > 0 else 0

    elapsed = max(1, int(time.time() - STATS["start_time"]))
    elapsed_h = elapsed // 3600
    elapsed_m = (elapsed % 3600) // 60

    speed = int((checked / elapsed) * 3600) if elapsed > 10 else 0
    recents = "\n".join([f"  └ 🎯 @{u}" for u in STATS["recent_available"][-5:]]) or "  └ Hozircha yo'q"

    return f"""⚡ **TURBO CHECKER HISOBOTI (Maksimal Tezlik)**
━━━━━━━━━━━━━━━━━━━━
📈 **Ko'rsatkich:** `{percent:.2f}%`
🎯 **Jami:** `{total:,}` | ✅ **Ko'rildi:** `{checked:,}` | ⏳ **Qoldi:** `{left:,}`
━━━━━━━━━━━━━━━━━━━━
🟢 **Bo'sh (Toza):** `{STATS['available']} ta`
💎 **Fragment (Auksion):** `{STATS['fragment']} ta`
🔴 **Band:** `{STATS['taken']} ta`
⚠️ **Boshqa:** `{STATS['errors']} ta`
━━━━━━━━━━━━━━━━━━━━
🔍 **Tekshirilmoqda:** `@{STATS['current_username']}`
🚀 **Hozirgi tezlik:** `~{speed} ta/soat`
⏱ **Vaqt:** `{elapsed_h}s {elapsed_m}m`
📍 **Log kanali:** `{get_target()}`
━━━━━━━━━━━━━━━━━━━━
⭐️ **Topilgan bo'sh nomlar:**
{recents}"""

async def checker_worker():
    await asyncio.sleep(3)
    all_combos = generate_combinations()
    done = load_progress()
    STATS["checked_count"] = len(done)
    remaining = [u for u in all_combos if u not in done]

    await send_log(
        f"⚡ **Turbo rejim ishga tushdi!**\n"
        f"📊 Qolgan kombinatsiyalar: `{len(remaining):,} ta`\n"
        f"🚀 Tezlik darajasi: `Maksimal (0.8s - 1.4s)`"
    )

    counter = 0
    for username in remaining:
        counter += 1
        STATS["current_username"] = username
        status = await check_one(username)

        if status == "available":
            link = f"https://t.me/{username}"
            append_line(AVAILABLE_FILE, link)
            STATS["available"] += 1
            STATS["recent_available"].append(username)
            msg = f"🎯 **BO'SH TOPILDI!**\n👉 @{username}\n🔗 {link}"
            await send_log(msg)
            if get_target() != "me":
                await client.send_message("me", msg)

        elif status == "fragment":
            append_line(FRAGMENT_FILE, f"fragment.com/username/{username}")
            STATS["fragment"] += 1

        elif status == "taken":
            append_line(TAKEN_FILE, f"t.me/{username}")
            STATS["taken"] += 1

        else:
            STATS["errors"] += 1

        done.add(username)
        save_progress(done)
        STATS["checked_count"] = len(done)

        # Maksimal tezkor pauza
        delay = random.uniform(STATS["current_min_delay"], STATS["current_max_delay"])
        await asyncio.sleep(delay)

        # Har 100 tadan keyin kichik dam olish
        if counter % BATCH_SIZE == 0 and counter != len(remaining):
            pause = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            await asyncio.sleep(pause)

# ================= BUYRUQLAR =================

@client.on(events.NewMessage)
async def commands_handler(event):
    if not event.out and event.sender_id != (await client.get_me()).id:
        return

    txt = (event.raw_text or "").strip()

    if txt == ".ping":
        await event.reply("🏓 **Pong! Bot tirik va turbo tezlikda ishlamoqda.**")

    elif txt == ".stat":
        await event.reply(get_stat_message())

    elif txt.startswith(".log"):
        parts = txt.split(maxsplit=1)
        if len(parts) > 1:
            val = parts[1].strip()
            try:
                val = int(val)
            except ValueError:
                pass
            try:
                ent = await client.get_entity(val)
                set_target(val)
                title = getattr(ent, 'title', getattr(ent, 'username', str(val)))
                await event.reply(f"✅ **Log kanali o'zgardi:** {title}")
            except Exception as e:
                await event.reply(f"❌ Xatolik: {e}")
        else:
            await event.reply(f"📍 Hozirgi manzil: `{get_target()}`")

async def main():
    if not SESSION_STR:
        print("XATOLIK: SESSION_STRING topilmadi!")
        return
    await client.start()
    asyncio.create_task(checker_worker())
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
