# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Setup page HTML served by the android-node service."""

SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>urirun Android Node Setup</title>
<style>
  :root {
    --bg: #0f172a; --card: #1e293b; --accent: #38bdf8;
    --ok: #4ade80; --warn: #fbbf24; --text: #e2e8f0; --muted: #94a3b8;
    --radius: 12px; --mono: 'Courier New', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif;
         min-height: 100vh; padding: 1rem; }
  header { text-align: center; padding: 2rem 1rem 1rem; }
  header h1 { font-size: 1.8rem; color: var(--accent); margin-bottom: .4rem; }
  header p { color: var(--muted); font-size: .9rem; }
  .qr-center { display: flex; flex-direction: column; align-items: center;
               gap: .5rem; margin: 1.5rem 0; }
  .qr-center img { width: 160px; height: 160px; border-radius: 8px;
                   background: white; padding: 4px; }
  .qr-center .url { font-size: .75rem; color: var(--muted); word-break: break-all; }
  .cards { display: grid; gap: 1rem; max-width: 760px; margin: 0 auto;
           grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
  .card { background: var(--card); border-radius: var(--radius); padding: 1.2rem; }
  .card h2 { font-size: 1rem; color: var(--accent); margin-bottom: .8rem;
             display: flex; align-items: center; gap: .4rem; }
  .card h2 .badge { font-size: .65rem; background: var(--accent);
                    color: var(--bg); padding: 2px 6px; border-radius: 4px; }
  ol, ul { padding-left: 1.2rem; }
  li { margin-bottom: .5rem; font-size: .85rem; line-height: 1.5; }
  code, pre { font-family: var(--mono); background: #0d1117;
              border-radius: 4px; padding: 2px 6px; font-size: .8rem;
              color: var(--ok); word-break: break-all; }
  pre { display: block; padding: .7rem; margin: .5rem 0;
        white-space: pre-wrap; overflow-x: auto; }
  .cmd-copy { position: relative; }
  .cmd-copy button { position: absolute; right: .3rem; top: .3rem;
                     background: var(--accent); color: var(--bg);
                     border: none; border-radius: 4px; padding: 2px 8px;
                     font-size: .7rem; cursor: pointer; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 99px;
          font-size: .7rem; margin-left: .3rem; }
  .pill-usb { background: #334155; color: var(--muted); }
  .pill-wifi { background: #164e63; color: #7dd3fc; }
  #status { background: var(--card); border-radius: var(--radius);
            padding: 1rem; max-width: 760px; margin: 1rem auto; font-size: .8rem; }
  #status h3 { color: var(--accent); margin-bottom: .5rem; }
  #status .device { padding: .3rem .5rem; background: #0d1117;
                    border-radius: 4px; margin: .3rem 0;
                    display: flex; gap: .5rem; align-items: center; }
  #status .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  #status .dot-ok { background: var(--ok); }
  #status .dot-off { background: var(--muted); }
  .route-list { display: grid; gap: .35rem; margin-top: .6rem; }
  .route-list code { display: block; white-space: normal; }
  .service-list { display: grid; gap: .75rem; }
  .service-item { background: #0d1117; border: 1px solid #334155;
                  border-radius: 8px; padding: .75rem; }
  .service-actions { display: flex; flex-wrap: wrap; gap: .5rem;
                     align-items: center; margin-top: .55rem; }
  .service-actions a, .service-actions button {
    background: var(--accent); color: var(--bg); text-decoration: none;
    border: 0; border-radius: 6px; padding: .45rem .7rem; font-weight: 700;
    font-size: .8rem; cursor: pointer;
  }
  .service-actions .secondary { background: #334155; color: var(--text); }
  .service-qr { width: 132px; height: 132px; background: white;
                padding: 4px; border-radius: 8px; margin-top: .55rem; }
  footer { text-align: center; color: var(--muted); font-size: .75rem;
           padding: 2rem 0 1rem; }
  a { color: var(--accent); }
</style>
</head>
<body>

<header>
  <h1>urirun Android Node</h1>
  <p>Connect your Android device to the urirun mesh</p>
</header>

<div class="qr-center">
  <img src="/qr.png" alt="QR code for this page" loading="lazy">
  <div class="url">{{SERVICE_URL}}</div>
  <small style="color:var(--muted);font-size:.7rem">Scan to open this page on your Android device</small>
</div>

<div id="status">
  <h3>ADB device status</h3>
  <div id="device-list"><em style="color:var(--muted)">checking…</em></div>
</div>

<div class="cards">

  <!-- PATH A: ADB control -->
  <div class="card">
    <h2>
      Path A — ADB control
      <span class="badge">immediate</span>
    </h2>
    <p style="font-size:.8rem;color:var(--muted);margin-bottom:.8rem">
      Control the tablet from your computer without installing anything on the device.
    </p>
    <ol>
      <li>On the tablet: <strong>Settings → About tablet → tap Build number 7×</strong> to enable Developer Options</li>
      <li>Go to <strong>Settings → Developer Options → Enable USB debugging</strong> <span class="pill pill-usb">USB</span></li>
      <li>For WiFi ADB, also enable <strong>ADB over network</strong> (port 5555) <span class="pill pill-wifi">WiFi</span></li>
      <li>Connect USB cable, accept the RSA key prompt on the tablet</li>
      <li>On your computer, run:</li>
    </ol>
    <div class="cmd-copy">
      <pre id="adb-connect">adb devices</pre>
      <button onclick="copyCmd('adb-connect')">copy</button>
    </div>
    <p style="font-size:.8rem;margin-top:.6rem">For WiFi ADB (no cable after this):</p>
    <div class="cmd-copy">
      <pre id="wifi-adb">adb tcpip 5555
adb connect TABLET_IP:5555</pre>
      <button onclick="copyCmd('wifi-adb')">copy</button>
    </div>
    <p style="font-size:.8rem;margin-top:.6rem">Then use the ADB connector in urirun:</p>
    <div class="cmd-copy">
      <pre id="adb-capture">ADB_SERIAL=TABLET_IP:5555 urirun run "adb://host/screen/query/capture" \
  --entry-points --execute --allow 'adb://*' --payload '{"output":"screen.png"}'</pre>
      <button onclick="copyCmd('adb-capture')">copy</button>
    </div>
  </div>

  <!-- PATH B: Termux node -->
  <div class="card">
    <h2>
      Path B — Termux node
      <span class="badge">persistent</span>
    </h2>
    <p style="font-size:.8rem;color:var(--muted);margin-bottom:.8rem">
      The tablet becomes a first-class urirun node, like any other registered machine.
    </p>
    <ol>
      <li>Install <strong>F-Droid</strong> from <a href="https://f-droid.org" target="_blank">f-droid.org</a></li>
      <li>In F-Droid, search and install <strong>Termux</strong></li>
      <li>Open Termux and run:</li>
    </ol>
    <div class="cmd-copy">
      <pre id="termux-bootstrap">curl -fsSL {{SERVICE_URL}}bootstrap.sh | bash</pre>
      <button onclick="copyCmd('termux-bootstrap')">copy</button>
    </div>
    <p style="font-size:.8rem;margin-top:.6rem">After bootstrap completes, add the node on your computer:</p>
    <div class="cmd-copy">
      <pre id="add-node">urirun host add-node nexus7 http://TABLET_IP:8765</pre>
      <button onclick="copyCmd('add-node')">copy</button>
    </div>
    <p style="font-size:.8rem;margin-top:.4rem;color:var(--muted)">
      The node auto-starts after reboot if you install <strong>Termux:Boot</strong> from F-Droid.
    </p>
  </div>

  <!-- APK download -->
  <div class="card" id="apk-card">
    <h2>
      Path C — Install APK
      <span class="badge">app</span>
    </h2>
    <p style="font-size:.8rem;color:var(--muted);margin-bottom:.8rem">
      Download and install the urirun node app directly.
      Enable <strong>Install unknown apps</strong> in Android settings first.
    </p>
    <div id="apk-list"><em style="color:var(--muted)">loading…</em></div>
  </div>

  <!-- PATH D: Webpage node -->
  <div class="card">
    <h2>
      Path D — Webpage node
      <span class="badge">browser page</span>
    </h2>
    <p style="font-size:.8rem;color:var(--muted);margin-bottom:.8rem">
      This page registers itself as a <strong>webpage</strong> node. The host can
      see it immediately, inspect its URI routes and control page-local features
      through the relay endpoint.
    </p>
    <div id="webpage-node-status" style="font-size:.8rem;color:var(--muted)">registering…</div>
    <h3 style="font-size:.85rem;margin:.8rem 0 .4rem;color:var(--accent)">URI processes</h3>
    <div id="webpage-route-list" class="route-list"><em style="color:var(--muted)">loading…</em></div>
    <h3 style="font-size:.85rem;margin:.8rem 0 .4rem;color:var(--accent)">Browser devices</h3>
    <div id="webpage-device-list" style="font-size:.8rem;color:var(--muted)">checking…</div>
  </div>

  <!-- PATH E: Host services delegated to phone -->
  <div class="card">
    <h2>
      Path E — Host services
      <span class="badge">delegated</span>
    </h2>
    <p style="font-size:.8rem;color:var(--muted);margin-bottom:.8rem">
      Open host-side services that are useful on this phone. The service still
      runs on the host; the phone is the UI/device surface.
    </p>
    <div id="host-service-list" class="service-list"><em style="color:var(--muted)">loading…</em></div>
  </div>

</div>

<footer>
  <p>urirun Android node service · port {{PORT}} · <a href="/api/status">API status</a></p>
</footer>

<script>
function copyCmd(id) {
  const text = document.getElementById(id).textContent;
  navigator.clipboard.writeText(text).catch(() => {});
}

function copyTextFrom(el) {
  const text = el && el.getAttribute ? (el.getAttribute('data-copy-url') || '') : '';
  navigator.clipboard.writeText(text).catch(() => {});
}

function escHtml(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);
}

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const el = document.getElementById('device-list');
    if (!d.adb) {
      el.innerHTML = '<span style="color:var(--warn)">adb not found on PATH — install Android platform-tools</span>';
      return;
    }
    if (!d.devices || d.devices.length === 0) {
      el.innerHTML = '<span style="color:var(--muted)">No devices connected. Enable USB debugging and connect a cable.</span>';
      return;
    }
    el.innerHTML = d.devices.map(dev =>
      `<div class="device">
        <span class="dot ${dev.state === 'device' ? 'dot-ok' : 'dot-off'}"></span>
        <code>${dev.serial}</code>
        <span>${dev.model || ''}</span>
        <span style="color:var(--muted)">${dev.state}</span>
      </div>`
    ).join('');
  } catch (e) {
    document.getElementById('device-list').textContent = 'Could not load status.';
  }
}

