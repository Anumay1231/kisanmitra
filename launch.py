"""One-step launcher for the KisanMitra web app.

Windows: double-click "Start KisanMitra.bat".   Mac/Linux: ./start.sh   (or: python launch.py)

What it does, every time:
  1. creates a private Python environment in .venv (first run only)
  2. installs the packages the web app needs (first run, or when requirements-app.txt changes)
  3. asks once for your Groq API key and saves it in .env (leave blank for demo mode)
  4. starts the server and opens http://localhost:<port> in your browser

Options:  python launch.py --key     ask for the Groq key again
          python launch.py --rag     also install the scheme-document search (large download)
"""
from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(ROOT, ".venv")
ENV_FILE = os.path.join(ROOT, ".env")
APP_REQS = os.path.join(ROOT, "requirements-app.txt")
RAG_REQS = ["langchain-community>=0.3", "langchain-huggingface>=0.1", "sentence-transformers>=3.0",
            "faiss-cpu>=1.8", "pypdf>=4.0"]
IS_WIN = os.name == "nt"
VPY = os.path.join(VENV, "Scripts" if IS_WIN else "bin", "python.exe" if IS_WIN else "python")


def say(msg: str) -> None:
    print(f"\n>> {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"\nERROR: {msg}\n", flush=True)
    sys.exit(1)


def ensure_venv() -> None:
    if os.path.exists(VPY):
        return
    say("First run: creating a Python environment in .venv (about a minute)...")
    venv.EnvBuilder(with_pip=True).create(VENV)
    if not os.path.exists(VPY):
        fail("Could not create .venv. Reinstall Python from python.org and tick 'Add python.exe to PATH'.")


def pip_install(args: list[str], stamp_name: str, stamp_value: str) -> None:
    stamp = os.path.join(VENV, stamp_name)
    if os.path.exists(stamp) and open(stamp).read() == stamp_value:
        return
    say("Installing packages (first run takes a few minutes)...")
    subprocess.run([VPY, "-m", "pip", "install", "--upgrade", "pip", "-q"], check=False)
    r = subprocess.run([VPY, "-m", "pip", "install", "-q", *args])
    if r.returncode != 0:
        fail("Package installation failed. Check your internet connection and run this again.")
    open(stamp, "w").write(stamp_value)


def read_env() -> dict[str, str]:
    env = {}
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def write_env(env: dict[str, str]) -> None:
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("# KisanMitra settings (this file is not uploaded to GitHub)\n")
        for k, v in env.items():
            f.write(f"{k}={v}\n")


def ask_key(env: dict[str, str], force: bool) -> None:
    key = env.get("GROQ_API_KEY", "")
    if key and key != "your_key_here" and not force:
        return
    if not sys.stdin or not sys.stdin.isatty():
        env.setdefault("GROQ_API_KEY", "")
        return
    say("Paste your Groq API key (free at https://console.groq.com/keys) and press Enter.")
    print("   Leave it blank to run in demo mode without the AI model.")
    env["GROQ_API_KEY"] = input("   GROQ_API_KEY: ").strip()
    write_env(env)
    print("   Saved in .env. Run 'python launch.py --key' to change it later.")


def free_port(preferred: int = 8000) -> int:
    for port in [preferred, *range(8001, 8020)]:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def open_browser_when_ready(url: str) -> None:
    for _ in range(600):                       # up to 5 minutes (first start can build the PDF index)
        try:
            urllib.request.urlopen(url + "/api/health", timeout=2)
            webbrowser.open(url)
            return
        except Exception:
            time.sleep(0.5)


def main() -> None:
    if sys.version_info < (3, 10):
        fail(f"Python 3.10 or newer is needed (found {sys.version.split()[0]}). Get it from python.org.")
    os.chdir(ROOT)
    args = set(sys.argv[1:])

    ensure_venv()
    reqs = open(APP_REQS, encoding="utf-8").read()
    pip_install(["-r", APP_REQS], ".installed-app", hashlib.md5(reqs.encode()).hexdigest())

    env = read_env()
    if "--rag" in args:
        pip_install(RAG_REQS, ".installed-rag", "1")
        env["KM_NO_RAG"] = "0"
        write_env(env)
    ask_key(env, force="--key" in args)

    if not os.path.isdir(os.path.join(ROOT, "frontend", "dist")):
        fail("frontend/dist is missing. Download the project again from GitHub.")

    rag_installed = os.path.exists(os.path.join(VENV, ".installed-rag"))
    run_env = dict(os.environ)
    run_env.update({k: v for k, v in env.items() if v})
    run_env.setdefault("KM_NO_RAG", "0" if rag_installed else "1")
    run_env["PYTHONIOENCODING"] = "utf-8"
    port = free_port()
    run_env["PORT"] = str(port)
    url = f"http://localhost:{port}"

    mode = "with the Groq AI model" if run_env.get("GROQ_API_KEY") else "in demo mode (no API key)"
    say(f"Starting KisanMitra {mode}. Your browser will open at {url}")
    if run_env.get("GROQ_API_KEY"):
        print("   Checking which Groq model your key can use. This takes 10 to 30 seconds.")
    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    try:
        subprocess.run([VPY, os.path.join(ROOT, "server.py")], env=run_env, cwd=ROOT)
    except KeyboardInterrupt:
        pass
    print("\nKisanMitra stopped.")


if __name__ == "__main__":
    main()
