"""Веб-сервер SC DMX: статичний інтерфейс + WebSocket для керування в реальному часі."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import logging.handlers
import os
import sys
import weakref
from pathlib import Path

from aiohttp import WSMsgType, web

from . import APP_NAME, __version__, updater
from .engine import Engine
from .outputs import _usb_backends, find_udmx_devices, list_serial_ports

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
ENGINE = web.AppKey("engine", Engine)
SOCKETS = web.AppKey("sockets", weakref.WeakSet)
TASKS = web.AppKey("tasks", list)
UPDATE = web.AppKey("update", dict)
STOP = web.AppKey("stop", asyncio.Event)
EXIT = web.AppKey("exit", dict)
UPDATE_CHECK_INTERVAL = 3600
# Програма працює, лише поки відкрите її вікно. Після закриття останнього вікна —
# коротка пауза (перезавантаження сторінки, оновлення), потім світло гасне і програма виходить.
CLOSE_GRACE_S = 6
STARTUP_TIMEOUT_S = 90       # вікно так і не відкрилося — не лишаємось у фоні
WATCH = web.AppKey("watch", dict)  # перевірка оновлень: при запуску і щогодини


async def broadcast(app: web.Application, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False)
    for ws in list(app[SOCKETS]):
        if not ws.closed:
            try:
                await ws.send_str(data)
            except ConnectionError:
                pass


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    app = request.app
    engine = app[ENGINE]
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    app[SOCKETS].add(ws)
    app[WATCH]["seen"] = True
    app[WATCH]["last_close"] = None
    await ws.send_json({"type": "state", "state": engine.state()})
    await ws.send_json({"type": "update", "update": app[UPDATE]})
    async for msg in ws:
        if msg.type != WSMsgType.TEXT:
            continue
        try:
            data = json.loads(msg.data)
            if data.get("cmd") == "find_udmx":
                await ws.send_json({"type": "udmx", "devices": _udmx_list()})
                continue
            if data.get("cmd") == "check_update":
                asyncio.create_task(check_updates(app))
                continue
            if data.get("cmd") == "apply_update":
                asyncio.create_task(apply_update(app))
                continue
            if data.get("cmd") == "open_url":
                # посилання відкриваються браузером користувача за замовчуванням —
                # лише з вікна на цьому ж комп'ютері; іншим пристроям — повертаємо назад
                url = str(data.get("url", ""))
                if _is_local(request):
                    if not await asyncio.get_running_loop().run_in_executor(None, open_external, url):
                        await ws.send_json({"type": "error", "message": "Не вдалося відкрити посилання"})
                else:
                    await ws.send_json({"type": "open_here", "url": url})
                continue
            if data.get("cmd") == "quit":
                await broadcast(app, {"type": "bye"})
                request_stop(app, 0)
                continue
            if data.get("cmd") == "list_ports":
                await ws.send_json({"type": "ports", "ports": list_serial_ports()})
                continue
            engine.handle(data)
        except (ValueError, KeyError, TypeError) as exc:
            await ws.send_json({"type": "error", "message": str(exc).strip("'\"")})
            continue
        # слайдери шлють багато дрібних команд — повний стан для них не потрібен
        if data.get("cmd") in ("set_color", "set_master"):
            await broadcast(app, {"type": "patch", "fixtures": [f.to_dict() for f in engine.fixtures],
                                  "master": engine.master})
        else:
            await broadcast(app, {"type": "state", "state": engine.state()})
    app[SOCKETS].discard(ws)
    if not _open_sockets(app):
        app[WATCH]["last_close"] = asyncio.get_running_loop().time()
    return ws


def _is_local(request: web.Request) -> bool:
    return (request.remote or "") in ("127.0.0.1", "::1", "localhost")


def open_external(url: str) -> bool:
    """Відкриває http(s)-посилання у браузері за замовчуванням операційної системи."""
    import webbrowser
    from urllib.parse import urlparse
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    try:
        if sys.platform == "win32":
            os.startfile(url)  # noqa: S606 — саме так Windows відкриває браузер за замовчуванням
            return True
        return webbrowser.open(url)
    except Exception:  # noqa: BLE001
        log.exception("Не вдалося відкрити %s", url)
        return False


def _open_sockets(app: web.Application) -> list:
    return [w for w in app[SOCKETS] if not w.closed]


async def window_watch(app: web.Application) -> None:
    """Вимикає програму, коли не лишилось жодного відкритого вікна."""
    loop = asyncio.get_running_loop()
    started = loop.time()
    w = app[WATCH]
    while True:
        await asyncio.sleep(1)
        if not w["enabled"] or app[UPDATE]["status"] in ("installing", "restarting"):
            continue
        if _open_sockets(app):
            continue
        now = loop.time()
        if not w["seen"] and now - started > STARTUP_TIMEOUT_S:
            log.info("Вікно програми не відкрилося — вихід")
            request_stop(app, 0)
            return
        if w["seen"] and w["last_close"] is not None and now - w["last_close"] > CLOSE_GRACE_S:
            log.info("Вікно програми закрито — світло вимкнено, вихід")
            request_stop(app, 0)
            return


def _udmx_list() -> list[dict]:
    try:
        return [{k: v for k, v in d.items() if k != "dev"} for d in find_udmx_devices()]
    except RuntimeError:
        return []


def check_udmx() -> int:
    """Діагностика: python -m dmxctl --check"""
    backends = _usb_backends()
    print("Бекенди libusb:", ", ".join(n for n, _ in backends) or "НЕ ЗНАЙДЕНО (pip install libusb-package)")
    try:
        devices = find_udmx_devices()
    except RuntimeError as exc:
        print("Помилка:", exc)
        return 1
    if not devices:
        print("uDMX не знайдено.")
        print("  * перевірте, що адаптер підключено (у Диспетчері пристроїв має бути «uDMX»);")
        print("  * Windows: встановіть драйвер WinUSB через Zadig (див. README).")
        return 1
    from .outputs import UDmxOutput
    for i, d in enumerate(devices):
        print(f"[{i}] {d['product']} serial={d['serial'] or '-'} USB {d['bus']}:{d['address']} через {d['backend']}")
    out = UDmxOutput()
    try:
        out.open()
        print("Тестовий кадр відправлено успішно — uDMX готовий до роботи.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("Пристрій знайдено, але відправка не вдалася:", exc)
        print("  Найчастіше причина — не той драйвер. Встановіть WinUSB через Zadig.")
        return 1
    finally:
        out.close()


async def live_feed(app: web.Application) -> None:
    """Розсилає живі кольори та значення каналів ~15 разів на секунду."""
    engine = app[ENGINE]
    last_output = None
    while True:
        await asyncio.sleep(1 / 15)
        if not app[SOCKETS]:
            continue
        info = engine.output.info()
        out_key = (info["ok"], info["status"])
        payload = {"type": "live", "live": engine.live, "dmx": list(engine.universe),
                   "frames": info["frames"]}
        if out_key != last_output:
            payload["output"] = info
            last_output = out_key
        await broadcast(app, payload)


async def set_update(app: web.Application, **changes) -> None:
    app[UPDATE].update(changes)
    await broadcast(app, {"type": "update", "update": app[UPDATE]})


async def check_updates(app: web.Application) -> None:
    upd = app[UPDATE]
    if upd["status"] in ("checking", "installing", "restarting"):
        return
    await set_update(app, status="checking", error="")
    try:
        info = await asyncio.get_running_loop().run_in_executor(None, updater.check)
        await set_update(app, status="idle", blocked=updater.can_self_update(), **info)
    except Exception as exc:  # noqa: BLE001 — немає інтернету тощо
        log.warning("Не вдалося перевірити оновлення: %s", exc)
        await set_update(app, status="idle", error=f"Не вдалося перевірити оновлення: {exc}")


async def apply_update(app: web.Application) -> None:
    upd = app[UPDATE]
    if not upd.get("available") or upd["status"] in ("installing", "restarting"):
        return
    loop = asyncio.get_running_loop()

    def progress(text: str) -> None:
        loop.call_soon_threadsafe(asyncio.ensure_future, set_update(app, progress=text))

    await set_update(app, status="installing", error="", progress="Підготовка…")
    try:
        await loop.run_in_executor(None, updater.download_and_install, upd["url"], progress)
    except Exception as exc:  # noqa: BLE001
        log.exception("Оновлення не вдалося")
        await set_update(app, status="idle", error=f"Оновлення не вдалося: {exc}")
        return
    log.info("Оновлено до %s, перезапуск", upd["latest"])
    await set_update(app, status="restarting", progress="Перезапуск…")
    await asyncio.sleep(0.5)
    request_stop(app, updater.RESTART_CODE)


async def update_loop(app: web.Application) -> None:
    await asyncio.sleep(3)
    while True:
        await check_updates(app)
        await asyncio.sleep(UPDATE_CHECK_INTERVAL)


def request_stop(app: web.Application, code: int) -> None:
    app[EXIT]["code"] = code
    app[STOP].set()


async def on_startup(app: web.Application) -> None:
    engine = app[ENGINE]
    app[TASKS] = [asyncio.create_task(engine.run()), asyncio.create_task(live_feed(app)),
                  asyncio.create_task(update_loop(app)), asyncio.create_task(window_watch(app))]


async def on_cleanup(app: web.Application) -> None:
    for t in app[TASKS]:
        t.cancel()
    for ws in list(app[SOCKETS]):
        await ws.close()
    # під час перезапуску після оновлення світло не гасимо
    blackout = app[EXIT]["code"] != updater.RESTART_CODE
    await asyncio.get_running_loop().run_in_executor(None, app[ENGINE].shutdown, blackout)


async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


def make_app(config_path: str, background: bool = False) -> web.Application:
    app = web.Application()
    app[WATCH] = {"enabled": not background, "seen": False, "last_close": None}
    app[ENGINE] = Engine(config_path)
    app[SOCKETS] = weakref.WeakSet()
    app[STOP] = asyncio.Event()
    app[EXIT] = {"code": 0}
    app[UPDATE] = {"current": __version__, "latest": "", "available": False, "status": "idle",
                   "error": "", "progress": "", "notes": "", "page": "", "url": "",
                   "blocked": updater.can_self_update(), "repo": updater.GITHUB_REPO}
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_static("/static", STATIC)
    app.on_response_prepare.append(_no_cache)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


async def _no_cache(request: web.Request, response: web.StreamResponse) -> None:
    # після оновлення браузер має взяти нові файли інтерфейсу
    if request.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"


async def serve(config_path: str, host: str, port: int, background: bool = False) -> int:
    app = make_app(config_path, background)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("%s %s запущено: http://localhost:%s/", APP_NAME, __version__, port)
    try:
        await app[STOP].wait()
    finally:
        await runner.cleanup()
    return app[EXIT]["code"]


def setup_logging(verbose: bool) -> None:
    handlers: list[logging.Handler] = []
    try:
        handlers.append(logging.handlers.RotatingFileHandler(
            updater.APP_DIR / "sc-dmx.log", maxBytes=1_000_000, backupCount=1, encoding="utf-8"))
    except OSError:
        pass
    if sys.stderr is not None:  # під pythonw консолі немає
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} — сервер")
    parser.add_argument("--host", default="0.0.0.0", help="адреса веб-сервера (типово 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="порт веб-сервера (типово 8080)")
    parser.add_argument("--config", default=str(updater.APP_DIR / "config.json"), help="файл конфігурації")
    parser.add_argument("--check", action="store_true", help="перевірити підключення uDMX і вийти")
    parser.add_argument("--background", action="store_true",
                        help="не вимикатися після закриття вікна (для керування з інших пристроїв)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args, _unknown = parser.parse_known_args(argv)
    if args.check:
        raise SystemExit(check_udmx())
    setup_logging(args.verbose)
    try:
        code = asyncio.run(serve(args.config, args.host, args.port, args.background))
    except KeyboardInterrupt:
        code = 0
    raise SystemExit(code)


if __name__ == "__main__":
    main()
