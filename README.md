# urirun-service-android-node

Service on port `8195` for connecting Android devices and browser pages to a urirun host.

Two separate roles:

- **Android setup** — QR page, ADB instructions, Termux bootstrap, APK download.
- **Webpage node relay** — any browser page that opens the service URL registers as a `webpage` node and exposes `/health`, `/routes`, `/run` through the relay.

## Start

```bash
urirun-android-node serve --host 0.0.0.0 --port 8195
```

Open the printed URL on a phone or another browser. To replace an old process on the same port:

```bash
urirun-android-node restart --host 0.0.0.0 --port 8195 --force-replace
```

## APK download

The setup page (Path C) shows available APKs with a QR code for direct phone download.

```
GET /apk/        — JSON list of available APKs
GET /apk/<file>  — download APK
```

Current APK:

| File | Arch | Android | Size |
|---|---|---|---|
| `urirunnode-0.3.0-arm64-v8a-debug.apk` | arm64-v8a (64-bit) | 12+ (API 31) | 18 MB |

The service checks these directories (first match wins per filename):

1. `URIRUN_ANDROID_NODE_APK_DIRS` or `URIRUN_ANDROID_NODE_APK_DIR` (env override)
2. `urirun-service-android-node/apk/` ← stable distribution location
3. `urirun-android-node-app/bin/` ← Buildozer output
4. `android-node-app/bin/`
5. `~/.urirun/android-node/apk/`

To build and publish a new APK:

```bash
cd /home/tom/github/if-uri/urirun-android-node-app
URIRUN_ANDROID_BUILD_SKIP_IMAGE=1 make docker-apk
```

`docker-apk` copies the result to `urirun-service-android-node/apk/` automatically.
The page reloads the list dynamically — no service restart needed.

## Browser plugins

```
GET /plugins              — JSON list of available plugins
GET /plugins/chrome.zip   — Chrome extension zip
GET /plugins/firefox.zip  — Firefox extension zip
```

Plugins are served when their source directories exist next to this repo:

```bash
cd /home/tom/github/if-uri/chrome-plugin && make package
# Chrome: chrome://extensions → Developer mode → Load unpacked

cd /home/tom/github/if-uri/firefox-plugin && make package
# Firefox: about:debugging → Load Temporary Add-on → manifest.json
```

## Webpage node relay

Opening the setup page on a phone/browser auto-registers it as a `webpage` node.
The host can reach it immediately through the relay endpoint.

```
GET  /api/webpage-node/list
GET  /api/webpage-node/relay/<id>/health
GET  /api/webpage-node/relay/<id>/routes
POST /api/webpage-node/relay/<id>/run
POST /api/webpage-node/register
POST /api/webpage-node/forget
```

Routes exposed per device (replace `{id}` with the assigned device id):

```
webpage://{id}/page/query/info
webpage://{id}/page/query/text
webpage://{id}/page/query/devices
webpage://{id}/page/command/navigate
webpage://{id}/page/command/eval
webpage://{id}/camera/query/status
webpage://{id}/camera/command/start
webpage://{id}/sensor/query/capabilities
webpage://{id}/user/query/activity
webpage://{id}/iframe/command/open
```

Legacy `/api/web-node/...` endpoints are accepted as aliases.

## All endpoints

```
GET  /                          setup page (HTML)
GET  /qr.png                    QR code for this page (or ?url=... for arbitrary URL)
GET  /bootstrap.sh              Termux bootstrap script
GET  /apk/                      APK list (JSON)
GET  /apk/<file>                APK download
GET  /plugins                   browser plugin list (JSON)
GET  /plugins/chrome.zip        Chrome extension
GET  /plugins/firefox.zip       Firefox extension
GET  /api/status                ADB devices + service info
POST /api/connect               register an Android node by IP:port
GET  /api/webpage-node/list     list connected webpage nodes
GET  /api/webpage-node/relay/<id>/health
GET  /api/webpage-node/relay/<id>/routes
POST /api/webpage-node/relay/<id>/run
```
