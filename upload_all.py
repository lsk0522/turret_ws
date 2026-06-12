import os
import subprocess

cmds = [
    "git init",
    "git remote add origin https://github.com/lsk0522/lsk0522.github.io.git",
    "git fetch origin",
    "git checkout -b main",
    "git reset --mixed origin/main",
    "git add .",
    "git commit -m \"Upload Turret project\"",
    "git push -u origin main"
]

for cmd in cmds:
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print("ERR:", res.stderr)
