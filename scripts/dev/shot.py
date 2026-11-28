"""Headless Edge over CDP: load the app, run JS steps, screenshot.

usage: shot.py <out.png> [js-step ...]     (each step is followed by a short pause)
       LR_SHOT_URL overrides the page (default http://127.0.0.1:8765/)
       LR_SHOT_SCALE sets the device scale factor (default 2; use 1 for WebGL pages, rendered in software)
Helpers available to steps:  type(i, text)  -> sets add-row input i and fires input
                             click(text)    -> clicks the first button containing text
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

from websockets.sync.client import connect

OUT, STEPS = sys.argv[1], sys.argv[2:]
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edgeprof")
HELPERS = """
window.type = (i, v) => {
  const el = document.querySelectorAll('.add-row input')[i];
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  el.focus(); setter.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true}));
};
window.click = (t) => [...document.querySelectorAll('button')].find(b => b.innerText.includes(t)).click();
"""

proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                         "--remote-debugging-port=9333", "--remote-allow-origins=*",
                         f"--user-data-dir={PROFILE}", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
n = 0
try:
    for _ in range(100):
        try:
            targets = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json/list"))
            page = next(t for t in targets if t["type"] == "page")
            break
        except Exception:
            time.sleep(0.2)
    ws = connect(page["webSocketDebuggerUrl"], max_size=50_000_000)

    def cmd(method, **params):
        global n
        n += 1
        ws.send(json.dumps({"id": n, "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    cmd("Emulation.setDeviceMetricsOverride", width=1600, height=940,
        deviceScaleFactor=float(os.environ.get("LR_SHOT_SCALE", "2")), mobile=False)
    cmd("Emulation.setFocusEmulationEnabled", enabled=True)
    cmd("Page.navigate", url=os.environ.get("LR_SHOT_URL", "http://127.0.0.1:8765/"))
    time.sleep(2.5)
    cmd("Runtime.evaluate", expression=HELPERS)
    for step in STEPS:
        r = cmd("Runtime.evaluate", expression=step, awaitPromise=True, returnByValue=True)
        if r.get("exceptionDetails"):
            print("step failed:", step, r["exceptionDetails"].get("exception", {}).get("description"))
        elif r.get("result", {}).get("value") is not None:
            print("step returned:", r["result"]["value"])
        time.sleep(0.8)
    time.sleep(0.5)
    shot = cmd("Page.captureScreenshot", format="png")
    open(OUT, "wb").write(base64.b64decode(shot["data"]))
    print("wrote", OUT)
finally:
    try:
        cmd("Browser.close")
    except Exception:
        pass
    time.sleep(0.5)
    proc.terminate()
