"""Drive the demo server into a screenshot-worthy state."""
import json
import sys
import time
import urllib.request

B = "http://127.0.0.1:8765/api"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(B + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(r) as resp:
        return json.load(resp)


for _ in range(30):
    try:
        req("GET", "/state")
        break
    except Exception:
        time.sleep(0.5)
else:
    sys.exit("server not up")

req("POST", "/sheet/triples", {"s": "ex:target", "p": "rdfs:label", "o": '"my demo folder"'})
approvals = 0
stop_at = int(sys.argv[1]) if len(sys.argv) > 1 else 2
max_applied = int(sys.argv[2]) if len(sys.argv) > 2 else 999
applied = 0
for i in range(40):
    st = req("POST", "/autopilot/step")["status"]
    print("step", i + 1, st)
    if st == "awaiting-approval":
        approvals += 1
        if approvals >= stop_at:
            break
        call = req("GET", "/state")["pending"][0]
        body = {"id": call["id"], "approve": True}
        if len(sys.argv) > 3 and sys.argv[3] == "remember":
            body["remember"] = call["suggested"]
        req("POST", "/approvals", body)
    if st == "done":
        break
    if st == "applied":
        applied += 1
        if applied >= max_applied:
            break

s = req("GET", "/state")
print("tick", s["tick"], s["autopilot"], s["pending"])
for a in req("GET", "/applications")["applications"]:
    print(" ", a["operation"], a["total"], a["valid"])
