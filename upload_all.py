import subprocess
import datetime

cmds = [
    "git add .",
    f"git commit -m \"Fix: threading safety, UX/UI Apple-quality improvements ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})\"",
    "git push origin main"
]

for cmd in cmds:
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print("ERR:", res.stderr)
print("Done!")
