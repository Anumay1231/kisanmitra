"""One-step launcher for the KisanMitra web app.

Windows: double-click "Start KisanMitra.bat".   Mac/Linux: ./start.sh   (or: python launch.py)

What it does, every time:
  1. creates a private Python environment in .venv (first run only)
  2. installs the packages the web app needs (first run, or when requirements-app.txt changes)
  3. asks once for your Groq API key and saves it in .env (leave blank for demo mode)
  4. starts the server and opens http://localhost:<port> in your browser

Options:  python launch.py --key     ask for the Groq key again
          python launch.py --rag     also install the scheme-document search (large download)
          python launch.py --phone   also allow phones on the same Wi-Fi to open the app
          python launch.py --share   also create a public https link anyone can open (Cloudflare quick tunnel)
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


TOOLS_DIR = os.path.join(ROOT, ".tools")
CLOUDFLARED_URLS = {
    "win": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    "linux": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
}


def get_cloudflared() -> str:
    """Path to the cloudflared program, downloading it into .tools the first time (about 60 MB)."""
    import shutil
    found = shutil.which("cloudflared")
    if found:
        return found
    if sys.platform == "darwin":
        fail("On a Mac, install cloudflared first: brew install cloudflared")
    exe = os.path.join(TOOLS_DIR, "cloudflared.exe" if IS_WIN else "cloudflared")
    if not os.path.exists(exe):
        os.makedirs(TOOLS_DIR, exist_ok=True)
        say("First share: downloading Cloudflare's tunnel program (about 60 MB, one time)...")
        tmp = exe + ".part"
        urllib.request.urlretrieve(CLOUDFLARED_URLS["win" if IS_WIN else "linux"], tmp)
        os.replace(tmp, exe)
        if not IS_WIN:
            os.chmod(exe, 0o755)
    return exe


def start_tunnel(port: int) -> subprocess.Popen:
    """Start a Cloudflare quick tunnel to the local app and print its public https link."""
    import re
    proc = subprocess.Popen([get_cloudflared(), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")

    def watch():
        shown = False
        for line in proc.stdout:                                  # keep reading so the pipe never fills
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not shown:
                shown = True
                bar = "=" * 64
                print(f"\n{bar}\n  PUBLIC LINK (share this):  {m.group(0)}\n"
                      f"  Works while this window stays open. Close the window to stop sharing.\n{bar}\n", flush=True)
                try:
                    with open(os.path.join(ROOT, "public-link.txt"), "w", encoding="utf-8") as f:
                        f.write(m.group(0) + "\n")
                except OSError:
                    pass
        if not shown:
            print("\nERROR: the public link could not be created. Check your internet connection.", flush=True)

    threading.Thread(target=watch, daemon=True).start()
    return proc


def lan_ip() -> str | None:
    """This computer's address on the local network (what a phone on the same Wi-Fi should open)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))          # no data is sent; this only picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return None


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

    if "--phone" in args:
        run_env["KM_HOST"] = "0.0.0.0"
        ip = lan_ip()
        say(f"Phone access is on. On a phone connected to the SAME Wi-Fi, open: http://{ip or '<this-PC-IP>'}:{port}")
        print("   If Windows asks about the firewall, click 'Allow' for private networks.")
    tunnel = None
    if "--share" in args:
        run_env["KM_PUBLIC"] = "1"          # the server limits questions per visitor to protect your key
        say("Sharing is on: creating a public link. It appears below in a few seconds.")
        print("   Anyone with the link can use the app while this window is open.")
        tunnel = start_tunnel(port)
    mode = "with the Groq AI model" if run_env.get("GROQ_API_KEY") else "in demo mode (no API key)"
    say(f"Starting KisanMitra {mode}. Your browser will open at {url}")
    if run_env.get("GROQ_API_KEY"):
        print("   Checking which Groq model your key can use. This takes 10 to 30 seconds.")
    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    try:
        subprocess.run([VPY, os.path.join(ROOT, "server.py")], env=run_env, cwd=ROOT)
    except KeyboardInterrupt:
        pass
    finally:
        if tunnel:
            tunnel.terminate()
            try:
                os.remove(os.path.join(ROOT, "public-link.txt"))
            except OSError:
                pass
    print("\nKisanMitra stopped.")


if __name__ == "__main__":
    main()
