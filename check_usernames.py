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
from telethon.errors import FloodWaitError, UsernameInvalidError, UsernameOccupiedError, UsernamePurchaseAvailableError

# ==== SOZLAMALAR ====
API_ID = 32261789
API_HASH = "06254a37741c127fd669909f57e67168"
SESSION_STR = os.environ.get("SESSION_STRING", "")

MIN_DELAY = 3.5
MAX_DELAY = 6.0
BATCH_SIZE = 40
BATCH_PAUSE_MIN = 60
BATCH_PAUSE_MAX = 120

PROGRESS_FILE = "progress.json"
AVAILABLE_FILE = "available.txt"
FRAGMENT_FILE = "fragment.txt"
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
    "fragment": 0,
    "taken": 0,
    "errors": 0,
    "current_username": "—",
    "recent_available": [],
    "start_time": time.time(),
    "current_delay": MIN_DELAY,
    "total_combos": 20150,
    "checked_count": 0
}

LIVE_STATS_ACTIVE = False
LIVE_STAT_MSG = None

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
        except UsernamePurchaseAvailableError:
            return "fragment"
        except (UsernameOccupiedError, UsernameInvalidError):
            return "taken"
        except FloodWaitError as e:
            wait_time = e.seconds + random.uniform(5, 10)
            await send_log(f"⚠️ **FloodWait:** `{wait_time:.0f}s` kutilmoqda...")
            await asyncio.sleep(wait_time)
            continue
        except Exception as e:
            err_str = str(e).upper()
            if "PURCHASE" in err_str:
                return "fragment"
            if "OCCUPIED" in err_str or "TAKEN" in err_str or "INVALID" in err_str:
                return "taken"
            await asyncio.sleep(3)
            if attempt == 1:
                return "error"
            continue
    return "error"

def build_stat_text():
    total = STATS["total_combos"] or 20150
    checked = STATS["checked_count"]
    left = max(0, total - checked)
    percent = (checked / total) * 100 if total > 0 else 0

    bar_len = 10
    filled = int((percent / 100) * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    elapsed = max(1, int(time.time() - STATS["start_time"]))
    elapsed_h = elapsed // 3600
    elapsed_m = (elapsed % 3600) // 60
    elapsed_s = elapsed % 60

    speed_per_hour = int((checked / elapsed) * 3600) if elapsed > 15 else 0
    if speed_per_hour > 0 and left > 0:
        eta_seconds = int(left / (speed_per_hour / 3600))
        eta_h = eta_seconds // 3600
        eta_m = (eta_seconds % 3600) // 60
        eta_str = f"{eta_h}s {eta_m}m"
    else:
        eta_str = "Hisoblanmoqda..."

    recents = "\n".join([f"  └ 🎯 @{u}" for u in STATS["recent_available"][-5:]]) or "  └ Hozircha yo'q"

    return f"""⚡ **LIVE CHECKER NAZORAT PANELI (6-belgili)**
━━━━━━━━━━━━━━━━━━━━
📈 **Progress:** `[{bar}] {percent:.2f}%`
🎯 **Jami:** `{total:,}` | ✅ **Ko'rildi:** `{checked:,}` | ⏳ **Qoldi:** `{left:,}`
━━━━━━━━━━━━━━━━━━━━
🟢 **Bo'sh (Toza):** `{STATS['available']} ta`
💎 **Fragment (Auksion):** `{STATS['fragment']} ta`
🔴 **Band (Akkaunt/Kanal):** `{STATS['taken']} ta`
⚠️ **Xatolik / Chetlatilgan:** `{STATS['errors']} ta`
━━━━━━━━━━━━━━━━━━━━
🔍 **Hozirgi tekshiruv:** `@{STATS['current_username']}`
⚡ **Tezlik:** `~{speed_per_hour} ta/soat` | ⏳ **ETA:** `{eta_str}`
⏱ **Faol vaqti:** `{elapsed_h:02d}:{elapsed_m:02d}:{elapsed_s:02d}`
📍 **Log kanali:** `{get_target()}`
━━━━━━━━━━━━━━━━━━━━
⭐️ **Oxirgi bo'sh nomlar:**
{recents}
━━━━━━━━━━━━━━━━━━━━
💡 To'xtatish: `.stopstat` | Yangilanish: har 10 soniyada"""

async def live_stat_updater():
    global LIVE_STATS_ACTIVE, LIVE_STAT_MSG
    while LIVE_STATS_ACTIVE and LIVE_STAT_MSG:
        try:
            await LIVE_STAT_MSG.edit(build_stat_text())
        except Exception:
            pass
        await asyncio.sleep(10)

async def checker_worker():
    await asyncio.sleep(3)
    all_combos = generate_combinations()
    STATS["total_combos"] = len(all_combos)
    done = load_progress()
    STATS["checked_count"] = len(done)
    remaining = [u for u in all_combos if u not in done]

    counter = 0

    await send_log(
        f"🚀 **Yangi toza sessiyada ishga tushdi!**\n"
        f"📊 Jami: `{len(all_combos):,} ta` | Qolgan: `{len(remaining):,} ta`"
    )

    for username in remaining:
        counter += 1
        STATS["current_username"] = username
        status = await check_one(username)

        if status == "available":
            link = f"https://t.me/{username}"
            append_line(AVAILABLE_FILE, link)
            STATS["available"] += 1
            STATS["recent_available"].append(username)
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

        elif status == "fragment":
            append_line(FRAGMENT_FILE, f"fragment.com/username/{username}")
            STATS["fragment"] += 1

        elif status == "taken":
            append_line(TAKEN_FILE, f"t.me/{username}")
            STATS["taken"] += 1

        else:
            append_line(ERRORS_FILE, f"t.me/{username}")
            STATS["errors"] += 1

        done.add(username)
        save_progress(done)
        STATS["checked_count"] = len(done)

        delay = random.uniform(STATS["current_delay"], STATS["current_delay"] + (MAX_DELAY - MIN_DELAY))
        await asyncio.sleep(delay)

        if counter % BATCH_SIZE == 0 and counter != len(remaining):
            pause = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            await send_log(f"☕ Tanaffus: `{pause:.0f} soniya`...")
            await asyncio.sleep(pause)

    await send_log("🏁 **Barcha 20,150 ta kombinatsiya tekshirib bo'lindi!**")

# ================= BUYRUQLAR =================

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.stat$"))
async def handle_stat(event):
    global LIVE_STATS_ACTIVE, LIVE_STAT_MSG
    LIVE_STATS_ACTIVE = True
    LIVE_STAT_MSG = event
    await event.edit(build_stat_text())
    asyncio.create_task(live_stat_updater())

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.stopstat$"))
async def handle_stop_stat(event):
    global LIVE_STATS_ACTIVE, LIVE_STAT_MSG
    LIVE_STATS_ACTIVE = False
    LIVE_STAT_MSG = None
    await event.edit("⏹ **Jonli statistika yangilanishi to'xtatildi.**")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.log(?:\s+(.+))?$"))
async def handle_set_log(event):
    arg = event.pattern_match.group(1)
    if not arg:
        current = get_target()
        await event.edit(f"📍 **Joriy log kanali:** `{current}`\nO'zgartirish: `.log @kanal` yoki `.log -100xxx`")
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
