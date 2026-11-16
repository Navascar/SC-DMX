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

from . import APP_NAME, __version__, library, updater
from .engine import SCENE_EXT, Engine
from .outputs import _usb_backends, find_udmx_devices, list_serial_ports

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
ENGINE = web.AppKey("engine", Engine)
SOCKETS = web.AppKey("sockets", weakref.WeakSet)
TASKS = web.AppKey("tasks", list)
UPDATE = web.AppKey("update", dict)
STOP = web.AppKey("stop", asyncio.Event)
EXIT = web.AppKey("exit", dict)
OWN_NAMES = web.AppKey("own_names", set)   # імена цього комп'ютера для перевірки Host
UPDATE_CHECK_INTERVAL = 3600
OFFLINE_RETRY_S = 600
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
            note = engine.pop_notice()
            if note:
                await ws.send_json({"type": "notice", "message": note})
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
        # вікно запуску ще не відкрило програму (напр. чекає «Оновити»), але живе й опитує сервер —
        # відлік «вікно так і не відкрилося» починається від його останнього запиту
        since = max(started, w.get("splash_at") or 0.0)
        if not w["seen"] and now - since > STARTUP_TIMEOUT_S:
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
        out_key = (info["ok"], info["status"], info.get("paused"))
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
    # checked — перевірка завершилась (будь-як): вікно запуску чекає саме на це
    try:
        info = await asyncio.get_running_loop().run_in_executor(None, updater.check)
        await set_update(app, status="idle", checked=True, blocked=updater.can_self_update(), **info)
    except (OSError, TimeoutError) as exc:  # URLError — підклас OSError: немає інтернету
        log.info("Немає підключення до інтернету — перевірку оновлень відкладено (%s)", exc)
        await set_update(app, status="idle", checked=True, offline=True,
                         error="Немає підключення до інтернету")
        return
    except Exception as exc:  # noqa: BLE001
        log.warning("Не вдалося перевірити оновлення: %s", exc)
        await set_update(app, status="idle", checked=True, error=f"Не вдалося перевірити оновлення: {exc}")
        return
    app[UPDATE]["offline"] = False


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
    while True:   # перша перевірка — одразу: вікно запуску не відкриває програму, поки її не буде
        await check_updates(app)
        # без інтернету пробуємо частіше, щоб оновлення знайшлося, щойно зʼявиться мережа
        await asyncio.sleep(OFFLINE_RETRY_S if app[UPDATE].get("offline") else UPDATE_CHECK_INTERVAL)


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


# ------------------------------------------------------ вікно запуску ---
# Вікно запуску (dmxctl/splash.py) питає стан оновлення й запускає його, поки інтерфейсу ще немає.
# Лише з цього комп'ютера і з заголовком X-SCDMX-Splash: звичайна сторінка в браузері не може
# надіслати такий заголовок на чужу адресу (CORS), тож сторонній сайт ці запити не зробить.
SPLASH_HEADER = "X-SCDMX-Splash"


def _splash_request(request: web.Request) -> None:
    if not _is_local(request) or request.headers.get(SPLASH_HEADER) != "1":
        raise web.HTTPForbidden(text="Forbidden")
    request.app[WATCH]["splash_at"] = asyncio.get_running_loop().time()   # вікно запуску живе


async def update_api(request: web.Request) -> web.Response:
    """GET — стан оновлення; POST — встановити доступне оновлення."""
    _splash_request(request)
    app = request.app
    if request.method == "POST":
        upd = app[UPDATE]
        if upd.get("available") and upd["status"] == "idle":
            upd["error"] = ""   # стара помилка не має виглядати як помилка нового встановлення
            asyncio.create_task(apply_update(app))
    return web.json_response(app[UPDATE])


async def quit_api(request: web.Request) -> web.Response:
    """Вікно запуску закрили до відкриття програми — вимикаємо й сервер."""
    _splash_request(request)
    request_stop(request.app, 0)
    return web.json_response({"ok": True})


# ------------------------------------------------- бібліотека приладів ---
async def library_api(request: web.Request) -> web.Response:
    q = request.query.get("q", "")
    kind = request.query.get("type", "")
    offset = max(0, int(request.query.get("offset", 0) or 0))
    limit = max(1, min(200, int(request.query.get("limit", 60) or 60)))
    recent = request.app[ENGINE].recent_models
    found = library.search(q, limit + 1, kind, offset, recent)
    resp = web.json_response({"total": len(library.models()), "counts": library.counts(q, recent),
                              "results": found[:limit], "more": len(found) > limit},
                             dumps=lambda o: json.dumps(o, ensure_ascii=False))
    resp.enable_compression()
    return resp


