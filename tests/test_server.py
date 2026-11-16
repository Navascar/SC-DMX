import asyncio

from aiohttp.test_utils import TestClient, TestServer

from dmxctl import server, updater


def test_bad_command_keeps_connection_and_shutdown(tmp_path):
    """Зіпсована чи непередбачена команда не рве з'єднання; після закриття вікна програма вимикається."""
    async def run():
        app = server.make_app(str(tmp_path / "cfg.json"), background=False)
        async with TestClient(TestServer(app)) as c:
            ws = await c.ws_connect("/ws", headers={"Host": f"127.0.0.1:{c.port}"})
            await ws.receive_json()
            await ws.receive_json()
            for bad in ("[]", "1", "null", '{"cmd": "static_color", "index": 999, "ids": []}',
                        '{"cmd": "set_master", "value": 1e400}'):
                await ws.send_str(bad)
                msg = await ws.receive_json(timeout=3)
                assert msg["type"] == "error"
            await ws.close()
            await asyncio.sleep(0.1)
            assert app[server.WATCH]["last_close"] is not None
    asyncio.run(run())


def test_update_check_does_not_overwrite_install(tmp_path, monkeypatch):
    """Перевірка, що закінчилась під час встановлення, не скидає стан «встановлення»."""
    import threading
    started, release = threading.Event(), threading.Event()

    def slow_check():
        started.set()
        release.wait(5)
        return {"current": "1.0.0", "latest": "9.9.9", "available": True, "notes": "", "url": "u", "page": ""}

    def slow_install(url, progress):
        release.set()
        import time
        time.sleep(0.5)
        assert app[server.UPDATE]["status"] == "installing"
    monkeypatch.setattr(updater, "check", slow_check)
    monkeypatch.setattr(updater, "download_and_install", slow_install)
    app = server.make_app(str(tmp_path / "cfg.json"), background=True)

    async def run():
        upd = app[server.UPDATE]
        upd.update(available=True, url="u")
        check = asyncio.create_task(server.check_updates(app))
        while not started.is_set():
            await asyncio.sleep(0.01)
        monkeypatch.setattr(server, "request_stop", lambda *_: None)
        await server.apply_update(app)
        await check
        assert upd["status"] == "restarting"
    asyncio.run(run())


def test_library_bad_numbers_400(tmp_path):
    async def run():
        app = server.make_app(str(tmp_path / "cfg.json"), background=True)
        async with TestClient(TestServer(app)) as c:
            r = await c.get("/api/library?limit=abc", headers={"Host": f"127.0.0.1:{c.port}"})
            assert r.status == 400
    asyncio.run(run())