function apkMeta(name) {
  // Parse APK filename \u2192 human-readable arch + Android version labels
  const archMap = {
    'arm64-v8a_armeabi-v7a': { label: '64+32-bit (universal)', note: 'Android 12+' },
    'arm64-v8a':              { label: '64-bit arm64',          note: 'Android 12+ (Pixel 4+, most 2019+ phones)' },
    'armeabi-v7a':            { label: '32-bit arm',            note: 'Android 12+ (older/low-end phones)' },
    'x86_64':                 { label: 'x86_64',                note: 'Android 12+ (emulator)' },
  };
  for (const [key, meta] of Object.entries(archMap)) {
    if (name.includes(key)) return meta;
  }
  return { label: '', note: 'Android 12+' };
}

async function loadApks() {
  try {
    const r = await fetch('/apk/');
    const d = await r.json();
    if (d.apks && d.apks.length > 0) {
      document.getElementById('apk-list').innerHTML = d.apks.map(a => {
        const apkUrl = location.origin + a.url;
        const meta = apkMeta(a.name);
        const mb = (a.bytes / 1024 / 1024).toFixed(1);
        return `<div style="margin:.6rem 0;padding:.6rem;background:#0d1117;border-radius:6px">
          <div style="margin-bottom:.35rem">
            <a href="${a.url}" download style="color:var(--ok);font-weight:bold">${a.name}</a>
            <span style="color:var(--muted);font-size:.75rem"> ${mb}\u00a0MB</span>
          </div>
          ${meta.label ? `<div style="font-size:.78rem;color:var(--accent);margin-bottom:.2rem">${meta.label} \u2014 ${meta.note}</div>` : ''}
          <div class="qr-center" style="margin:.5rem 0 0">
            <img src="/qr.png?url=${encodeURIComponent(apkUrl)}" alt="QR APK" loading="lazy" style="width:140px;height:140px">
            <small style="color:var(--muted);font-size:.7rem">Zeskanuj, aby pobra\u0107 APK na telefon</small>
            <div class="url" style="font-size:.7rem;word-break:break-all">${apkUrl}</div>
          </div>
        </div>`;
      }).join('');
    } else {
      const dirs = (d.apkDirs || []).map(p => `<li><code>${p}</code></li>`).join('');
      document.getElementById('apk-list').innerHTML =
        `<div style="color:var(--warn);font-size:.82rem;margin-bottom:.6rem">Brak APK. Skompiluj i skopiuj plik do jednego z katalog\u00f3w poni\u017cej.</div>
         <ul style="font-size:.75rem;color:var(--muted);padding-left:1.1rem;margin-bottom:.5rem">${dirs}</ul>
         <div class="cmd-copy">
           <pre id="apk-build">cd ~/github/if-uri/urirun-android-node-app
URIRUN_ANDROID_BUILD_SKIP_IMAGE=1 make docker-apk</pre>
           <button onclick="copyCmd('apk-build')">copy</button>
         </div>`;
    }
  } catch (e) {
    document.getElementById('apk-list').textContent = 'Nie mo\u017cna za\u0142adowa\u0107 listy APK.';
  }
}

