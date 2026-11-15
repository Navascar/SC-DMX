"""Лаунчер SC DMX.

python -m dmxctl [--open] [--port N] ...

* запускає сервер в окремому процесі й перезапускає його після оновлення
  (код виходу 42), тож оновлення застосовуються без участі користувача;
* з --open відкриває інтерфейс в окремому вікні (Edge/Chrome у режимі застосунку);
* якщо програма вже запущена — просто відкриває її вікно, другу копію не стартує.

Тут лише стандартна бібліотека, щоб лаунчер працював навіть під час оновлення залежностей.
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser

RESTART_CODE = 42
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_port(port: int, timeout: float = 30) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if port_busy(port):
            return True
        time.sleep(0.3)
    return False


def open_window(url: str) -> None:
    """Вікно без адресного рядка (app mode); якщо не вийшло — звичайний браузер."""
    candidates = []
    if sys.platform == "win32":
        for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"),
                     os.environ.get("LOCALAPPDATA")):
            if base:
                candidates += [os.path.join(base, r"Microsoft\Edge\Application\msedge.exe"),
                               os.path.join(base, r"Google\Chrome\Application\chrome.exe")]
    else:
        candidates += [shutil.which(n) for n in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")]
    for exe in candidates:
        if exe and os.path.exists(exe):
            try:
                subprocess.Popen([exe, f"--app={url}", "--window-size=1400,900"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    args, _ = parser.parse_known_args()
    server_args = [a for a in sys.argv[1:] if a != "--open"]

    if args.help or args.check:  # довідка й діагностика — напряму, без перезапусків
        from .server import main as server_main
        server_main(server_args + (["--help"] if args.help else []))
        return

    url = f"http://localhost:{args.port}/"
    if port_busy(args.port):
        print(f"SC DMX вже запущено: {url}")
        if args.open:
            open_window(url)
        return

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.executable.lower().endswith("pythonw.exe") else 0
    first = True
    while True:
        proc = subprocess.Popen([sys.executable, "-m", "dmxctl.server", *server_args],
                                cwd=APP_DIR, creationflags=flags)
        if first:
            print(f"SC DMX: {url}  (Ctrl+C — вихід)")
            if args.open and wait_port(args.port):
                open_window(url)
            first = False
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            try:
                code = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = 0
            break
        if code != RESTART_CODE:
            break
        print("Перезапуск після оновлення…")
        # чекаємо, поки старий процес звільнить порт
        for _ in range(50):
            if not port_busy(args.port):
                break
            time.sleep(0.1)
    sys.exit(code if code != RESTART_CODE else 0)


if __name__ == "__main__":
    main()
