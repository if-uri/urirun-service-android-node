# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import io
import json
import pathlib
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import URLError

import pytest

import urirun_service_android_node.core as core
from urirun_service_android_node import DEFAULT_PORT, SERVICE_ID, service_manifest


def test_service_manifest_declares_port() -> None:
    m = service_manifest()
    assert m["id"] == SERVICE_ID
    assert m["id"] == "android-node"
    assert m["defaultPort"] == 8195


def test_service_manifest_has_required_fields() -> None:
    m = service_manifest()
    assert m["kind"] == "service"
    assert "/api/status" in m["http"]["api"]
    assert "/api/host-services" in m["http"]["api"]
    assert "/bootstrap.sh" in m["http"]["api"]
    assert "/apk/" in m["http"]["api"]
    assert "/plugins/chrome.zip" in m["http"]["api"]


def test_lan_ip_returns_string() -> None:
    ip = core._lan_ip()
    assert isinstance(ip, str)
    assert "." in ip  # IPv4 dotted notation


def test_adb_devices_no_adb(monkeypatch) -> None:
    monkeypatch.setattr(core.shutil, "which", lambda _: None)
    devices = core._adb_devices()
    assert devices == []


def test_qr_bytes_writes_and_reads(monkeypatch, tmp_path) -> None:
    written: list = []

    def fake_write(url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"PNG_FAKE")
        written.append(url)

    monkeypatch.setattr(core, "_write_qr_png", fake_write)
    monkeypatch.setattr(core, "_QR_CACHE", tmp_path / "qr.png")
    result = core._qr_bytes("http://192.168.1.1:8195/")
    assert result == b"PNG_FAKE"
    assert written == ["http://192.168.1.1:8195/"]


def _start_test_server(tmp_path) -> tuple[ThreadingHTTPServer, int, str]:
    """Start the service on a free port, return (server, port, base_url)."""
    # Write a fake bootstrap script
    bs = tmp_path / "bootstrap.sh"
    bs.write_text("#!/bin/bash\necho hello\n")
    server = core.serve(host="127.0.0.1", port=0,
                        bootstrap_script=str(bs))
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port, f"http://127.0.0.1:{port}"


def test_api_status_endpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(core.shutil, "which", lambda _: None)  # no adb
    server, port, base = _start_test_server(tmp_path)
    try:
        with urlopen(f"{base}/api/status") as resp:
            data = json.loads(resp.read())
        assert data["ok"] is True
        assert data["adb"] is False
        assert isinstance(data["devices"], list)
    finally:
        server.shutdown()


def test_bootstrap_sh_endpoint(tmp_path) -> None:
    server, port, base = _start_test_server(tmp_path)
    try:
        with urlopen(f"{base}/bootstrap.sh") as resp:
            body = resp.read().decode()
        assert "hello" in body
    finally:
        server.shutdown()


