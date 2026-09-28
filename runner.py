import subprocess
import os
import sys

# Agar orqa fonda eski python jarayoni qolib ketgan bo'lsa, o'ldiramiz
os.system("pkill -9 -f check_usernames.py 2>/dev/null")

port = os.environ.get("PORT", "10000")
subprocess.Popen([sys.executable, "-m", "http.server", str(port)])

print(">>> YANGI TOZA BOT ISHGA TUSHMOQDA... <<<")
p = subprocess.Popen([sys.executable, "check_usernames.py"])
p.wait()
