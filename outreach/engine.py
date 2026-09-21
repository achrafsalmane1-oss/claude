"""Waterfall sequence engine: schedules steps, auto-sends email, queues manual work."""
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import db
import mailer

CHANNEL_FIELD = {"email": "email", "linkedin": "linkedin_url", "call": "phone"}
DEAD_STATUSES = ("unsubscribed", "do_not_contact", "bounced")
_lock = threading.Lock()
_stop = threading.Event()
_state = {"last_tick": None, "last_imap": None, "last_error": "", "sent_this_tick": 0}


def parse_iso(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def utcnow():
    return datetime.now(timezone.utc)


def step_delay(step):
    return timedelta(days=int(step.get("delay_days") or 0), hours=int(step.get("delay_hours") or 0))


def sequence_steps(sequence_id):
    return db.query(
        "SELECT * FROM steps WHERE sequence_id = ? ORDER BY position ASC, id ASC", (sequence_id,)
    )


def required_field(step):
    return step.get("requires_field") or CHANNEL_FIELD.get(step["channel"], "")


def in_send_window(campaign, when=None):
    local = (when or utcnow()).astimezone()
    if campaign.get("weekdays_only") and local.weekday() >= 5:
        return False
    start = int(campaign.get("window_start") or 0)
    end = int(campaign.get("window_end") or 24)
    return start <= local.hour < end


def next_window_open(campaign, when=None):
    local = (when or utcnow()).astimezone()
    start = int(campaign.get("window_start") or 0)
    end = int(campaign.get("window_end") or 24)
    candidate = local.replace(minute=0, second=0, microsecond=0)
    if local.hour < start:
        candidate = candidate.replace(hour=start)
    else:
        candidate = (candidate + timedelta(days=1)).replace(hour=start)
    if campaign.get("weekdays_only"):
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
    if start >= end:  # misconfigured window, do not spin
        candidate = local + timedelta(hours=1)
    return candidate.astimezone(timezone.utc)


def sent_today(campaign_id):
    day = utcnow().astimezone().strftime("%Y-%m-%d")
    row = db.query_one("SELECT count FROM sendlog WHERE day = ? AND campaign_id = ?", (day, campaign_id))
    return row["count"] if row else 0


def bump_sent(campaign_id):
    day = utcnow().astimezone().strftime("%Y-%m-%d")
    db.execute(
        "INSERT INTO sendlog(day, campaign_id, count) VALUES (?, ?, 1) "
        "ON CONFLICT(day, campaign_id) DO UPDATE SET count = count + 1",
        (day, campaign_id),
    )


# ---------------------------------------------------------------- enrollment


def enroll(campaign_id, contact_ids):
    campaign = db.query_one("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    if not campaign:
        return {"added": 0, "skipped": 0, "error": "campaign not found"}
    steps = sequence_steps(campaign["sequence_id"])
    if not steps:
        return {"added": 0, "skipped": 0, "error": "sequence has no steps"}
    added = skipped = 0
    first_due = utcnow() + step_delay(steps[0])
    for cid in contact_ids:
        contact = db.query_one("SELECT * FROM contacts WHERE id = ?", (cid,))
        if not contact or contact["status"] in DEAD_STATUSES:
            skipped += 1
            continue
        exists = db.query_one(
            "SELECT id FROM enrollments WHERE campaign_id = ? AND contact_id = ?", (campaign_id, cid)
        )
        if exists:
            skipped += 1
            continue
        db.insert("enrollments", {
            "campaign_id": campaign_id,
            "contact_id": cid,
            "status": "active",
            "step_index": 0,
            "next_action_at": first_due.isoformat(),
            "created_at": db.now_iso(),
            "updated_at": db.now_iso(),
        })
        added += 1
    return {"added": added, "skipped": skipped}


def finish_enrollment(enrollment, status):
    db.update("enrollments", enrollment["id"], {
        "status": status, "next_action_at": None, "updated_at": db.now_iso()
    })


def advance(enrollment, steps, next_index, from_time=None):
    """Schedule the next step, using that step's own delay."""
    base = from_time or utcnow()
    if next_index >= len(steps):
        finish_enrollment(enrollment, "finished")
        return
    due = base + step_delay(steps[next_index])
    db.update("enrollments", enrollment["id"], {
        "status": "active",
        "step_index": next_index,
        "next_action_at": due.isoformat(),
        "updated_at": db.now_iso(),
    })


def open_task_for(enrollment_id, step_id):
    return db.query_one(
        "SELECT id FROM tasks WHERE enrollment_id = ? AND step_id = ? AND status = 'pending'",
        (enrollment_id, step_id),
    )


def create_task(enrollment, campaign, step, contact):
    if open_task_for(enrollment["id"], step["id"]):
        return None
    subject = mailer.render(step.get("subject", ""), contact)
    body = mailer.render(step.get("body", ""), contact)
    tid = db.insert("tasks", {
        "enrollment_id": enrollment["id"],
        "campaign_id": campaign["id"],
        "contact_id": contact["id"],
        "step_id": step["id"],
        "step_index": enrollment["step_index"],
        "channel": step["channel"],
        "action": step.get("action") or "message",
        "status": "pending",
        "due_at": db.now_iso(),
        "subject": subject,
        "body": body,
        "created_at": db.now_iso(),
    })
    db.update("enrollments", enrollment["id"], {"status": "waiting", "updated_at": db.now_iso()})
    return tid


def process_enrollment(enrollment, campaign, steps):
    """Run an enrollment forward, falling through steps whose channel data is missing."""
    guard = 0
    enrollment = dict(enrollment)
    while guard < len(steps) + 2:
        guard += 1
        idx = enrollment["step_index"]
        if idx >= len(steps):
            finish_enrollment(enrollment, "finished")
            return
        step = steps[idx]
        contact = db.query_one("SELECT * FROM contacts WHERE id = ?", (enrollment["contact_id"],))
        if not contact:
            finish_enrollment(enrollment, "stopped")
            return
        if contact["status"] in DEAD_STATUSES:
            finish_enrollment(enrollment, "stopped")
            return
        if campaign.get("stop_on_reply") and contact["status"] == "replied":
            finish_enrollment(enrollment, "replied")
            return

        field = required_field(step)
        if field and not (contact.get(field) or "").strip():
            db.log_event(contact["id"], campaign["id"], idx, step["channel"], "skipped",
                         {"reason": "missing " + field})
            if (step.get("on_missing") or "skip") == "stop":
                finish_enrollment(enrollment, "stopped")
                return
            enrollment["step_index"] = idx + 1  # waterfall: fall straight through
            db.update("enrollments", enrollment["id"], {"step_index": idx + 1})
            continue

        if step["channel"] == "email" and step.get("auto_send", 1):
            if not in_send_window(campaign):
                db.update("enrollments", enrollment["id"], {
                    "next_action_at": next_window_open(campaign).isoformat(),
                    "updated_at": db.now_iso(),
                })
                return
            if sent_today(campaign["id"]) >= int(campaign.get("daily_limit") or 0) > 0:
                db.update("enrollments", enrollment["id"], {
                    "next_action_at": next_window_open(campaign).isoformat(),
                    "updated_at": db.now_iso(),
                })
                return
            subject = mailer.render(step.get("subject", ""), contact)
            body = mailer.render(step.get("body", ""), contact)
            signature = db.get_settings().get("signature", "")
            if signature and "{{signature}}" not in (step.get("body") or ""):
                body = body.rstrip() + "\n\n" + signature
            ok, _mid, err = mailer.send_email(contact, subject, body, campaign["id"])
            bump_sent(campaign["id"])
            _state["sent_this_tick"] += 1
            db.insert("tasks", {
                "enrollment_id": enrollment["id"],
                "campaign_id": campaign["id"],
                "contact_id": contact["id"],
                "step_id": step["id"],
                "step_index": idx,
                "channel": "email",
                "action": "message",
                "status": "done" if ok else "failed",
                "due_at": db.now_iso(),
                "subject": subject,
                "body": body,
                "outcome": "auto-sent" if ok else "send failed",
                "notes": err,
                "created_at": db.now_iso(),
                "completed_at": db.now_iso(),
            })
            advance(enrollment, steps, idx + 1)
            return

        create_task(enrollment, campaign, step, contact)
        return


def tick():
    """One scheduler pass. Safe to call from the UI as well as the background loop."""
    with _lock:
        _state["sent_this_tick"] = 0
        settings = db.get_settings()
        if settings.get("engine_enabled", "1") != "1":
            _state["last_tick"] = db.now_iso()
            return {"ok": True, "skipped": "engine disabled"}
        processed = 0
        now = utcnow().isoformat()
        for campaign in db.query("SELECT * FROM campaigns WHERE status = 'running'"):
            steps = sequence_steps(campaign["sequence_id"])
            if not steps:
                continue
            due = db.query(
                "SELECT * FROM enrollments WHERE campaign_id = ? AND status = 'active' "
                "AND next_action_at IS NOT NULL AND next_action_at <= ? ORDER BY next_action_at ASC LIMIT 200",
                (campaign["id"], now),
            )
            for enrollment in due:
                try:
                    process_enrollment(enrollment, campaign, steps)
                    processed += 1
                except Exception as exc:  # noqa: BLE001 - one bad row must not stop the loop
                    _state["last_error"] = "%s: %s" % (type(exc).__name__, exc)
                    finish_enrollment(enrollment, "stopped")
            remaining = db.query_one(
                "SELECT COUNT(*) AS n FROM enrollments WHERE campaign_id = ? AND status IN ('active','waiting')",
                (campaign["id"],),
            )
            if remaining and remaining["n"] == 0:
                db.update("campaigns", campaign["id"], {"status": "done", "updated_at": db.now_iso()})
        _state["last_tick"] = db.now_iso()
        return {"ok": True, "processed": processed, "sent": _state["sent_this_tick"]}


# ------------------------------------------------------------ task outcomes


def complete_task(task_id, outcome="", notes="", body=None, log_message=True):
    task = db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        return {"ok": False, "error": "task not found"}
    contact = db.query_one("SELECT * FROM contacts WHERE id = ?", (task["contact_id"],))
    final_body = body if body is not None else task["body"]

    if task["channel"] == "email" and not task.get("action") == "note":
        ok, _mid, err = mailer.send_email(contact, task["subject"], final_body, task["campaign_id"], task_id)
        if not ok:
            db.update("tasks", task_id, {"status": "failed", "notes": err, "completed_at": db.now_iso()})
            return {"ok": False, "error": err}
        if task.get("campaign_id"):
            bump_sent(task["campaign_id"])
    elif log_message:
        db.insert("messages", {
            "contact_id": contact["id"],
            "campaign_id": task["campaign_id"],
            "task_id": task_id,
            "channel": task["channel"],
            "direction": "out",
            "subject": task["subject"] or (outcome or task["channel"]),
            "body": final_body if task["channel"] == "linkedin" else (final_body + (
                "\n\n--- call notes ---\n" + notes if notes else "")),
            "status": "sent",
            "created_at": db.now_iso(),
        })
        db.touch_thread(contact["id"], "out", task["channel"], outcome or final_body)
        db.execute("UPDATE contacts SET status = 'active' WHERE id = ? AND status = 'new'", (contact["id"],))
        db.log_event(contact["id"], task["campaign_id"], task["step_index"], task["channel"],
                     "call" if task["channel"] == "call" else "linkedin",
                     {"outcome": outcome, "notes": notes})

    db.update("tasks", task_id, {
        "status": "done", "outcome": outcome, "notes": notes,
        "body": final_body, "completed_at": db.now_iso(),
    })
    _resume_after_task(task)
    return {"ok": True}


def skip_task(task_id, reason=""):
    task = db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        return {"ok": False, "error": "task not found"}
    db.update("tasks", task_id, {
        "status": "skipped", "outcome": "skipped", "notes": reason, "completed_at": db.now_iso()
    })
    db.log_event(task["contact_id"], task["campaign_id"], task["step_index"], task["channel"],
                 "skipped", {"reason": reason})
    _resume_after_task(task)
    return {"ok": True}


def _resume_after_task(task):
    if not task.get("enrollment_id"):
        return
    enrollment = db.query_one("SELECT * FROM enrollments WHERE id = ?", (task["enrollment_id"],))
    if not enrollment or enrollment["status"] in ("replied", "stopped", "finished"):
        return
    campaign = db.query_one("SELECT * FROM campaigns WHERE id = ?", (enrollment["campaign_id"],))
    if not campaign:
        return
    steps = sequence_steps(campaign["sequence_id"])
    advance(enrollment, steps, enrollment["step_index"] + 1)
    # If the next step is due right away, surface it now instead of waiting for the next tick.
    fresh = db.query_one("SELECT * FROM enrollments WHERE id = ?", (enrollment["id"],))
    if (fresh and fresh["status"] == "active" and campaign["status"] == "running"
            and fresh["next_action_at"] and fresh["next_action_at"] <= utcnow().isoformat()):
        try:
            process_enrollment(fresh, campaign, steps)
        except Exception as exc:  # noqa: BLE001
            _state["last_error"] = "%s: %s" % (type(exc).__name__, exc)


# ------------------------------------------------------------ inbound signals


def _stop_enrollments(contact_id, status, only_stop_on_reply=False):
    sql = "SELECT e.* FROM enrollments e JOIN campaigns c ON c.id = e.campaign_id " \
          "WHERE e.contact_id = ? AND e.status IN ('active','waiting')"
    params = [contact_id]
    if only_stop_on_reply:
        sql += " AND c.stop_on_reply = 1"
    for enrollment in db.query(sql, tuple(params)):
        db.update("enrollments", enrollment["id"], {
            "status": status, "next_action_at": None, "updated_at": db.now_iso()
        })
        db.execute(
            "UPDATE tasks SET status = 'skipped', outcome = ?, completed_at = ? "
            "WHERE enrollment_id = ? AND status = 'pending'",
            (status, db.now_iso(), enrollment["id"]),
        )


def register_reply(contact_id, channel="email", note=""):
    db.update("contacts", contact_id, {"status": "replied", "updated_at": db.now_iso()})
    db.log_event(contact_id, None, None, channel, "reply", {"note": note})
    _stop_enrollments(contact_id, "replied", only_stop_on_reply=True)


def register_bounce(contact_id):
    contact = db.query_one("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    db.update("contacts", contact_id, {"status": "bounced", "updated_at": db.now_iso()})
    if contact and contact.get("email"):
        db.execute(
            "INSERT OR IGNORE INTO suppressions(value, kind, reason, created_at) VALUES (?,?,?,?)",
            (contact["email"].lower(), "email", "bounce", db.now_iso()),
        )
    db.log_event(contact_id, None, None, "email", "bounce", {})
    _stop_enrollments(contact_id, "bounced")


def unsubscribe(contact_id, reason="unsubscribed"):
    contact = db.query_one("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    db.update("contacts", contact_id, {"status": "unsubscribed", "updated_at": db.now_iso()})
    if contact and contact.get("email"):
        db.execute(
            "INSERT OR IGNORE INTO suppressions(value, kind, reason, created_at) VALUES (?,?,?,?)",
            (contact["email"].lower(), "email", reason, db.now_iso()),
        )
    db.log_event(contact_id, None, None, "email", "unsubscribe", {"reason": reason})
    _stop_enrollments(contact_id, "stopped")


# ------------------------------------------------------------ background loop


def _loop():
    last_imap = 0.0
    while not _stop.is_set():
        try:
            tick()
            st = db.get_settings()
            minutes = int(st.get("imap_poll_minutes") or 10)
            if st.get("imap_host") and minutes > 0 and time.time() - last_imap > minutes * 60:
                result = mailer.poll_inbox()
                last_imap = time.time()
                _state["last_imap"] = db.now_iso()
                if not result.get("ok"):
                    _state["last_error"] = result.get("error", "")
        except Exception as exc:  # noqa: BLE001 - keep the worker alive
            _state["last_error"] = "%s: %s" % (type(exc).__name__, exc)
        _stop.wait(20)


def start_background():
    thread = threading.Thread(target=_loop, name="outreach-engine", daemon=True)
    thread.start()
    return thread


def status():
    return dict(_state)
