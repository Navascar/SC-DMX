"""Лаунчер SC DMX.

python -m dmxctl [--open] [--port N] ...

* запускає сервер в окремому процесі й перезапускає його після оновлення
  (код виходу 42), тож оновлення застосовуються без участі користувача;
* з --open відкриває власне вікно програми (Qt WebEngine — без Edge і без інтернету);
  якщо Qt WebEngine не встановлено — запасний варіант через браузер;
* якщо програма вже запущена — просто відкриває її вікно, другу копію не стартує;
* якщо порт 8080 зайнятий іншим застосунком — працює на наступному вільному порту.

Тут лише стандартна бібліотека, щоб лаунчер працював навіть під час оновлення залежностей.
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

RESTART_CODE = 42
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_scdmx(port: int) -> bool:
    """Чи на порту саме SC DMX, а не інший застосунок (той самий порт може бути зайнятий чимось іншим)."""
    from urllib.request import ProxyHandler, build_opener
    try:
        with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/", timeout=2) as resp:
            return b"<title>SC DMX</title>" in resp.read(4096)
    except Exception:  # noqa: BLE001 — не відповідає або не HTTP
        return False


def free_port(start: int, tries: int = 20) -> int:
    for port in range(start, start + tries):
        if not port_busy(port):
            return port
    return start


def find_scdmx_port(start: int, tries: int = 20) -> int | None:
    return next((p for p in range(start, start + tries) if port_busy(p) and is_scdmx(p)), None)


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


def show_window(url: str, server_done=lambda: False) -> None:
    """Власне вікно програми (Qt WebEngine) — в окремому процесі, щоб збій вікна не зупинив
    програму. Якщо вікно не запускається, запасний варіант — браузер."""
    from . import window
    if window.available():
        started = time.monotonic()
        proc = subprocess.Popen([sys.executable, "-m", "dmxctl.window", url], cwd=APP_DIR)
        while proc.poll() is None:
            if server_done():          # «Вимкнути програму» — закриваємо й вікно
                proc.terminate()
                proc.wait()
                return
            time.sleep(0.3)
        if proc.returncode == 0 or time.monotonic() - started > 10:
            return                     # користувач закрив вікно
        print("Не вдалося відкрити вікно Qt — інтерфейс відкрито в браузері")
    else:
        print("Qt WebEngine не встановлено — інтерфейс відкрито в браузері")
    from urllib.parse import urlsplit
    wait_port(urlsplit(url).port or 80)   # браузеру потрібен уже запущений сервер
    open_window(url)


def focus_existing(port: int) -> None:
    """Програма вже працює: виводимо її вікно на передній план. Якщо вікна немає (програма
    стартує або працює з --background) — чекаємо його, а потім відкриваємо одне вікно."""
    if sys.platform == "win32":
        from . import winshell
        end = time.monotonic() + 15
        while time.monotonic() < end:
            hwnd = winshell.find_app_window()
            if hwnd:
                winshell.focus_window(hwnd)
                return
            time.sleep(0.3)
    port = find_scdmx_port(port) or port
    wait_port(port)
    show_window(f"http://127.0.0.1:{port}/")   # друге вікно однаково не відкриється: у вікна свій захист від копій


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

    guard = None   # м'ютекс «програма вже працює» — тримаємо до виходу
    already = False
    if sys.platform == "win32":
        from . import winshell
        guard = winshell.single_instance(winshell.APP_MUTEX)
        already = guard is None
    # Зайнятий порт ще не означає, що SC DMX запущена: це може бути інший застосунок.
    # Раніше в такому разі сервер не запускався, а вікно відкривало чужу сторінку — порожнє вікно.
    if not already and find_scdmx_port(args.port) is not None:
        already = True
    if already:
        # друга копія не запускається: лише показуємо вікно вже відкритої програми
        print("SC DMX вже запущено")
        if args.open:
            focus_existing(args.port)
        return

    port = args.port
    if port_busy(port):
        port = free_port(port + 1)
        print(f"Порт {args.port} зайнятий іншим застосунком, SC DMX працює на порту {port}")
        server_args += ["--port", str(port)]
    url = f"http://127.0.0.1:{port}/"

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.executable.lower().endswith("pythonw.exe") else 0
    state = {"code": 0, "proc": None}
    done = threading.Event()

    def supervise() -> None:
        """Сервер в окремому процесі; після оновлення (код 42) — перезапуск."""
        while True:
            proc = subprocess.Popen([sys.executable, "-m", "dmxctl.server", *server_args],
                                    cwd=APP_DIR, creationflags=flags)
            state["proc"] = proc
            code = proc.wait()
            if code != RESTART_CODE:
                state["code"] = code
                break
            print("Перезапуск після оновлення…")
            for _ in range(50):  # чекаємо, поки старий процес звільнить порт
                if not port_busy(port):
                    break
                time.sleep(0.1)
        done.set()

    threading.Thread(target=supervise, name="server", daemon=True).start()
    print(f"SC DMX: {url}  (Ctrl+C — вихід)")
    try:
        if args.open:
            # вікно — одразу, з екраном завантаження (воно саме чекає на сервер);
            # після його закриття сервер сам гасить світло й виходить
            show_window(url, done.is_set)
        while not done.wait(0.5):
            pass
    except KeyboardInterrupt:
        proc = state["proc"]
        if proc and proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    sys.exit(state["code"])


if __name__ == "__main__":
    main()
