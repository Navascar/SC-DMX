import asyncio

from dmxctl.splash import CHECK_WAIT_S, decide, progress_percent, short_notes

UPD = {"status": "idle", "checked": True, "available": False, "blocked": None, "error": ""}


def test_decide_startup_flow():
    assert decide(None, 0, False) == "wait"                                   # сервер ще стартує
    assert decide({**UPD, "checked": False}, 1, False) == "checking"          # чекаємо перевірку оновлень
    assert decide({**UPD, "checked": False}, CHECK_WAIT_S + 1, False) == "open"  # повільний інтернет — не тримаємо
    assert decide(UPD, 0, False) == "open"
    assert decide({**UPD, "offline": True, "error": "Немає підключення"}, 0, False) == "open"


def test_decide_update_is_required():
    upd = {**UPD, "available": True, "latest": "9.9.9"}
    assert decide(upd, 0, False) == "update"
    # оновлення не можна встановити (git, немає прав) — програма відкривається
    assert decide({**upd, "blocked": "це робоча копія git"}, 0, False) == "open"
    assert decide(upd, 0, True) == "installing"                               # «Оновити» натиснуто
    assert decide({**upd, "status": "installing"}, 0, True) == "installing"
    assert decide(None, 0, True) == "installing"                              # сервер перезапускається
    assert decide({**upd, "error": "Оновлення не вдалося: мережа"}, 0, True) == "failed"


def test_splash_text_helpers():
    assert progress_percent("Завантаження… 42%") == 42 and progress_percent("Підготовка…") is None
    notes = "## 1.0\n- Перше\n- Друге\n* Третє"
    assert short_notes(notes) == "• Перше\n• Друге\n• Третє"
    assert short_notes("\n".join(f"- {i}" for i in range(10)), limit=2).endswith("…")


def test_splash_api_only_with_header(tmp_path):
    from aiohttp.test_utils import TestClient, TestServer
    from dmxctl.server import EXIT, STOP, make_app

    async def run():
        app = make_app(str(tmp_path / "cfg.json"), background=True)
        async with TestClient(TestServer(app)) as c:
            host = {"Host": f"127.0.0.1:{c.port}"}
            assert (await c.get("/api/update", headers=host)).status == 403          # без заголовка
            r = await c.get("/api/update", headers={**host, "X-Nitor-Splash": "1"})
            assert r.status == 200 and "checked" in await r.json()
            # вікно запуску версії, що ще називалася SC DMX, — під час оновлення на Nitor
            assert (await c.get("/api/update", headers={**host, "X-SCDMX-Splash": "1"})).status == 200
            r = await c.post("/api/quit", headers={**host, "X-Nitor-Splash": "1",
                                                   "Origin": "https://evil.example"})
            assert r.status == 403 and not app[STOP].is_set()                       # чужа сторінка
            r = await c.post("/api/quit", headers={**host, "X-Nitor-Splash": "1"})
            assert r.status == 200 and app[STOP].is_set() and app[EXIT]["code"] == 0
    asyncio.run(run())


def test_server_waits_while_splash_shows_update(tmp_path, monkeypatch):
    """Поки вікно запуску показує «Оновити» (лише HTTP, без WebSocket), сервер не вимикається;
    коли вікно зникло — вимикається, як раніше."""
    from aiohttp.test_utils import TestClient, TestServer
    from dmxctl import server, updater
    monkeypatch.setattr(updater, "check", lambda: {"current": "1.0.0", "latest": "9.9.9", "available": True,
                                                   "notes": "", "url": "http://x/Nitor.zip", "page": ""})
    monkeypatch.setattr(updater, "can_self_update", lambda: None)
    monkeypatch.setattr(server, "STARTUP_TIMEOUT_S", 0.6)

    async def run():
        app = server.make_app(str(tmp_path / "cfg.json"), background=False)
        async with TestClient(TestServer(app)) as c:
            h = {"Host": f"127.0.0.1:{c.port}", "X-Nitor-Splash": "1"}
            for _ in range(10):                       # ~2 с опитування — утричі довше за таймаут
                upd = await (await c.get("/api/update", headers=h)).json()
                await asyncio.sleep(0.2)
            assert decide(upd, 5, False) == "update"
            assert not app[server.STOP].is_set()
            await asyncio.sleep(2.2)                  # вікно запуску зникло
            assert app[server.STOP].is_set()
    asyncio.run(run())