async def scene_file(request: web.Request) -> web.Response:
    """Сцена як файл .scdmx — для перенесення на інший комп'ютер."""
    from urllib.parse import quote
    name = request.query.get("name", "")
    try:
        data = request.app[ENGINE].export_scene(name)
    except KeyError:
        raise web.HTTPNotFound(text="сцену не знайдено")
    fname = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in name).strip(" .") or "scene"
    fname += SCENE_EXT
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return web.Response(body=body, content_type="application/json", headers={
        "Content-Disposition": f"attachment; filename=\"scene{SCENE_EXT}\"; filename*=UTF-8''{quote(fname)}"})


async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------- захист ---
def _host_name(host_header: str) -> str:
    """Ім'я хоста із заголовка Host без порту: «127.0.0.1:8080» → «127.0.0.1», «[::1]:8080» → «::1»."""
    h = (host_header or "").strip().lower()
    if h.startswith("["):
        return h[1:h.find("]")] if "]" in h else h[1:]
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


def _own_names() -> set[str]:
    import socket
    names = {"localhost"}
    try:
        name = socket.gethostname().lower()
        names |= {name, f"{name}.local", socket.getfqdn().lower()}
    except OSError:
        pass
    return names


def host_allowed(host_header: str, own_names: set[str]) -> bool:
    """Захист від DNS rebinding: програма відповідає лише на свою адресу — localhost, IP-адресу
    (керування з інших пристроїв мережі) або ім'я цього комп'ютера, а не на чужий домен."""
    import ipaddress
    name = _host_name(host_header)
    if not name:
        return False
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return name in own_names


def origin_allowed(origin: str | None, host_header: str) -> bool:
    """Захист від міжсайтового WebSocket: команди приймаються лише зі сторінки самої програми.
    Без Origin звертаються не браузери (напр. інсталятор, щоб закрити програму) — їх пропускаємо."""
    if not origin:
        return True
    from urllib.parse import urlsplit
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and parts.netloc.lower() == (host_header or "").strip().lower()


@web.middleware
async def guard(request: web.Request, handler):
    if not host_allowed(request.headers.get("Host", ""), request.app[OWN_NAMES]):
        log.warning("Відхилено запит з чужим Host: %r", request.headers.get("Host"))
        raise web.HTTPForbidden(text="Forbidden host")
    if request.path in ("/ws", "/api/update", "/api/quit") and not origin_allowed(request.headers.get("Origin"), request.headers.get("Host", "")):
        log.warning("Відхилено запит %s з чужої сторінки: %r", request.path, request.headers.get("Origin"))
        raise web.HTTPForbidden(text="Forbidden origin")
    return await handler(request)


def make_app(config_path: str, background: bool = False) -> web.Application:
    app = web.Application(middlewares=[guard])
    app[OWN_NAMES] = _own_names()
    app[WATCH] = {"enabled": not background, "seen": False, "last_close": None}
    app[ENGINE] = Engine(config_path)
    app[SOCKETS] = weakref.WeakSet()
    app[STOP] = asyncio.Event()
    app[EXIT] = {"code": 0}
    app[UPDATE] = {"current": __version__, "latest": "", "available": False, "status": "idle",
                   "error": "", "progress": "", "notes": "", "page": "", "url": "",
                   "blocked": updater.can_self_update(), "repo": updater.GITHUB_REPO, "checked": False}
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/library", library_api)
    app.router.add_get("/api/scene", scene_file)
    app.router.add_get("/api/update", update_api)
    app.router.add_post("/api/update", update_api)
    app.router.add_post("/api/quit", quit_api)
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
    runner = web.AppRunner(app, access_log=None, shutdown_timeout=2)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("%s %s запущено: http://localhost:%s/", APP_NAME, __version__, port)
    try:
        await app[STOP].wait()
    finally:
        # спершу самі закриваємо зʼєднання вікон — інакше зупинка чекала б, поки їх закриє клієнт
        for ws in list(app[SOCKETS]):
            try:
                await ws.close(message=b"quit")
            except Exception:  # noqa: BLE001
                pass
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
