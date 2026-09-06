import subprocess
import json
import os
import glob
from telethon.sync import TelegramClient
from telethon import functions, types

API_ID = 32261789
API_HASH = "06254a37741c127fd669909f57e67168"
INPUT_VIDEO = "/sdcard/VID_20260904_125128_287.mp4"
PROCESSED_VIDEO = "exact_original.mp4"

if not os.path.exists(INPUT_VIDEO):
    print(f"Xatolik: {INPUT_VIDEO} topilmadi!")
    exit(1)

session_target = "ob_session_1" if os.path.exists("ob_session_1.session") else None
if not session_target:
    sessions = glob.glob("*.session")
    if sessions:
        session_target = sessions[0].replace(".session", "")

# Videoni 1 piksel ham o'zgartirmasdan (-c copy), faqat 59 soniyaga cheklash
subprocess.run([
    'ffmpeg', '-y', '-ss', '00:00:00', '-to', '00:00:59',
    '-i', INPUT_VIDEO, '-c', 'copy', PROCESSED_VIDEO
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_video_info(path):
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height:format=duration',
        '-of', 'json', path
    ]
    data = json.loads(subprocess.check_output(cmd))
    w = int(data['streams'][0]['width'])
    h = int(data['streams'][0]['height'])
    duration = int(round(float(data['format']['duration'])))
    return w, h, duration

w, h, duration = get_video_info(PROCESSED_VIDEO)
print(f"Asl video parametrlari: {w}x{h}, Davomiyligi: {duration}s")

client = TelegramClient(session_target, API_ID, API_HASH)

with client:
    print("Video o'zining asl holatida yuklanmoqda...")
    video_file = client.upload_file(PROCESSED_VIDEO)

    video_attr = types.DocumentAttributeVideo(
        duration=duration,
        w=w,
        h=h,
        supports_streaming=True
    )

    media = types.InputMediaUploadedDocument(
        file=video_file,
        mime_type='video/mp4',
        attributes=[video_attr]
    )

    print("Story profilingizga joylanmoqda...")
    result = client(functions.stories.SendStoryRequest(
        peer='me',
        media=media,
        privacy_rules=[types.InputPrivacyValueAllowAll()],
        period=86400
    ))

    if os.path.exists(PROCESSED_VIDEO):
        os.remove(PROCESSED_VIDEO)

    print("✅ Video asl o'lchami va sifatda profilingizga joylandi!")
