# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Android node setup and distribution service for urirun (port 8195).

Serves a setup page with QR codes for:
- ADB WiFi connection (for immediate device control via urirun-connector-adb)
- Termux node bootstrap (for persistent urirun node on the Android device)
- Optional APK download (place compiled APK in apk/ subdirectory)

Endpoints:
  GET /              setup.html with step-by-step instructions
  GET /qr.png        QR code PNG pointing to this service URL
  GET /bootstrap.sh  Termux bootstrap script
  GET /apk/          list available APK files
  GET /apk/<file>    download a specific APK
  GET /api/status    JSON: ADB device list + service info
  POST /api/connect  register an Android node with its IP:port
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Sequence
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
import urllib.request


SERVICE_ID = "android-node"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8195
DEFAULT_DASHBOARD_PORT = 8194

_QR_CACHE: pathlib.Path = pathlib.Path.home() / ".urirun" / "android-node" / "qr.png"
_APK_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent / "apk"

# In-memory registry of connected webpage nodes (phones/browsers that opened the page).
# Each entry: {id, name, platform, userAgent, lastSeen, queue: [actions], results: {}}
_WEB_NODES: dict = {}
_WEB_SEQ = {"n": 0}
WEBPAGE_ROUTES = [
    "webpage://{id}/page/query/info",
    "webpage://{id}/page/query/text",
    "webpage://{id}/page/query/devices",
    "webpage://{id}/page/command/navigate",
    "webpage://{id}/page/command/eval",
    "webpage://{id}/camera/query/status",
    "webpage://{id}/camera/command/start",
    "webpage://{id}/sensor/query/capabilities",
    "webpage://{id}/user/query/activity",
    "webpage://{id}/iframe/command/open",
]


# --- config helpers ---------------------------------------------------------

def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v else default


def default_host() -> str:
    return os.environ.get("URIRUN_ANDROID_NODE_HOST", DEFAULT_HOST)


def default_port() -> int:
    return _env_int("URIRUN_ANDROID_NODE_PORT", DEFAULT_PORT)


def service_manifest() -> dict:
    return {
        "id": SERVICE_ID,
        "kind": "service",
        "name": "urirun-service-android-node",
        "label": "Android setup and webpage-node relay service",
        "defaultHost": DEFAULT_HOST,
        "defaultPort": DEFAULT_PORT,
        "env": {
            "host": "URIRUN_ANDROID_NODE_HOST",
            "port": "URIRUN_ANDROID_NODE_PORT",
            "apkDir": "URIRUN_ANDROID_NODE_APK_DIR",
            "apkDirs": "URIRUN_ANDROID_NODE_APK_DIRS",
            "dashboardPort": "URIRUN_DASHBOARD_PORT",
            "dashboardPublicUrl": "URIRUN_DASHBOARD_PUBLIC_URL",
        },
        "routes": [
            "android://node/setup/query/status",
            "android://node/setup/command/connect",
            "webpage://{id}/page/query/info",
            "webpage://{id}/page/query/devices",
            "webpage://{id}/camera/command/start",
        ],
        "http": {
            "index": "/",
            "api": [
                "/api/status", "/api/connect", "/bootstrap.sh", "/qr.png",
                "/apk/", "/apk/<file>",
                "/plugins", "/plugins/chrome.zip", "/plugins/firefox.zip",
                "/api/host-services",
                "/api/web-node/list", "/api/webpage-node/list",
                "/api/web-node/relay/<id>/health",
                "/api/web-node/relay/<id>/routes",
                "/api/web-node/relay/<id>/run",
            ],
        },
    }


def urirun_service() -> dict:
    return service_manifest()


# --- network helpers --------------------------------------------------------