def test_qr_png_endpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(core, "_QR_CACHE", tmp_path / "qr.png")

    def fake_write(url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG_FAKE_DATA")

    monkeypatch.setattr(core, "_write_qr_png", fake_write)
    server, port, base = _start_test_server(tmp_path)
    try:
        with urlopen(f"{base}/qr.png") as resp:
            assert resp.headers["Content-Type"] == "image/png"
            body = resp.read()
        assert body == b"\x89PNG_FAKE_DATA"
    finally:
        server.shutdown()


def test_root_page_html(monkeypatch, tmp_path) -> None:
    server, port, base = _start_test_server(tmp_path)
    try:
        with urlopen(f"{base}/") as resp:
            body = resp.read().decode()
        assert "urirun Android Node" in body
        assert "bootstrap.sh" in body
        assert "Path C — Install APK" in body
        assert "Path E — Host services" in body
        assert "/api/host-services" in body
    finally:
        server.shutdown()


def test_host_services_default_to_same_lan_host_and_dashboard_port(monkeypatch) -> None:
    monkeypatch.delenv("URIRUN_DASHBOARD_PUBLIC_URL", raising=False)
    monkeypatch.delenv("URIRUN_DASHBOARD_BASE", raising=False)
    monkeypatch.delenv("URIRUN_DASHBOARD_PUBLIC_HOST", raising=False)
    monkeypatch.delenv("URIRUN_DASHBOARD_PORT", raising=False)
    monkeypatch.setattr(core, "_host_phone_scanner_services", lambda _base: [])
    data = core.host_services("http://192.168.188.212:8195/")
    assert data["dashboardBase"] == "http://192.168.188.212:8194"
    scanner = data["services"][0]
    assert scanner["id"] == "service:phone-scanner"
    assert scanner["target"] == "service:phone-scanner"
    assert scanner["url"].startswith("http://192.168.188.212:8194/scanner?")
    assert "autostart=1" in scanner["url"]
    assert "minScore=45" in scanner["url"]


def test_host_services_honor_dashboard_public_url(monkeypatch) -> None:
    monkeypatch.setenv("URIRUN_DASHBOARD_PUBLIC_URL", "https://dash.example.test:9443/base/")
    monkeypatch.setattr(core, "_host_phone_scanner_services", lambda _base: [])
    data = core.host_services("http://192.168.188.212:8195/")
    assert data["dashboardBase"] == "https://dash.example.test:9443/base"
    assert data["services"][0]["url"].startswith("https://dash.example.test:9443/base/scanner?")


def test_host_services_prefers_host_dashboard_summary(monkeypatch) -> None:
    monkeypatch.setenv("URIRUN_DASHBOARD_PUBLIC_URL", "http://dash.example.test:8194")

    def fake_summary(base, path, timeout=1.5):
        assert base == "http://dash.example.test:8194"
        assert path == "/api/summary"
        return {"services": [
            {"id": "service:phone-scanner", "url": "https://scanner.example.test:9443/scanner?count=2",
             "label": "Host registry scanner", "routes": ["scanner://page/camera/command/autonomous"]},
        ]}

    monkeypatch.setattr(core, "_host_dashboard_json", fake_summary)
    data = core.host_services("http://192.168.188.212:8195/")
    scanner = data["services"][0]
    assert scanner["url"] == "https://scanner.example.test:9443/scanner?count=2"
    assert scanner["label"] == "Host registry scanner"
    assert scanner["source"] == "host-dashboard-summary"


def test_host_services_endpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("URIRUN_DASHBOARD_PUBLIC_URL", raising=False)
    monkeypatch.delenv("URIRUN_DASHBOARD_BASE", raising=False)
    monkeypatch.delenv("URIRUN_DASHBOARD_PUBLIC_HOST", raising=False)
    monkeypatch.delenv("URIRUN_DASHBOARD_SCHEME", raising=False)
    monkeypatch.delenv("URIRUN_DASHBOARD_PORT", raising=False)
    monkeypatch.setattr(core, "_host_phone_scanner_services", lambda _base: [])
    core._WEB_NODES.clear()
    server, port, base = _start_test_server(tmp_path)
    try:
        with urlopen(f"{base}/api/host-services") as resp:
            data = json.loads(resp.read())
        assert data["ok"] is True
        assert data["services"][0]["id"] == "service:phone-scanner"
        assert f"http://127.0.0.1:8194/scanner?" in data["services"][0]["url"]
    finally:
        server.shutdown()


def test_apk_list_reports_dirs_when_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(core, "_apk_dirs", lambda: [tmp_path / "apk"])
    assert core._list_apks() == []


def test_apk_endpoint_serves_found_apk(monkeypatch, tmp_path) -> None:
    apk_dir = tmp_path / "bin"
    apk_dir.mkdir()
    apk = apk_dir / "urirun test.apk"
    apk.write_bytes(b"APK")
    monkeypatch.setattr(core, "_apk_dirs", lambda: [apk_dir])
    server, port, base = _start_test_server(tmp_path)
    try:
        with urlopen(f"{base}/apk/") as resp:
            listing = json.loads(resp.read())
        assert listing["count"] == 1
        assert listing["apks"][0]["name"] == "urirun test.apk"
        assert listing["apks"][0]["url"] == "/apk/urirun%20test.apk"

        with urlopen(f"{base}/apk/urirun%20test.apk") as resp:
            assert resp.headers["Content-Type"] == "application/vnd.android.package-archive"
            assert resp.read() == b"APK"
    finally:
        server.shutdown()


def test_main_manifest_prints_json(capsys) -> None:
    from urirun_service_android_node.core import main
    rc = main(["manifest"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["id"] == "android-node"
    assert data["defaultPort"] == 8195


def test_web_node_register_and_list() -> None:
    core._WEB_NODES.clear()
    r = core.web_node_register(
        {"userAgent": "Mozilla/5.0 (Linux; Android 8.1; Nexus 7)"},
        service_url="http://192.168.1.1:8195/",
        client_ip="192.168.1.55")
    assert r["ok"] is True
    assert r["platform"] == "android"
    assert r["nodeUrl"].endswith(f"/api/webpage-node/relay/{r['id']}")
    assert r["relayUrl"] == r["nodeUrl"]
    assert r["clientIp"] == "192.168.1.55"
    assert r["clientUrl"] == "http://192.168.1.55"
    assert f"webpage://{r['id']}/page/query/info" in r["routes"]
    listing = core.web_node_list()
    assert listing["count"] == 1
    assert listing["devices"][0]["online"] is True
    assert listing["devices"][0]["clientIp"] == "192.168.1.55"
    assert listing["devices"][0]["relayUrl"].endswith(f"/api/webpage-node/relay/{r['id']}")
    assert listing["devices"][0]["capabilities"] == ["webpage", "dom", "camera", "sensor", "iframe", "user-activity"]


def test_web_node_action_queue_roundtrip() -> None:
    core._WEB_NODES.clear()
    dev = core.web_node_register({"userAgent": "Chrome"}, service_url="http://h:8195/")["id"]
    core.web_node_enqueue(dev, {"id": "a1", "type": "navigate", "url": "https://example.com"})
    polled = core.web_node_poll(dev)
    assert polled["actions"] == [{"id": "a1", "type": "navigate", "url": "https://example.com"}]
    # queue drains after poll
    assert core.web_node_poll(dev)["actions"] == []
    # result is accepted
    assert core.web_node_result(dev, {"id": dev, "actionId": "a1", "result": {"ok": 1}})["ok"] is True


def test_web_node_poll_unknown_device() -> None:
    core._WEB_NODES.clear()
    assert core.web_node_poll("nope")["ok"] is False


def test_page_embeds_web_node_client() -> None:
    from urirun_service_android_node.page import SETUP_HTML
    assert "/api/webpage-node/register" in SETUP_HTML
    assert "urirun-webnode-id" in SETUP_HTML
    assert "webpage-route-list" in SETUP_HTML


def test_webpage_relay_health_routes_and_timeout() -> None:
    core._WEB_NODES.clear()
    dev = core.web_node_register({"userAgent": "Chrome"}, service_url="http://h:8195/")["id"]

    health = core.web_node_health(dev, service_url="http://h:8195/")
    assert health["ok"] is True
    assert health["nodeType"] == "webpage"
    assert health["routeCount"] == len(core.WEBPAGE_ROUTES)

    routes = core.web_node_routes(dev)
    assert routes["ok"] is True
    assert f"webpage://{dev}/camera/command/start" in {route["uri"] for route in routes["routes"]}

    result = core.web_node_run(dev, {
        "uri": f"webpage://{dev}/page/query/info",
        "payload": {},
    }, timeout=0.01)
    assert result["ok"] is False
    assert result["queued"] is True


def test_web_node_forget_by_id_and_name() -> None:
    core._WEB_NODES.clear()
    reg = core.web_node_register({"userAgent": "Chrome"}, service_url="http://h:8195/")
    dev_id = reg["id"]
    # forget by id
    assert core.web_node_forget(dev_id)["forgot"] == dev_id
    assert core.web_node_list()["count"] == 0
    # forget by name
    reg2 = core.web_node_register({"userAgent": "Android"}, service_url="http://h:8195/")
    assert core.web_node_forget(reg2["name"])["forgot"] == reg2["id"]
    assert core.web_node_list()["count"] == 0
    # forgetting an unknown id is a graceful no-op
    assert core.web_node_forget("nope")["ok"] is True


def test_relay_bare_url_returns_node_health(tmp_path):
    """The bare relay URL (nodeUrl with no /health|/routes|/run suffix) is the node root and
    must return health, not 404 — host mesh and users hit <nodeUrl> directly."""
    core._WEB_NODES.clear()
    server, port, base = _start_test_server(tmp_path)
    try:
        import urllib.request
        # register a webpage node on this live test server
        req = urllib.request.Request(f"{base}/api/webpage-node/register",
                                     data=b'{"userAgent":"Android Chrome"}',
                                     headers={"Content-Type": "application/json"}, method="POST")
        reg = json.loads(urllib.request.urlopen(req, timeout=3).read())
        dev = reg["id"]
        # bare relay URL → health (was 404 before the fix)
        bare = json.loads(urllib.request.urlopen(f"{base}/api/webpage-node/relay/{dev}", timeout=3).read())
        assert bare["ok"] is True
        assert bare["kind"] == "node"
        assert bare["nodeType"] == "webpage"
        # /health still works too
        health = json.loads(urllib.request.urlopen(f"{base}/api/webpage-node/relay/{dev}/health", timeout=3).read())
        assert health["ok"] is True
    finally:
        server.shutdown()


def test_relay_bare_url_post_dispatches_run(tmp_path):
    """POST to the bare relay URL (the node's url, no /run suffix) must dispatch a URI via run,
    not 404 — the host mesh POSTs {uri, payload} to <node_url> directly."""
    core._WEB_NODES.clear()
    server, port, base = _start_test_server(tmp_path)
    try:
        import urllib.request
        reg = urllib.request.Request(f"{base}/api/webpage-node/register",
                                     data=b'{"userAgent":"Android"}',
                                     headers={"Content-Type": "application/json"}, method="POST")
        dev = json.loads(urllib.request.urlopen(reg, timeout=3).read())["id"]
        # POST bare relay url with a uri; no page poller → run times out (queued) but NOT 404.
        body = json.dumps({"uri": f"webpage://{dev}/page/query/info", "payload": {}}).encode()
        req = urllib.request.Request(f"{base}/api/webpage-node/relay/{dev}", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        r = json.loads(urllib.request.urlopen(req, timeout=12).read())
        assert "not found" not in str(r.get("error", ""))
        assert r.get("queued") is True or r.get("ok") is True  # routed to run
    finally:
        server.shutdown()