async function loadHostServices() {
  const el = document.getElementById('host-service-list');
  if (!el) return;
  try {
    const r = await fetch('/api/host-services', { cache: 'no-store' });
    const d = await r.json();
    const services = Array.isArray(d.services) ? d.services : [];
    if (!services.length) {
      el.innerHTML = '<span style="color:var(--muted)">No phone-delegated host services reported.</span>';
      return;
    }
    el.innerHTML = services.map((svc) => {
      const url = String(svc.url || '');
      const routes = Array.isArray(svc.routes) ? svc.routes : [];
      return `<div class="service-item">
        <div><strong>${escHtml(svc.label || svc.name || svc.id || 'Service')}</strong>
          <span class="pill pill-wifi">${escHtml(svc.kind || 'service')}</span></div>
        <div style="font-size:.78rem;color:var(--muted);margin-top:.25rem">${escHtml(svc.description || '')}</div>
        <div class="service-actions">
          <a href="${escHtml(url)}" target="_self" rel="noreferrer">Open</a>
          <button type="button" class="secondary" data-copy-url="${escHtml(url)}" onclick="copyTextFrom(this)">copy URL</button>
        </div>
        <img class="service-qr" src="/qr.png?url=${encodeURIComponent(url)}" alt="QR ${escHtml(svc.label || svc.id || url)}" loading="lazy">
        <div class="url" style="font-size:.7rem;word-break:break-all;margin-top:.4rem">${escHtml(url)}</div>
        ${routes.length ? '<div class="route-list">' + routes.map((uri) => '<code>' + escHtml(uri) + '</code>').join('') + '</div>' : ''}
      </div>`;
    }).join('');
  } catch (e) {
    el.textContent = 'Could not load host services.';
  }
}

