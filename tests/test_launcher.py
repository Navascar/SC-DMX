import http.server
import socket
import threading

from dmxctl.__main__ import find_scdmx_port, free_port, is_scdmx


def _serve(body: bytes):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_foreign_app_on_port_is_not_scdmx():
    """Інший застосунок на порту — не SC DMX: програма має запуститися на іншому порту, а не вважати себе відкритою."""
    other = _serve(b"<html><title>Other</title></html>")
    ours = _serve(b"<!doctype html><title>SC DMX</title>")
    try:
        assert not is_scdmx(other.server_port)
        assert is_scdmx(ours.server_port)
        assert find_scdmx_port(other.server_port, tries=1) is None
    finally:
        other.shutdown()
        ours.shutdown()


def test_free_port_skips_busy_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        busy = s.getsockname()[1]
        assert free_port(busy) != busy
