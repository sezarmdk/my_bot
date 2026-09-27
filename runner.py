import subprocess
import os
import sys

port = os.environ.get("PORT", "10000")
subprocess.Popen([sys.executable, "-m", "http.server", str(port)])

print(">>> Username Checker boti runner orqali ishga tushirilmoqda... <<<")
p = subprocess.Popen([sys.executable, "check_usernames.py"])
p.wait()