loadStatus();
loadApks();
loadHostServices();
setInterval(loadStatus, 10000);

// === Webpage-node client ===
// Opening this page on a phone/browser auto-registers the device as a "webpage node": it shows up in
// the host dashboard immediately (stage 1), controllable via JS actions relayed by the service.
// Installing the APK/Termux later upgrades it to a full "mobile node" (stage 2).
(function webNode() {
  let id = localStorage.getItem('urirun-webnode-id') || '';
  let routes = [];

  function renderRoutes() {
    const el = document.getElementById('webpage-route-list');
    if (!el) return;
    el.innerHTML = (routes || []).map((uri) => '<code>' + uri + '</code>').join('') ||
      '<span style="color:var(--muted)">no routes yet</span>';
  }

  async function renderDevices() {
    const el = document.getElementById('webpage-device-list');
    if (!el) return;
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        el.textContent = 'mediaDevices.enumerateDevices is not available in this browser/context';
        return;
      }
      const list = await navigator.mediaDevices.enumerateDevices();
      el.innerHTML = list.map((d) => '<div><code>' + d.kind + '</code> ' + (d.label || '(permission required for label)') + '</div>').join('') ||
        '<span style="color:var(--muted)">no media devices reported</span>';
    } catch (e) {
      el.textContent = 'Could not list devices: ' + e;
    }
  }

  async function register() {
    try {
      const r = await fetch('/api/webpage-node/register', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ id, userAgent: navigator.userAgent, name: '', pageUrl: location.href })
      });
      const d = await r.json();
      if (d.ok && d.id) {
        id = d.id;
        routes = d.routes || [];
        localStorage.setItem('urirun-webnode-id', id);
        const status = document.getElementById('webpage-node-status');
        if (status) status.innerHTML = 'Registered as <code>' + (d.name || id) + '</code>'
          + '<br>Device: <code>' + (d.clientIp || 'unknown') + '</code>'
          + '<br>Relay: <code>' + (d.nodeUrl || '') + '</code>';
        renderRoutes();
        renderDevices();
      }
    } catch (e) {}
  }
  async function runAction(a) {
    // Execute a relayed action in this browser/page and return a result.
    try {
      if (a.type === 'navigate' && a.url) { location.href = a.url; return { navigated: a.url }; }
      if (a.type === 'eval' && a.expression) {
        // eslint-disable-next-line no-eval
        const v = eval(a.expression); return { value: v };
      }
      if (a.type === 'info') {
        return {
          title: document.title,
          url: location.href,
          origin: location.origin,
          readyState: document.readyState,
          viewport: { width: innerWidth, height: innerHeight },
          scroll: { x: scrollX, y: scrollY }
        };
      }
      if (a.type === 'text') { return { text: (document.body ? document.body.innerText : '').slice(0, 20000) }; }
      if (a.type === 'devices') {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return { supported: false, devices: [] };
        const list = await navigator.mediaDevices.enumerateDevices();
        return { supported: true, devices: list.map((d) => ({ kind: d.kind, label: d.label || '' })) };
      }
      if (a.type === 'camera-start') {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return { ok: false, error: 'camera API not supported' };
        const stream = await navigator.mediaDevices.getUserMedia(a.constraints || { video: true, audio: false });
        let video = document.getElementById('urirun-webpage-camera');
        if (!video) {
          video = document.createElement('video');
          video.id = 'urirun-webpage-camera';
          video.autoplay = true; video.muted = true; video.playsInline = true;
          video.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:2147483647;width:240px;max-width:35vw;border:2px solid #38bdf8;background:#000';
          document.documentElement.appendChild(video);
        }
        video.srcObject = stream;
        renderDevices();
        return { ok: true, tracks: stream.getTracks().map((t) => ({ kind: t.kind, label: t.label || '', readyState: t.readyState })) };
      }
      if (a.type === 'sensors') {
        return {
          deviceMotion: typeof DeviceMotionEvent !== 'undefined',
          deviceOrientation: typeof DeviceOrientationEvent !== 'undefined',
          geolocation: !!navigator.geolocation,
          mediaDevices: !!(navigator.mediaDevices && navigator.mediaDevices.enumerateDevices)
        };
      }
      if (a.type === 'activity') {
        return { visible: document.visibilityState, focused: document.hasFocus(), scroll: { x: scrollX, y: scrollY } };
      }
      if (a.type === 'iframe' && a.url) {
        let frame = document.getElementById(a.frameId || 'urirun-webpage-frame');
        if (!frame) {
          frame = document.createElement('iframe');
          frame.id = a.frameId || 'urirun-webpage-frame';
          frame.style.cssText = 'position:fixed;inset:5vh 5vw;z-index:2147483646;width:90vw;height:90vh;border:2px solid #38bdf8;background:#fff';
          document.documentElement.appendChild(frame);
        }
        frame.src = a.url;
        return { opened: a.url, note: 'target page may block iframe embedding' };
      }
      if (a.type === 'screenshot') {
        // best-effort: render the visible DOM size; full pixel capture needs getDisplayMedia
        return { note: 'screenshot not supported in plain webpage node; use mobile node (APK)' };
      }
      return { error: 'unknown action ' + a.type };
    } catch (e) { return { error: String(e) }; }
  }
  async function poll() {
    if (!id) { await register(); }
    try {
      const r = await fetch('/api/webpage-node/poll/' + encodeURIComponent(id));
      const d = await r.json();
      if (d.ok && d.actions) {
        for (const a of d.actions) {
          const result = await runAction(a);
          fetch('/api/webpage-node/result', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id, actionId: a.id || '', result })
          }).catch(() => {});
        }
      }
    } catch (e) {}
  }
  register().then(() => { poll(); setInterval(poll, 3000); });
})();
</script>
</body>
</html>
"""
