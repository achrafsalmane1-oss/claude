#!/usr/bin/env python3
"""Migrate campaigns (names, subjects, bodies, ordering, variants, wait days,
thread-reply flags) from the source workspace to the destination workspace.

Only content is copied. Leads are intentionally NOT touched.
Campaign-level send settings (plain_text, daily caps, unsubscribe) are not
exposed by the write API and must be set in the destination UI.
"""
import json, urllib.request, urllib.error, time, os

SRC_DIR = os.path.join(os.path.dirname(__file__), "source")
# Destination API token is read from the environment to keep secrets out of git.
DTOKEN = os.environ["THERANOW_API_TOKEN"]
DEST = "https://send.theranow.com"

# Source campaign ids in the order we want them created
CAMPAIGNS = [710, 790, 791, 931, 1002, 1053]


def api(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        DEST + path, data=data, method=method,
        headers={"Authorization": "Bearer " + DTOKEN,
                 "Accept": "application/json",
                 "Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req).read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} on {method} {path}: {e.read().decode()}")


def build_steps(src_steps):
    """Turn source steps into a destination sequence_steps payload.

    - base steps keep their integer order
    - variant steps -> order=None, variant_from_step = base step's order
    - for thread_reply steps the destination auto-prepends 'Re: ', so we strip
      one leading 'Re: ' to avoid doubling and to match the source subject text
    """
    id_to_order = {s["id"]: s["order"] for s in src_steps}
    out = []
    # deterministic order: base steps by order first, then their variants
    def sort_key(s):
        if s["order"] is not None:
            return (s["order"], 0)
        base_order = id_to_order.get(s["variant_from_step"]) or 0
        return (base_order, 1)
    for s in sorted(src_steps, key=sort_key):
        subject = s["email_subject"] or ""
        if s["thread_reply"] and subject.startswith("Re: "):
            subject = subject[4:]  # destination will re-add "Re: "
        # source can contain an empty step body; the destination API requires a
        # non-empty body, so fall back to the editor's "blank line" markup
        body = s["email_body"] or ""
        if not body.strip():
            body = "<p><br></p>"
        step = {
            "email_subject": subject,
            "email_body": body,
            "wait_in_days": s["wait_in_days"],
            "active": s["active"],
            "thread_reply": s["thread_reply"],
        }
        if s["variant"]:
            step["order"] = None
            step["variant"] = True
            step["variant_from_step"] = id_to_order.get(s["variant_from_step"])
        else:
            step["order"] = s["order"]
            step["variant"] = False
        out.append(step)
    return out


def main():
    created = []
    for cid in CAMPAIGNS:
        camp = json.load(open(f"{SRC_DIR}/campaign_{cid}.json"))["data"]
        steps = json.load(open(f"{SRC_DIR}/steps_{cid}.json"))["data"]
        name = camp["name"]
        # 1. create the campaign shell
        c = api("POST", "/api/campaigns",
                {"name": name, "type": camp.get("type", "outbound"),
                 "open_tracking": camp.get("open_tracking", False),
                 "sequence_prioritization": camp.get("sequence_prioritization", "followups")})
        new_id = c["data"]["id"]
        # 2. push the full sequence in one bulk call
        payload = {"title": name, "sequence_steps": build_steps(steps)}
        api("POST", f"/api/campaigns/{new_id}/sequence-steps", payload)
        created.append((new_id, name, len(steps)))
        print(f"created campaign {new_id}: {name!r} ({len(steps)} steps)")
        time.sleep(0.5)
    print("\nDONE")
    for nid, name, n in created:
        print(f"  {nid}: {name!r} ({n} steps)")


if __name__ == "__main__":
    main()