def _lan_ip() -> str:
    """Best-effort: get LAN IP by connecting a UDP socket (no packet sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _service_url(bind_host: str, port: int) -> str:
    host = _lan_ip() if bind_host in ("", "0.0.0.0", "::") else bind_host
    return f"http://{host}:{port}/"


def _url_host(host: str) -> str:
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def _dashboard_base_url(service_url: str) -> str:
    explicit = (os.environ.get("URIRUN_DASHBOARD_PUBLIC_URL") or os.environ.get("URIRUN_DASHBOARD_BASE") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    parsed = urlsplit(service_url)
    scheme = (os.environ.get("URIRUN_DASHBOARD_SCHEME") or parsed.scheme or "http").strip() or "http"
    host = (
        os.environ.get("URIRUN_DASHBOARD_PUBLIC_HOST")
        or parsed.hostname
        or _lan_ip()
    )
    port = _env_int("URIRUN_DASHBOARD_PORT", _env_int("URIRUN_SERVICE_CHAT_PORT", DEFAULT_DASHBOARD_PORT))
    return f"{scheme}://{_url_host(host)}:{port}"


def _scanner_page_url(base_url: str) -> str:
    """Delegate scanner URL shaping to the scanner package when available."""
    try:
        from urirun_scanner.scanner_net import _scanner_page_url as _real_scanner_page_url
        return _real_scanner_page_url(base_url)
    except Exception:  # noqa: BLE001 - standalone setup service fallback
        parts = urlsplit(base_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        defaults = {
            "autostart": os.environ.get("URIRUN_PHONE_SCANNER_AUTOSTART", "1"),
            "auto": os.environ.get("URIRUN_PHONE_SCANNER_AUTO", "1"),
            "best": os.environ.get("URIRUN_PHONE_SCANNER_BEST", "1"),
            "count": os.environ.get("URIRUN_PHONE_SCANNER_BEST_COUNT", "6"),
            "minScore": os.environ.get("URIRUN_PHONE_SCANNER_MIN_SCORE", "45"),
            "interval": os.environ.get("URIRUN_PHONE_SCANNER_INTERVAL", "3"),
        }
        for key, value in defaults.items():
            query.setdefault(key, value)
        return urlunsplit((
            parts.scheme,
            parts.netloc,
            parts.path or "/scanner",
            urlencode(query),
            parts.fragment,
        ))


def _host_dashboard_json(dashboard_base: str, path: str, timeout: float = 1.5) -> dict:
    url = dashboard_base.rstrip("/") + path
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _host_phone_scanner_services(dashboard_base: str) -> list[dict]:
    """Read phone-delegated host services from the host dashboard source of truth."""
    try:
        summary = _host_dashboard_json(dashboard_base, "/api/summary")
    except Exception:  # noqa: BLE001 - dashboard may be down during setup
        return []
    services = summary.get("services") if isinstance(summary, dict) else None
    if not isinstance(services, list):
        return []
    out: list[dict] = []
    for item in services:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id") or "")
        if sid != "service:phone-scanner":
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        out.append({
            **item,
            "target": item.get("target") or sid,
            "description": item.get("description") or "Open the host phone-scanner UI on this smartphone.",
            "source": "host-dashboard-summary",
        })
    return out


def _fallback_phone_scanner_service(dashboard_base: str) -> dict:
    scanner_url = _scanner_page_url(f"{dashboard_base}/scanner")
    return {
        "id": "service:phone-scanner",
        "name": "phone-scanner",
        "kind": "service",
        "label": "Phone Scanner",
        "url": scanner_url,
        "target": "service:phone-scanner",
        "description": "Open the host phone-scanner UI on this smartphone.",
        "routes": [
            "dashboard://host/phone-scanner/command/start",
            "dashboard://host/service/phone-scanner/command/restart",
            "scanner://page/camera/command/autonomous",
        ],
        "source": "android-node-fallback",
    }


def host_services(service_url: str) -> dict:
    """Return host services that make sense to open from a phone.

    The android-node landing page is the phone entry point on port 8195. These
    links delegate back to host services on the same LAN host, without baking in
    a private IP address.
    """
    dashboard_base = _dashboard_base_url(service_url)
    services = _host_phone_scanner_services(dashboard_base)
    if not services:
        services = [_fallback_phone_scanner_service(dashboard_base)]
    return {
        "ok": True,
        "serviceUrl": service_url,
        "dashboardBase": dashboard_base,
        "services": services,
    }


# --- QR generation ----------------------------------------------------------

def _write_qr_png(url: str, path: pathlib.Path) -> None:
    """Write a QR code PNG for url to path (requires qrcode[pil])."""
    import qrcode  # type: ignore
    path.parent.mkdir(parents=True, exist_ok=True)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.convert("RGB").save(path)


def _qr_bytes(url: str) -> bytes:
    """Return QR code PNG bytes, using cache file."""
    if not _QR_CACHE.exists():
        _write_qr_png(url, _QR_CACHE)
    return _QR_CACHE.read_bytes()


def _qr_bytes_for(url: str) -> bytes:
    """Return QR PNG bytes for an arbitrary url, cached per-url by hash. Used for the APK download
    QR (and any other deep link) so a phone can scan straight to it."""
    import hashlib
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    path = _QR_CACHE.parent / f"qr-{digest}.png"
    if not path.exists():
        _write_qr_png(url, path)
    return path.read_bytes()


# --- ADB detection ----------------------------------------------------------

def _adb_devices() -> list[dict]:
    """Return list of connected ADB devices (empty if adb not found)."""
    adb = shutil.which("adb")
    if not adb:
        return []
    try:
        proc = subprocess.run([adb, "devices", "-l"],
                              capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return []
    devices = []
    for line in proc.stdout.strip().splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        model = next((p.split(":", 1)[1].replace("_", " ")
                      for p in parts[2:] if p.startswith("model:")), "")
        devices.append({"serial": serial, "state": state, "model": model})
    return devices


# --- bootstrap script path --------------------------------------------------

def _bootstrap_script_path(override: str | None) -> pathlib.Path | None:
    if override:
        p = pathlib.Path(override)
        return p if p.exists() else None
    # Development default: canonical Android application repository.
    candidates = [
        pathlib.Path(__file__).parent.parent.parent / "urirun-android-node-app" / "scripts" / "bootstrap-termux.sh",
        pathlib.Path.home() / ".urirun" / "android-node" / "bootstrap.sh",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# --- webpage-node registry (browsers/phones that opened the page) ------------

def _now() -> float:
    import time
    return time.time()


def web_node_register(payload: dict, *, service_url: str, client_ip: str | None = None) -> dict:
    """Register a browser/phone that opened the page as a webpage node.

    Returns its id + relay URL. The webpage node is controlled via the action
    queue (poll/result), relayed by this service.
    """
    payload = payload if isinstance(payload, dict) else {}
    dev_id = str(payload.get("id") or "").strip()
    if not dev_id:
        _WEB_SEQ["n"] += 1
        dev_id = f"web{_WEB_SEQ['n']}"
    ua = str(payload.get("userAgent") or "")
    platform = "android" if "Android" in ua else "ios" if ("iPhone" in ua or "iPad" in ua) else "browser"
    name = str(payload.get("name") or "").strip() or f"{platform}-{dev_id}"
    reported_ip = str(payload.get("clientIp") or payload.get("deviceIp") or "").strip()
    client_ip = reported_ip or str(client_ip or "").strip()
    client_url = f"http://{client_ip}" if client_ip else ""
    entry = _WEB_NODES.get(dev_id) or {"queue": [], "results": {}}
    entry.update({
        "id": dev_id, "name": name, "platform": platform, "userAgent": ua,
        "clientIp": client_ip,
        "clientUrl": client_url,
        "pageUrl": str(payload.get("pageUrl") or ""),
        "lastSeen": _now(),
        # relay endpoint: the host reaches this webpage node THROUGH the service
        "nodeUrl": service_url.rstrip("/") + f"/api/webpage-node/relay/{dev_id}",
        "online": True,
        "capabilities": ["webpage", "dom", "camera", "sensor", "iframe", "user-activity"],
        "routes": [route.replace("{id}", dev_id) for route in WEBPAGE_ROUTES],
    })
    _WEB_NODES[dev_id] = entry
    return {"ok": True, "id": dev_id, "name": name, "platform": platform,
            "nodeUrl": entry["nodeUrl"], "relayUrl": entry["nodeUrl"],
            "clientIp": entry["clientIp"], "clientUrl": entry["clientUrl"],
            "pageUrl": entry["pageUrl"], "routes": entry["routes"],
            "capabilities": entry["capabilities"]}


def web_node_list() -> dict:
    """List connected webpage nodes (online = seen in the last 15s)."""
    now = _now()
    devices = []
    for entry in _WEB_NODES.values():
        online = (now - entry.get("lastSeen", 0)) < 15
        devices.append({"id": entry["id"], "name": entry["name"],
                        "platform": entry["platform"], "online": online,
                        "nodeUrl": entry["nodeUrl"],
                        "relayUrl": entry["nodeUrl"],
                        "clientIp": entry.get("clientIp") or "",
                        "clientUrl": entry.get("clientUrl") or "",
                        "pageUrl": entry.get("pageUrl") or "",
                        "routes": entry.get("routes") or [],
                        "capabilities": entry.get("capabilities") or []})
    return {"ok": True, "devices": devices, "count": len(devices)}


def web_node_forget(id_or_name: str) -> dict:
    """Drop a webpage node from the registry by id or name (used by the dashboard delete button)."""
    key = (id_or_name or "").strip()
    if not key:
        return {"ok": False, "error": "id or name is required"}
    if key in _WEB_NODES:
        _WEB_NODES.pop(key, None)
        return {"ok": True, "forgot": key}
    for dev_id, entry in list(_WEB_NODES.items()):
        if entry.get("name") == key:
            _WEB_NODES.pop(dev_id, None)
            return {"ok": True, "forgot": dev_id}
    return {"ok": True, "forgot": None}  # already gone


def web_node_poll(dev_id: str) -> dict:
    """Webpage node long-poll: return queued actions and mark it seen."""
    entry = _WEB_NODES.get(dev_id)
    if not entry:
        return {"ok": False, "error": "unknown device"}
    entry["lastSeen"] = _now()
    actions = entry["queue"]
    entry["queue"] = []
    return {"ok": True, "actions": actions}


def web_node_enqueue(dev_id: str, action: dict) -> dict:
    """Host-side: enqueue an action for a webpage node to execute."""
    entry = _WEB_NODES.get(dev_id)
    if not entry:
        return {"ok": False, "error": "unknown device"}
    entry["queue"].append(action)
    return {"ok": True, "queued": len(entry["queue"])}


def web_node_result(dev_id: str, payload: dict) -> dict:
    """Webpage node posts the result of an executed action."""
    entry = _WEB_NODES.get(dev_id)
    if not entry:
        return {"ok": False, "error": "unknown device"}
    action_id = str(payload.get("actionId") or "")
    entry["results"][action_id] = payload.get("result")
    entry["lastSeen"] = _now()
    return {"ok": True}


def _webpage_routes(dev_id: str) -> list[dict]:
    return [
        {
            "uri": route.replace("{id}", dev_id),
            "kind": "command" if "/command/" in route else "query",
            "adapter": "webpage-relay",
            "target": dev_id,
        }
        for route in WEBPAGE_ROUTES
    ]


def web_node_health(dev_id: str, *, service_url: str) -> dict:
    entry = _WEB_NODES.get(dev_id)
    if not entry:
        return {"ok": False, "error": "unknown device"}
    online = (_now() - entry.get("lastSeen", 0)) < 15
    return {
        "ok": True,
        "name": entry.get("name") or dev_id,
        "kind": "node",
        "nodeType": "webpage",
        "type": "webpage",
        "runtime": "browser-page-js",
        "transport": "http+js-relay",
        "service": SERVICE_ID,
        "serviceUrl": service_url,
        "reachable": online,
        "routeCount": len(WEBPAGE_ROUTES),
        "capabilities": entry.get("capabilities") or [],
    }


def web_node_routes(dev_id: str) -> dict:
    if dev_id not in _WEB_NODES:
        return {"ok": False, "error": "unknown device", "routes": []}
    return {"ok": True, "routes": _webpage_routes(dev_id)}


def _action_from_uri(dev_id: str, uri: str, payload: dict) -> dict:
    route = uri
    if "://" in route:
        route = route.split("://", 1)[1]
        parts = route.split("/")
        route = "/".join(parts[1:]) if len(parts) > 1 else ""
    action = {"uri": uri, "payload": payload}
    if route in {"page/query/info"}:
        action["type"] = "info"
    elif route in {"page/query/text"}:
        action["type"] = "text"
    elif route in {"page/query/devices", "camera/query/status"}:
        action["type"] = "devices"
    elif route in {"page/command/navigate"}:
        action.update({"type": "navigate", "url": payload.get("url")})
    elif route in {"page/command/eval"}:
        action.update({"type": "eval", "expression": payload.get("expression")})
    elif route in {"camera/command/start"}:
        action.update({"type": "camera-start", "constraints": payload.get("constraints")})
    elif route in {"sensor/query/capabilities"}:
        action["type"] = "sensors"
    elif route in {"user/query/activity"}:
        action["type"] = "activity"
    elif route in {"iframe/command/open"}:
        action.update({"type": "iframe", "url": payload.get("url"), "frameId": payload.get("id")})
    else:
        action["type"] = "uri"
    return action


def web_node_run(dev_id: str, payload: dict, *, timeout: float = 8.0) -> dict:
    entry = _WEB_NODES.get(dev_id)
    if not entry:
        return {"ok": False, "error": "unknown device"}
    payload = payload if isinstance(payload, dict) else {}
    uri = str(payload.get("uri") or "").strip()
    if not uri:
        return {"ok": False, "error": "uri is required"}
    import time
    _WEB_SEQ["n"] += 1
    action_id = f"act{_WEB_SEQ['n']}"
    action = _action_from_uri(dev_id, uri, payload.get("payload") if isinstance(payload.get("payload"), dict) else {})
    action["id"] = action_id
    entry["queue"].append(action)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if action_id in entry["results"]:
            result = entry["results"].pop(action_id)
            return {"ok": True, "uri": uri, "result": result}
        time.sleep(0.1)
    return {"ok": False, "uri": uri, "error": "webpage action timed out", "queued": True, "actionId": action_id}


# --- browser plugin distribution (served from port 8195) --------------------

def _repo_root() -> pathlib.Path:
    # urirun_service_android_node/core.py → package → urirun-service-android-node → repo root
    return pathlib.Path(__file__).parent.parent.parent


def _plugin_dir(name: str) -> pathlib.Path | None:
    """Return the chrome-plugin / firefox-plugin source dir if present."""
    if name not in ("chrome", "firefox"):
        return None
    override = os.environ.get(f"URIRUN_{name.upper()}_PLUGIN_DIR")
    candidates = [pathlib.Path(override)] if override else []
    candidates += [_repo_root() / f"{name}-plugin",
                   pathlib.Path.home() / ".urirun" / "android-node" / f"{name}-plugin"]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _apk_dirs() -> list[pathlib.Path]:
    """APK search path for /apk/ distribution.

    The package-local apk/ directory is the stable distribution location, while
    urirun-android-node-app/bin is where Buildozer writes debug APKs during
    local development.
    """
    candidates: list[pathlib.Path] = []
    configured = os.environ.get("URIRUN_ANDROID_NODE_APK_DIRS") or os.environ.get("URIRUN_ANDROID_NODE_APK_DIR")
    if configured:
        candidates.extend(pathlib.Path(p).expanduser() for p in configured.split(os.pathsep) if p)
    candidates.extend([
        _APK_DIR,
        _repo_root() / "urirun-android-node-app" / "bin",
        pathlib.Path.home() / ".urirun" / "android-node" / "apk",
    ])
    out: list[pathlib.Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        out.append(path.expanduser())
    return out


def _list_apks() -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for directory in _apk_dirs():
        if not directory.exists():
            continue
        for apk in sorted(directory.glob("*.apk")):
            if not apk.is_file() or apk.name in seen:
                continue
            seen.add(apk.name)
            items.append({
                "name": apk.name,
                "url": f"/apk/{quote(apk.name)}",
                "bytes": apk.stat().st_size,
                "sourceDir": str(directory),
                "path": str(apk),
            })
    return items


def _find_apk(name: str) -> pathlib.Path | None:
    clean = pathlib.PurePath(unquote(name)).name
    if not clean or clean != unquote(name) or not clean.endswith(".apk"):
        return None
    for directory in _apk_dirs():
        apk = directory / clean
        if apk.is_file():
            return apk
    return None


def _zip_plugin(name: str) -> bytes | None:
    """Zip a plugin source dir into bytes for download (skips .git/node_modules)."""
    import io
    import zipfile
    src = _plugin_dir(name)
    if not src:
        return None
    buf = io.BytesIO()
    skip = {".git", "node_modules", "__pycache__", ".pytest_cache"}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_dir():
                continue
            if any(part in skip for part in path.relative_to(src).parts):
                continue
            zf.write(path, arcname=str(pathlib.Path(name + "-plugin") / path.relative_to(src)))
    return buf.getvalue()


def plugins_index(service_url: str) -> dict:
    """List the browser clients this service distributes: chrome plugin, firefox plugin, webpage."""
    base = service_url.rstrip("/")
    items = []
    if _plugin_dir("chrome"):
        items.append({"id": "chrome", "label": "Chrome extension",
                      "download": f"{base}/plugins/chrome.zip",
                      "install": "chrome://extensions → Load unpacked (rozpakuj zip)"})
    if _plugin_dir("firefox"):
        items.append({"id": "firefox", "label": "Firefox extension",
                      "download": f"{base}/plugins/firefox.zip",
                      "install": "about:debugging#/runtime/this-firefox → Load Temporary Add-on"})
    items.append({"id": "webpage", "label": "Webpage control (no install)",
                  "open": f"{base}/", "install": "Otwórz URL w przeglądarce — rejestruje się jako webpage node"})
    return {"ok": True, "plugins": items, "serviceUrl": service_url}


# --- HTTP handler -----------------------------------------------------------

def _make_handler(*, service_url: str, bootstrap_script: str | None = None,
                  bind_port: int = DEFAULT_PORT):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # suppress default access log

        def _send(self, code: int, ctype: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, code: int, data: dict) -> None:
            body = json.dumps(data, indent=2).encode()
            self._send(code, "application/json", body)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?")[0]

            if path in ("/", "/index.html"):
                from urirun_service_android_node.page import SETUP_HTML
                body = SETUP_HTML.replace("{{SERVICE_URL}}", service_url)\
                                 .replace("{{LAN_IP}}", _lan_ip())\
                                 .replace("{{PORT}}", str(bind_port))\
                                 .encode()
                self._send(200, "text/html; charset=utf-8", body)

            elif path == "/qr.png":
                try:
                    from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs
                    target = (_parse_qs(_urlparse(self.path).query).get("url") or [""])[0].strip()
                    body = _qr_bytes_for(target) if target else _qr_bytes(service_url)
                    self._send(200, "image/png", body)
                except Exception as exc:
                    self._send_json(500, {"ok": False, "error": str(exc)})

            elif path == "/bootstrap.sh":
                script = _bootstrap_script_path(bootstrap_script)
                if script:
                    body = script.read_bytes()
                    self._send(200, "text/plain; charset=utf-8", body)
                else:
                    self._send_json(404, {"ok": False,
                                          "error": "bootstrap.sh not found"})

            elif path == "/apk/" or path == "/apk":
                items = _list_apks()
                self._send_json(200, {
                    "ok": True,
                    "apks": items,
                    "count": len(items),
                    "apkDirs": [str(p) for p in _apk_dirs()],
                    "hint": "Build or copy an APK into one of apkDirs to enable download." if not items else "",
                })

            elif path.startswith("/apk/"):
                name = path[len("/apk/"):]
                apk = _find_apk(name)
                if apk is None:
                    self._send_json(404, {"ok": False, "error": "APK not found"})
                else:
                    body = apk.read_bytes()
                    self._send(200, "application/vnd.android.package-archive", body)

            elif path in {"/plugins", "/plugins/", "/api/plugins"}:
                self._send_json(200, plugins_index(service_url))

            elif path == "/api/host-services":
                self._send_json(200, host_services(service_url))

            elif path in {"/plugins/chrome.zip", "/plugins/firefox.zip"}:
                name = "chrome" if "chrome" in path else "firefox"
                blob = _zip_plugin(name)
                if blob is None:
                    self._send_json(404, {"ok": False, "error": f"{name}-plugin not found"})
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Disposition", f'attachment; filename="{name}-plugin.zip"')
                    self.send_header("Content-Length", str(len(blob)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(blob)

            elif path == "/api/status":
                adb_bin = shutil.which("adb")
                devices = _adb_devices()
                self._send_json(200, {
                    "ok": True,
                    "service": SERVICE_ID,
                    "port": bind_port,
                    "serviceUrl": service_url,
                    "adb": adb_bin is not None,
                    "adbPath": adb_bin,
                    "devices": devices,
                    "deviceCount": len(devices),
                    "bootstrapAvailable": _bootstrap_script_path(bootstrap_script) is not None,
                    "apkCount": len(_list_apks()),
                    "apkDirs": [str(p) for p in _apk_dirs()],
                })

            elif path in {"/api/web-node/list", "/api/webpage-node/list"}:
                self._send_json(200, web_node_list())

            elif path.startswith("/api/web-node/poll/"):
                dev_id = path[len("/api/web-node/poll/"):]
                self._send_json(200, web_node_poll(dev_id))

            elif path.startswith("/api/webpage-node/poll/"):
                dev_id = path[len("/api/webpage-node/poll/"):]
                self._send_json(200, web_node_poll(dev_id))

            elif path.startswith("/api/web-node/relay/") or path.startswith("/api/webpage-node/relay/"):
                prefix = "/api/web-node/relay/" if path.startswith("/api/web-node/relay/") else "/api/webpage-node/relay/"
                rest = path[len(prefix):]
                dev_id, _, suffix = rest.partition("/")
                # Bare relay URL (no suffix) is the node's root — return its health so the
                # nodeUrl itself responds (host mesh probes <nodeUrl> and <nodeUrl>/health).
                if suffix in ("", "health"):
                    self._send_json(200, web_node_health(dev_id, service_url=service_url))
                elif suffix == "routes":
                    self._send_json(200, web_node_routes(dev_id))
                else:
                    self._send_json(404, {"ok": False, "error": f"not found: {path}"})

            else:
                self._send_json(404, {"ok": False, "error": f"not found: {path}"})

        def do_POST(self):
            path = self.path.split("?")[0]
            if (
                path in {"/api/web-node/register", "/api/web-node/result", "/api/webpage-node/register", "/api/webpage-node/result",
                         "/api/web-node/forget", "/api/webpage-node/forget"}
                or path.startswith("/api/web-node/enqueue/")
                or path.startswith("/api/webpage-node/enqueue/")
                or path.startswith("/api/web-node/relay/")
                or path.startswith("/api/webpage-node/relay/")
            ):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json(400, {"ok": False, "error": "invalid JSON"})
                    return
                if path in {"/api/web-node/register", "/api/webpage-node/register"}:
                    client_ip = self.client_address[0] if self.client_address else ""
                    self._send_json(200, web_node_register(payload, service_url=service_url, client_ip=client_ip))
                elif path in {"/api/web-node/forget", "/api/webpage-node/forget"}:
                    self._send_json(200, web_node_forget(str(payload.get("id") or payload.get("name") or "")))
                elif path in {"/api/web-node/result", "/api/webpage-node/result"}:
                    self._send_json(200, web_node_result(str(payload.get("id") or ""), payload))
                elif path.startswith("/api/web-node/enqueue/") or path.startswith("/api/webpage-node/enqueue/"):
                    prefix = "/api/web-node/enqueue/" if path.startswith("/api/web-node/enqueue/") else "/api/webpage-node/enqueue/"
                    dev_id = path[len(prefix):]
                    self._send_json(200, web_node_enqueue(dev_id, payload))
                else:
                    prefix = "/api/web-node/relay/" if path.startswith("/api/web-node/relay/") else "/api/webpage-node/relay/"
                    rest = path[len(prefix):]
                    dev_id, _, suffix = rest.partition("/")
                    # POST to the bare relay URL (the node's url) OR .../run both dispatch a URI:
                    # the host mesh POSTs {uri, payload} to <node_url> (the standard node /run
                    # contract treats the node URL itself as the run endpoint).
                    if suffix in ("", "run"):
                        self._send_json(200, web_node_run(dev_id, payload))
                    else:
                        self._send_json(404, {"ok": False, "error": f"not found: {path}"})
                return
            if path == "/api/connect":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json(400, {"ok": False, "error": "invalid JSON"})
                    return
                node_url = payload.get("node_url", "").strip()
                node_name = payload.get("node_name", "android").strip()
                if not node_url:
                    self._send_json(400, {"ok": False, "error": "node_url required"})
                    return
                # Quick health check on the node
                try:
                    import urllib.request
                    with urllib.request.urlopen(node_url.rstrip("/") + "/health",
                                               timeout=3) as resp:
                        health = json.loads(resp.read())
                    reachable = True
                except Exception as exc:
                    health = {}
                    reachable = False
                self._send_json(200, {
                    "ok": True,
                    "node_name": node_name,
                    "node_url": node_url,
                    "reachable": reachable,
                    "health": health,
                    "hint": f"urirun host add-node {node_name} {node_url}",
                })
            else:
                self._send_json(404, {"ok": False, "error": f"not found: {path}"})

    return Handler


# --- server lifecycle -------------------------------------------------------

def serve(
    *,
    project: str = ".",
    host: str | None = None,
    port: int | None = None,
    bootstrap_script: str | None = None,
    replace: bool = True,
) -> ThreadingHTTPServer:
    bind_host = host or default_host()
    # port=0 means "ephemeral free port" (used by tests) — honour it instead of falling
    # through to default_port(), so tests never collide with a running service on 8195.
    bind_port = int(port) if port is not None else default_port()
    svc_url = _service_url(bind_host, bind_port)

    # Invalidate cached QR so it regenerates with the new URL. If the cache is
    # outside the writable area (sandbox/read-only home), service startup must
    # still continue; /qr.png can regenerate on a writable cache later.
    try:
        if _QR_CACHE.exists():
            _QR_CACHE.unlink(missing_ok=True)
    except OSError:
        pass

    handler = _make_handler(service_url=svc_url, bootstrap_script=bootstrap_script,
                            bind_port=bind_port)
    server = ThreadingHTTPServer((bind_host, bind_port), handler)
    print(json.dumps({
        "event": "urirun.service_android_node.started",
        "url": svc_url,
        "port": bind_port,
        "service": SERVICE_ID,
    }), flush=True)
    return server


def _free_old_android_node_port(port: int, *, force: bool) -> dict:
    try:
        from urirun.host import service_control
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "port": port,
            "error": f"urirun.host.service_control is not available: {exc}",
            "configure": "install urirun[host] or use a process manager to restart the service",
        }
    return service_control.free_port_from_matching_processes(
        port,
        force=force,
        emit=True,
        is_target=lambda pid: service_control.is_android_node_process(pid),
        event_prefix="urirun.service_android_node",
    )


def _url_for(host: str | None, port: int | None) -> str:
    return _service_url(host or default_host(), int(port or default_port()))


# --- CLI --------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urirun-android-node",
                                     description="urirun Android node setup service")
    sub = parser.add_subparsers(dest="cmd")

    srv = sub.add_parser("serve", help="start the service")
    srv.add_argument("--host", default=None)
    srv.add_argument("--port", type=int, default=None)
    srv.add_argument("--bootstrap-script", default=None)

    rst = sub.add_parser("restart", help="replace any old android-node process on the same port and start")
    rst.add_argument("--host", default=None)
    rst.add_argument("--port", type=int, default=None)
    rst.add_argument("--bootstrap-script", default=None)
    rst.add_argument("--force-replace", action="store_true",
                     help="allow replacing any process that owns the port; default only replaces android-node")

    sub.add_parser("url", help="print service URL")
    sub.add_parser("manifest", help="print service manifest as JSON")
    sub.add_parser("status", help="check ADB devices")

    args = parser.parse_args(list(argv) if argv is not None else None)
    cmd = args.cmd or "serve"

    if cmd == "serve":
        server = serve(host=args.host, port=args.port,
                       bootstrap_script=getattr(args, "bootstrap_script", None))
        print(f"Serving at {_url_for(args.host, args.port)}", file=sys.stderr)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

    elif cmd == "restart":
        port = int(args.port or default_port())
        replaced = _free_old_android_node_port(port, force=bool(args.force_replace))
        if not replaced.get("ok"):
            print(json.dumps({
                "ok": False,
                "event": "urirun.service_android_node.restart_failed",
                "replace": replaced,
            }, indent=2))
            return 1
        server = serve(host=args.host, port=port,
                       bootstrap_script=getattr(args, "bootstrap_script", None))
        print(json.dumps({
            "ok": True,
            "event": "urirun.service_android_node.restart_ready",
            "replace": replaced,
            "url": _url_for(args.host, port),
        }), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

    elif cmd == "url":
        print(_url_for(None, None))

    elif cmd == "manifest":
        print(json.dumps(service_manifest(), indent=2))

    elif cmd == "status":
        adb = shutil.which("adb")
        if not adb:
            print(json.dumps({"ok": False, "error": "adb not found on PATH"}))
            return 1
        devices = _adb_devices()
        print(json.dumps({"ok": True, "devices": devices, "count": len(devices)}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
