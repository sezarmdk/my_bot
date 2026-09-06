import os
import sys
import json
import subprocess
from telethon.sync import TelegramClient
from telethon import functions, types
from telethon.errors import RPCError

API_ID = 32261789
API_HASH = os.environ.get("API_HASH", "BU_YERGA_API_HASH_QOYING")

SRC_VIDEO = "/sdcard/VID_20260904_125128_287.mp4"
PROCESSED_VIDEO = "/data/data/com.termux/files/home/my_bot/trimmed_story.mp4"
SESSION_PATH = "/data/data/com.termux/files/home/my_bot/ob_session_1"

if not os.path.exists(SRC_VIDEO):
    print(f"[XATO] Manba video topilmadi: {SRC_VIDEO}")
    sys.exit(1)

# 1. ffmpeg bilan sifatni 1% ham buzmasdan (-c copy) aniq 59.5 soniyaga qirqish
print("[1/5] Video sifatga tegmasdan 59 soniyaga moslanmoqda...")
trim_cmd = [
    "ffmpeg", "-y",
    "-ss", "00:00:00",
    "-to", "00:00:59.5",
    "-i", SRC_VIDEO,
    "-c", "copy",
    "-movflags", "+faststart",
    PROCESSED_VIDEO
]

res = subprocess.run(trim_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
if res.returncode != 0:
    print(f"[XATO] ffmpeg xatosi: {res.stderr.decode('utf-8', errors='ignore')}")
    sys.exit(1)

# Aniq o'lcham va davomiylikni tekshirish
probe_cmd = [
    "ffprobe", "-v", "error", "-select_streams", "v:0",
    "-show_entries", "stream=width,height,duration:format=duration",
    "-of", "json", PROCESSED_VIDEO
]
meta = json.loads(subprocess.check_output(probe_cmd))
w = int(meta["streams"][0]["width"])
h = int(meta["streams"][0]["height"])
raw_dur = meta["streams"][0].get("duration") or meta["format"].get("duration") or 59
duration = int(round(float(raw_dur)))

print(f"[2/5] Video parametrlari: {w}x{h}, davomiyligi: {duration}s")

# 2. Fayl sessiyasi orqali ulanish
print("[3/5] Telegram mijoziga ulanilmoqda...")
client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

with client:
    print("[4/5] Fayl asl baytlarida to'g'ridan-to'g'ri MTProto serveriga yuklanmoqda...")
    
    def progress(current, total):
        pct = (current / total) * 100
        print(f"\rYuklanish: {pct:.1f}% ({current // 1024} KB / {total // 1024} KB)", end="", flush=True)

    uploaded_file = client.upload_file(PROCESSED_VIDEO, progress_callback=progress)
    print("\n[5/5] Story SendStoryRequest orqali profilingizga joylanmoqda...")

    video_attr = types.DocumentAttributeVideo(
        duration=duration,
        w=w,
        h=h,
        supports_streaming=True
    )

    media = types.InputMediaUploadedDocument(
        file=uploaded_file,
        mime_type="video/mp4",
        attributes=[video_attr]
    )

    try:
        story_result = client(functions.stories.SendStoryRequest(
            peer="me",
            media=media,
            privacy_rules=[types.InputPrivacyValueAllowAll()],
            period=86400
        ))
        print("✅ Story muvaffaqiyatli profilga joylandi!")
        print(f"Story ID: {getattr(story_result, 'id', 'N/A')}")
    except RPCError as e:
        print(f"\n[Telegram RPC Xatosi]: {e}")
    except Exception as ex:
        print(f"\n[Kutilmagan xatolik]: {ex}")
    finally:
        if os.path.exists(PROCESSED_VIDEO):
            os.remove(PROCESSED_VIDEO)
