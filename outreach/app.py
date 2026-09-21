#!/usr/bin/env python3
"""Local outreach MVP: CSV import -> waterfall sequences -> master inbox -> reporting.

Standard library only. No third-party services. Run:  python3 app.py
"""
import argparse
import csv
import io
import json
import os
import re
import sqlite3
import sys
import threading
import uuid
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db  # noqa: E402
import engine  # noqa: E402
import mailer  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PIXEL = bytes.fromhex(
    "47494638396101000100800000ffffff00000021f90401000000002c00000000"
    "010001000002024401003b"
)
CONTACT_FIELDS = ("first_name", "last_name", "email", "phone", "linkedin_url",
                  "company", "title", "website")

HEADER_HINTS = {
    "first_name": ["first name", "firstname", "first", "given name", "fname", "prenom"],
    "last_name": ["last name", "lastname", "last", "surname", "family name", "lname"],
    "email": ["email", "email address", "work email", "e-mail", "personal email", "email_1"],
    "phone": ["phone", "phone number", "mobile", "cell", "direct dial", "telephone", "mobile phone"],
    "linkedin_url": ["linkedin", "linkedin url", "linkedin profile", "li url", "profile url", "linkedin_profile"],
    "company": ["company", "company name", "organization", "account", "employer", "org"],
    "title": ["title", "job title", "position", "role", "headline"],
    "website": ["website", "domain", "company domain", "company website", "url"],
}


# ------------------------------------------------------------------ helpers


def guess_mapping(headers):
    mapping = {}
    used = set()
    for header in headers:
        key = re.sub(r"[^a-z0-9 ]+", " ", (header or "").strip().lower()).strip()
        for field, hints in HEADER_HINTS.items():
            if field in used:
                continue
            if key in hints or key.replace(" ", "_") == field:
                mapping[header] = field
                used.add(field)
                break
        else:
            mapping[header] = "custom"
    return mapping


def clean_linkedin(value):
    v = (value or "").strip()
    if not v:
        return ""
    if v.startswith("linkedin.com") or v.startswith("www.linkedin.com"):
        v = "https://" + v
    return v


def clean_phone(value):
    v = re.sub(r"[^\d+]", "", (value or "").strip())
    return v


def contact_payload(row, mapping):
    data = {f: "" for f in CONTACT_FIELDS}
    custom = {}
    for header, value in row.items():
        target = mapping.get(header, "custom")
        value = (value or "").strip()
        if target == "ignore" or not header:
            continue
        if target in CONTACT_FIELDS:
            data[target] = value
        elif value:
            custom[re.sub(r"[^a-zA-Z0-9_]+", "_", header.strip().lower()).strip("_")] = value
    data["email"] = data["email"].strip().lower()
    data["phone"] = clean_phone(data["phone"])
    data["linkedin_url"] = clean_linkedin(data["linkedin_url"])
    data["custom"] = json.dumps(custom)
    return data


def import_rows(text, mapping, list_name="", dedupe=True, source="csv"):
    reader = csv.DictReader(io.StringIO(text))
    list_id = None
    if list_name:
        existing = db.query_one("SELECT id FROM lists WHERE name = ?", (list_name,))
        list_id = existing["id"] if existing else db.insert(
            "lists", {"name": list_name, "created_at": db.now_iso()}
        )
    created = updated = skipped = 0
    for row in reader:
        data = contact_payload(row, mapping)
        if not any([data["email"], data["phone"], data["linkedin_url"]]):
            skipped += 1
            continue
        existing = None
        if dedupe:
            if data["email"]:
                existing = db.query_one("SELECT * FROM contacts WHERE email = ? AND email != ''",
                                        (data["email"],))
            if not existing and data["linkedin_url"]:
                existing = db.query_one(
                    "SELECT * FROM contacts WHERE linkedin_url = ? AND linkedin_url != ''",
                    (data["linkedin_url"],))
        if existing:
            patch = {k: v for k, v in data.items()
                     if k != "custom" and v and not (existing.get(k) or "").strip()}
            try:
                old_custom = json.loads(existing.get("custom") or "{}")
            except ValueError:
                old_custom = {}
            new_custom = json.loads(data["custom"])
            old_custom.update({k: v for k, v in new_custom.items() if v})
            patch["custom"] = json.dumps(old_custom)
            patch["updated_at"] = db.now_iso()
            db.update("contacts", existing["id"], patch)
            contact_id = existing["id"]
            updated += 1
        else:
            data.update({"status": "new", "source": source,
                         "created_at": db.now_iso(), "updated_at": db.now_iso()})
            contact_id = db.insert("contacts", data)
            created += 1
        if list_id:
            db.execute("INSERT OR IGNORE INTO list_members(list_id, contact_id) VALUES (?, ?)",
                       (list_id, contact_id))
    return {"created": created, "updated": updated, "skipped": skipped, "list_id": list_id}


def contact_filter_sql(params):
    where, args = [], []
    search = (params.get("search") or [""])[0].strip()
    status = (params.get("status") or [""])[0].strip()
    list_id = (params.get("list_id") or [""])[0].strip()
    has = (params.get("has") or [""])[0].strip()
    if search:
        like = "%" + search.lower() + "%"
        where.append("(lower(first_name||' '||last_name) LIKE ? OR lower(email) LIKE ? "
                     "OR lower(company) LIKE ? OR phone LIKE ? OR lower(title) LIKE ?)")
        args += [like, like, like, "%" + search + "%", like]
    if status:
        where.append("status = ?")
        args.append(status)
    if has in ("email", "phone", "linkedin_url"):
        where.append("%s != ''" % has)
    if list_id:
        where.append("id IN (SELECT contact_id FROM list_members WHERE list_id = ?)")
        args.append(int(list_id))
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return clause, args


def unsub_token(contact_id):
    import hashlib
    secret = db.get_settings().get("secret", "outreach")
    return hashlib.sha256(("%s:%s" % (contact_id, secret)).encode()).hexdigest()[:16]


# --------------------------------------------------------------- API routing


class Api:
    """Each method returns a JSON-serialisable object."""

    # ---- bootstrap / settings
    def get_bootstrap(self, q):
        counts = {
            "contacts": db.query_one("SELECT COUNT(*) n FROM contacts")["n"],
            "tasks_pending": db.query_one("SELECT COUNT(*) n FROM tasks WHERE status='pending'")["n"],
            "unread": db.query_one("SELECT COUNT(*) n FROM threads WHERE unread=1")["n"],
            "campaigns_running": db.query_one(
                "SELECT COUNT(*) n FROM campaigns WHERE status='running'")["n"],
        }
        settings = db.get_settings()
        settings.pop("smtp_pass", None)
        settings.pop("imap_pass", None)
        settings.pop("secret", None)
        return {"counts": counts, "settings": settings, "engine": engine.status(),
                "lists": db.query("SELECT l.*, (SELECT COUNT(*) FROM list_members m "
                                  "WHERE m.list_id=l.id) AS size FROM lists l ORDER BY l.id DESC")}

    def get_settings(self, q):
        s = db.get_settings()
        s["smtp_pass"] = "********" if s.get("smtp_pass") else ""
        s["imap_pass"] = "********" if s.get("imap_pass") else ""
        s.pop("secret", None)
        return s

    def post_settings(self, q, body):
        payload = {k: v for k, v in body.items() if k not in ("secret",)}
        for secret_field in ("smtp_pass", "imap_pass"):
            if payload.get(secret_field) == "********":
                payload.pop(secret_field)
        db.set_settings(payload)
        return self.get_settings(q)

    def post_settings_test(self, q, body):
        st = db.get_settings()
        if not st.get("smtp_host"):
            return {"ok": False, "error": "No SMTP host configured (dry-run mode is active)."}
        to = body.get("to") or st.get("from_email") or st.get("smtp_user")
        fake = {"id": 0, "email": to, "first_name": "there", "last_name": "", "custom": "{}"}
        was_dry = st.get("dry_run")
        db.set_settings({"dry_run": "0"})
        try:
            ok, _mid, err = mailer.send_email(
                fake, "Outreach MVP test email",
                "This is a test send from your local outreach tool. If you got this, SMTP works.")
        finally:
            db.set_settings({"dry_run": was_dry})
        if fake["id"] == 0:
            db.execute("DELETE FROM messages WHERE contact_id = 0")
            db.execute("DELETE FROM threads WHERE contact_id = 0")
            db.execute("DELETE FROM events WHERE contact_id = 0")
        return {"ok": ok, "error": err}

    # ---- contacts
    def get_contacts(self, q):
        clause, args = contact_filter_sql(q)
        limit = min(int((q.get("limit") or ["100"])[0]), 500)
        offset = int((q.get("offset") or ["0"])[0])
        total = db.query_one("SELECT COUNT(*) n FROM contacts" + clause, tuple(args))["n"]
        rows = db.query(
            "SELECT * FROM contacts" + clause + " ORDER BY id DESC LIMIT ? OFFSET ?",
            tuple(args) + (limit, offset))
        return {"total": total, "rows": rows,
                "statuses": db.query("SELECT status, COUNT(*) n FROM contacts GROUP BY status")}

    def get_contact_ids(self, q):
        clause, args = contact_filter_sql(q)
        return {"ids": [r["id"] for r in db.query("SELECT id FROM contacts" + clause, tuple(args))]}

    def get_contact(self, q, contact_id):
        contact = db.query_one("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        if not contact:
            return {"error": "not found"}
        contact["messages"] = db.query(
            "SELECT * FROM messages WHERE contact_id = ? ORDER BY created_at ASC, id ASC", (contact_id,))
        contact["tasks"] = db.query(
            "SELECT t.*, c.name AS campaign_name FROM tasks t LEFT JOIN campaigns c ON c.id=t.campaign_id "
            "WHERE t.contact_id = ? ORDER BY t.id DESC LIMIT 50", (contact_id,))
        contact["enrollments"] = db.query(
            "SELECT e.*, c.name AS campaign_name FROM enrollments e JOIN campaigns c ON c.id=e.campaign_id "
            "WHERE e.contact_id = ?", (contact_id,))
        contact["events"] = db.query(
            "SELECT * FROM events WHERE contact_id = ? ORDER BY id DESC LIMIT 50", (contact_id,))
        return contact

    def post_contact(self, q, body, contact_id=None):
        data = {k: (body.get(k) or "").strip() for k in CONTACT_FIELDS}
        data["email"] = data["email"].lower()
        data["phone"] = clean_phone(data["phone"])
        data["linkedin_url"] = clean_linkedin(data["linkedin_url"])
        if body.get("custom") is not None:
            data["custom"] = json.dumps(body.get("custom") or {})
        if body.get("status"):
            data["status"] = body["status"]
        data["updated_at"] = db.now_iso()
        if contact_id:
            db.update("contacts", contact_id, data)
            return self.get_contact(q, contact_id)
        data["created_at"] = db.now_iso()
        data.setdefault("status", "new")
        data["source"] = "manual"
        new_id = db.insert("contacts", data)
        return self.get_contact(q, new_id)

    def post_contacts_bulk(self, q, body):
        action = body.get("action")
        ids = [int(i) for i in body.get("ids", [])]
        if not ids:
            return {"ok": False, "error": "no contacts selected"}
        marks = ",".join("?" for _ in ids)
        if action == "delete":
            for table in ("list_members",):
                db.execute("DELETE FROM %s WHERE contact_id IN (%s)" % (table, marks), tuple(ids))
            db.execute("DELETE FROM contacts WHERE id IN (%s)" % marks, tuple(ids))
            db.execute("DELETE FROM enrollments WHERE contact_id IN (%s)" % marks, tuple(ids))
            db.execute("DELETE FROM tasks WHERE contact_id IN (%s)" % marks, tuple(ids))
        elif action == "status":
            db.execute("UPDATE contacts SET status = ? WHERE id IN (%s)" % marks,
                       tuple([body.get("status", "new")] + ids))
        elif action == "unsubscribe":
            for cid in ids:
                engine.unsubscribe(cid, "manual")
        elif action == "add_to_list":
            name = (body.get("list_name") or "").strip()
            if not name:
                return {"ok": False, "error": "list name required"}
            row = db.query_one("SELECT id FROM lists WHERE name = ?", (name,))
            list_id = row["id"] if row else db.insert("lists", {"name": name, "created_at": db.now_iso()})
            for cid in ids:
                db.execute("INSERT OR IGNORE INTO list_members(list_id, contact_id) VALUES (?, ?)",
                           (list_id, cid))
        elif action == "enroll":
            return engine.enroll(int(body.get("campaign_id")), ids)
        return {"ok": True, "count": len(ids)}

    # ---- import
    def post_import_preview(self, q, body):
        text = body.get("csv", "")
        try:
            sample = csv.DictReader(io.StringIO(text))
            headers = sample.fieldnames or []
            rows = []
            for i, row in enumerate(sample):
                if i >= 5:
                    break
                rows.append(row)
        except csv.Error as exc:
            return {"ok": False, "error": str(exc)}
        total = max(text.count("\n") - 1, 0)
        return {"ok": True, "headers": headers, "rows": rows,
                "mapping": guess_mapping(headers), "approx_rows": total,
                "fields": list(CONTACT_FIELDS) + ["custom", "ignore"]}

    def post_import_commit(self, q, body):
        result = import_rows(body.get("csv", ""), body.get("mapping", {}),
                             body.get("list_name", ""), body.get("dedupe", True))
        if body.get("campaign_id") and result["list_id"]:
            ids = [r["contact_id"] for r in db.query(
                "SELECT contact_id FROM list_members WHERE list_id = ?", (result["list_id"],))]
            result["enrolled"] = engine.enroll(int(body["campaign_id"]), ids)
        return result

    # ---- lists
    def get_lists(self, q):
        return db.query("SELECT l.*, (SELECT COUNT(*) FROM list_members m WHERE m.list_id=l.id) "
                        "AS size FROM lists l ORDER BY l.id DESC")

    def delete_list(self, q, list_id):
        db.execute("DELETE FROM list_members WHERE list_id = ?", (list_id,))
        db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        return {"ok": True}

    # ---- sequences
    def get_sequences(self, q):
        rows = db.query("SELECT * FROM sequences ORDER BY id DESC")
        for r in rows:
            r["steps"] = db.query("SELECT * FROM steps WHERE sequence_id = ? ORDER BY position", (r["id"],))
            r["campaigns"] = db.query_one(
                "SELECT COUNT(*) n FROM campaigns WHERE sequence_id = ?", (r["id"],))["n"]
        return rows

    def post_sequence(self, q, body, sequence_id=None):
        name = (body.get("name") or "Untitled sequence").strip()
        if sequence_id:
            db.update("sequences", sequence_id, {
                "name": name, "description": body.get("description", ""), "updated_at": db.now_iso()})
        else:
            sequence_id = db.insert("sequences", {
                "name": name, "description": body.get("description", ""),
                "created_at": db.now_iso(), "updated_at": db.now_iso()})
        if body.get("steps") is not None:
            db.execute("DELETE FROM steps WHERE sequence_id = ?", (sequence_id,))
            for position, step in enumerate(body["steps"]):
                db.insert("steps", {
                    "sequence_id": sequence_id,
                    "position": position,
                    "channel": step.get("channel", "email"),
                    "action": step.get("action", "message"),
                    "delay_days": int(step.get("delay_days") or 0),
                    "delay_hours": int(step.get("delay_hours") or 0),
                    "subject": step.get("subject", ""),
                    "body": step.get("body", ""),
                    "requires_field": step.get("requires_field", ""),
                    "on_missing": step.get("on_missing", "skip"),
                    "auto_send": 1 if step.get("auto_send", True) else 0,
                    "created_at": db.now_iso(),
                })
        return {"ok": True, "id": sequence_id}

    def delete_sequence(self, q, sequence_id):
        if db.query_one("SELECT id FROM campaigns WHERE sequence_id = ?", (sequence_id,)):
            return {"ok": False, "error": "sequence is used by a campaign"}
        db.execute("DELETE FROM steps WHERE sequence_id = ?", (sequence_id,))
        db.execute("DELETE FROM sequences WHERE id = ?", (sequence_id,))
        return {"ok": True}

    # ---- campaigns
    def get_campaigns(self, q):
        rows = db.query(
            "SELECT c.*, s.name AS sequence_name FROM campaigns c "
            "JOIN sequences s ON s.id = c.sequence_id ORDER BY c.id DESC")
        for r in rows:
            stats = db.query_one(
                "SELECT COUNT(*) total, SUM(status='active') active, SUM(status='waiting') waiting, "
                "SUM(status='finished') finished, SUM(status='replied') replied "
                "FROM enrollments WHERE campaign_id = ?", (r["id"],))
            r["stats"] = {k: (v or 0) for k, v in (stats or {}).items()}
            r["sent_today"] = engine.sent_today(r["id"])
        return rows

    def post_campaign(self, q, body, campaign_id=None):
        data = {
            "name": (body.get("name") or "Untitled campaign").strip(),
            "sequence_id": int(body.get("sequence_id") or 0),
            "daily_limit": int(body.get("daily_limit") or 50),
            "window_start": int(body.get("window_start") or 8),
            "window_end": int(body.get("window_end") or 18),
            "weekdays_only": 1 if body.get("weekdays_only", True) else 0,
            "stop_on_reply": 1 if body.get("stop_on_reply", True) else 0,
            "updated_at": db.now_iso(),
        }
        if body.get("status"):
            data["status"] = body["status"]
        if campaign_id:
            db.update("campaigns", campaign_id, data)
        else:
            data["created_at"] = db.now_iso()
            data.setdefault("status", "draft")
            campaign_id = db.insert("campaigns", data)
        return {"ok": True, "id": campaign_id}

    def post_campaign_status(self, q, body, campaign_id):
        status = body.get("status", "draft")
        db.update("campaigns", campaign_id, {"status": status, "updated_at": db.now_iso()})
        if status == "running":
            engine.tick()
        return {"ok": True}

    def post_campaign_enroll(self, q, body, campaign_id):
        ids = [int(i) for i in body.get("contact_ids", [])]
        if body.get("list_id"):
            ids += [r["contact_id"] for r in db.query(
                "SELECT contact_id FROM list_members WHERE list_id = ?", (int(body["list_id"]),))]
        if body.get("all_matching"):
            clause, args = contact_filter_sql({k: [v] for k, v in body.get("filter", {}).items()})
            ids += [r["id"] for r in db.query("SELECT id FROM contacts" + clause, tuple(args))]
        return engine.enroll(campaign_id, sorted(set(ids)))

    def delete_campaign(self, q, campaign_id):
        db.execute("DELETE FROM enrollments WHERE campaign_id = ?", (campaign_id,))
        db.execute("DELETE FROM tasks WHERE campaign_id = ? AND status='pending'", (campaign_id,))
        db.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        return {"ok": True}

    # ---- tasks
    def get_tasks(self, q):
        channel = (q.get("channel") or [""])[0]
        status = (q.get("status") or ["pending"])[0]
        where, args = ["t.status = ?"], [status]
        if channel:
            where.append("t.channel = ?")
            args.append(channel)
        rows = db.query(
            "SELECT t.*, c.first_name, c.last_name, c.email, c.phone, c.linkedin_url, c.company, "
            "c.title, c.status AS contact_status, cm.name AS campaign_name "
            "FROM tasks t JOIN contacts c ON c.id = t.contact_id "
            "LEFT JOIN campaigns cm ON cm.id = t.campaign_id "
            "WHERE " + " AND ".join(where) + " ORDER BY t.due_at ASC, t.id ASC LIMIT 300",
            tuple(args))
        counts = db.query("SELECT channel, COUNT(*) n FROM tasks WHERE status='pending' GROUP BY channel")
        return {"rows": rows, "counts": {c["channel"]: c["n"] for c in counts}}

    def post_task_complete(self, q, body, task_id):
        return engine.complete_task(task_id, body.get("outcome", ""), body.get("notes", ""),
                                    body.get("body"))

    def post_task_skip(self, q, body, task_id):
        return engine.skip_task(task_id, body.get("reason", ""))

    def post_task_snooze(self, q, body, task_id):
        hours = int(body.get("hours") or 24)
        due = (engine.utcnow() + timedelta(hours=hours)).isoformat()
        db.update("tasks", task_id, {"due_at": due})
        return {"ok": True, "due_at": due}

    # ---- inbox
    def get_inbox(self, q):
        state = (q.get("filter") or ["all"])[0]
        where, args = [], []
        if state == "unread":
            where.append("t.unread = 1")
        elif state == "replied":
            where.append("t.last_direction = 'in'")
        elif state in ("open", "closed", "won", "lost"):
            where.append("t.state = ?")
            args.append(state)
        elif state in ("email", "linkedin", "call"):
            where.append("t.last_channel = ?")
            args.append(state)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        rows = db.query(
            "SELECT t.*, c.first_name, c.last_name, c.email, c.company, c.title, c.phone, "
            "c.linkedin_url, c.status AS contact_status FROM threads t "
            "JOIN contacts c ON c.id = t.contact_id" + clause +
            " ORDER BY t.last_message_at DESC LIMIT 200", tuple(args))
        return {"rows": rows}

    def get_thread(self, q, contact_id):
        contact = self.get_contact(q, contact_id)
        db.execute("UPDATE threads SET unread = 0 WHERE contact_id = ?", (contact_id,))
        return contact

    def post_thread_reply(self, q, body, contact_id):
        contact = db.query_one("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        channel = body.get("channel", "email")
        text = body.get("body", "")
        if channel == "email":
            ok, _mid, err = mailer.send_email(contact, body.get("subject", ""), text)
            return {"ok": ok, "error": err}
        db.insert("messages", {
            "contact_id": contact_id, "channel": channel, "direction": "out",
            "subject": body.get("subject", ""), "body": text, "status": "sent",
            "created_at": db.now_iso()})
        db.touch_thread(contact_id, "out", channel, text)
        db.log_event(contact_id, None, None, channel, "linkedin" if channel == "linkedin" else "call", {})
        return {"ok": True}

    def post_thread_log(self, q, body, contact_id):
        """Log an inbound reply that arrived outside email (LinkedIn DM, a call back)."""
        channel = body.get("channel", "linkedin")
        text = body.get("body", "")
        db.insert("messages", {
            "contact_id": contact_id, "channel": channel, "direction": "in",
            "subject": body.get("subject", ""), "body": text, "status": "received",
            "created_at": db.now_iso()})
        db.touch_thread(contact_id, "in", channel, text, unread=False)
        if body.get("mark_replied", True):
            engine.register_reply(contact_id, channel, text[:200])
        return {"ok": True}

    def post_thread_state(self, q, body, contact_id):
        if body.get("state"):
            db.execute("UPDATE threads SET state = ? WHERE contact_id = ?", (body["state"], contact_id))
        if body.get("contact_status"):
            status = body["contact_status"]
            if status == "unsubscribed":
                engine.unsubscribe(contact_id, "manual")
            else:
                db.update("contacts", contact_id, {"status": status, "updated_at": db.now_iso()})
        if body.get("unread") is not None:
            db.execute("UPDATE threads SET unread = ? WHERE contact_id = ?",
                       (1 if body["unread"] else 0, contact_id))
        return {"ok": True}

    def post_inbox_sync(self, q, body):
        return mailer.poll_inbox()

    # ---- reports
    def get_reports(self, q):
        campaign_id = (q.get("campaign_id") or [""])[0]
        days = int((q.get("days") or ["30"])[0])
        since = (engine.utcnow() - timedelta(days=days)).isoformat()
        cfilter, cargs = ("", [])
        if campaign_id:
            cfilter = " AND campaign_id = ?"
            cargs = [int(campaign_id)]

        def count_events(etype, channel=None):
            sql = "SELECT COUNT(*) n FROM events WHERE type = ? AND created_at >= ?" + cfilter
            args = [etype, since] + cargs
            if channel:
                sql += " AND channel = ?"
                args.append(channel)
            return db.query_one(sql, tuple(args))["n"]

        msg_filter = " AND campaign_id = ?" if campaign_id else ""
        emails_sent = db.query_one(
            "SELECT COUNT(*) n FROM messages WHERE direction='out' AND channel='email' "
            "AND created_at >= ?" + msg_filter, tuple([since] + cargs))["n"]
        opens = db.query_one(
            "SELECT COUNT(*) n FROM messages WHERE direction='out' AND channel='email' "
            "AND open_count > 0 AND created_at >= ?" + msg_filter, tuple([since] + cargs))["n"]
        replies = db.query_one(
            "SELECT COUNT(DISTINCT contact_id) n FROM messages WHERE direction='in' AND created_at >= ?",
            (since,))["n"]
        li_sent = db.query_one(
            "SELECT COUNT(*) n FROM messages WHERE direction='out' AND channel='linkedin' "
            "AND created_at >= ?" + msg_filter, tuple([since] + cargs))["n"]
        calls = db.query_one(
            "SELECT COUNT(*) n FROM tasks WHERE channel='call' AND status='done' AND completed_at >= ?"
            + (" AND campaign_id = ?" if campaign_id else ""), tuple([since] + cargs))["n"]

        dispositions = db.query(
            "SELECT outcome, COUNT(*) n FROM tasks WHERE channel='call' AND status='done' "
            "AND completed_at >= ?" + (" AND campaign_id = ?" if campaign_id else "") +
            " GROUP BY outcome ORDER BY n DESC", tuple([since] + cargs))

        by_step = db.query(
            "SELECT t.step_index, t.channel, COUNT(*) n, SUM(t.status='done') done, "
            "SUM(t.status='skipped') skipped, SUM(t.status='failed') failed "
            "FROM tasks t WHERE t.created_at >= ?" + (" AND t.campaign_id = ?" if campaign_id else "") +
            " GROUP BY t.step_index, t.channel ORDER BY t.step_index", tuple([since] + cargs))
        # waterfall fall-throughs never become tasks, so fold the skip events in
        skips = db.query(
            "SELECT step_index, channel, COUNT(*) n FROM events WHERE type='skipped' AND created_at >= ?"
            + cfilter + " GROUP BY step_index, channel", tuple([since] + cargs))
        index = {(r["step_index"], r["channel"]): r for r in by_step}
        for s in skips:
            key = (s["step_index"], s["channel"])
            if key in index:
                index[key]["skipped"] = (index[key]["skipped"] or 0) + s["n"]
                index[key]["n"] += s["n"]
            else:
                by_step.append({"step_index": s["step_index"], "channel": s["channel"],
                                "n": s["n"], "done": 0, "skipped": s["n"], "failed": 0})
        by_step = [b for b in by_step if b["step_index"] is not None]
        by_step.sort(key=lambda b: (b["step_index"], b["channel"]))

        series = db.query(
            "SELECT substr(created_at,1,10) d, "
            "SUM(type='sent') sent, SUM(type='open') opens, SUM(type='reply') replies, "
            "SUM(type='call') calls, SUM(type='linkedin') linkedin "
            "FROM events WHERE created_at >= ?" + cfilter +
            " GROUP BY d ORDER BY d", tuple([since] + cargs))

        per_campaign = db.query(
            "SELECT c.id, c.name, c.status, "
            "(SELECT COUNT(*) FROM enrollments e WHERE e.campaign_id=c.id) enrolled, "
            "(SELECT COUNT(*) FROM messages m WHERE m.campaign_id=c.id AND m.direction='out') touches, "
            "(SELECT COUNT(*) FROM enrollments e WHERE e.campaign_id=c.id AND e.status='replied') replied "
            "FROM campaigns c ORDER BY c.id DESC")

        return {
            "totals": {
                "emails_sent": emails_sent, "opens": opens, "replies": replies,
                "linkedin_sent": li_sent, "calls": calls,
                "bounces": count_events("bounce"), "unsubscribes": count_events("unsubscribe"),
                "skipped": count_events("skipped"),
                "contacts": db.query_one("SELECT COUNT(*) n FROM contacts")["n"],
                "reached": db.query_one(
                    "SELECT COUNT(DISTINCT contact_id) n FROM messages WHERE direction='out'")["n"],
            },
            "dispositions": dispositions, "by_step": by_step, "series": series,
            "per_campaign": per_campaign,
        }

    # ---- engine
    def post_engine_tick(self, q, body):
        return engine.tick()

    def get_engine_status(self, q):
        s = engine.status()
        s["due_now"] = db.query_one(
            "SELECT COUNT(*) n FROM enrollments WHERE status='active' AND next_action_at <= ?",
            (engine.utcnow().isoformat(),))["n"]
        return s

    def post_preview(self, q, body):
        contact = db.query_one("SELECT * FROM contacts WHERE id = ?", (int(body.get("contact_id") or 0),))
        if not contact:
            contact = db.query_one("SELECT * FROM contacts ORDER BY id DESC LIMIT 1") or {
                "first_name": "Alex", "last_name": "Doe", "company": "Acme",
                "title": "Head of Growth", "email": "alex@acme.com", "custom": "{}"}
        return {
            "subject": mailer.render(body.get("subject", ""), contact),
            "body": mailer.render(body.get("body", ""), contact),
            "missing": mailer.missing_tokens(
                (body.get("subject", "") + " " + body.get("body", "")), contact),
            "contact": {"id": contact.get("id"), "name": "%s %s" % (
                contact.get("first_name", ""), contact.get("last_name", ""))},
        }


API = Api()


class Handler(BaseHTTPRequestHandler):
    server_version = "OutreachMVP/1.0"

    def log_message(self, fmt, *args):  # quieter console
        if os.environ.get("OUTREACH_VERBOSE"):
            super().log_message(fmt, *args)

    # -- plumbing
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        payload = body if isinstance(body, (bytes, bytearray)) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _static(self, path):
        name = path.lstrip("/") or "index.html"
        if name.startswith("static/"):
            name = name[len("static/"):]
        safe = os.path.normpath(os.path.join(STATIC_DIR, name))
        if not safe.startswith(STATIC_DIR) or not os.path.isfile(safe):
            return self._send(404, {"error": "not found"})
        ctype = {
            ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
        }.get(os.path.splitext(safe)[1], "application/octet-stream")
        with open(safe, "rb") as fh:
            self._send(200, fh.read(), ctype)

    # -- routing
    def do_GET(self):
        parsed = urlparse(self.path)
        path, q = parsed.path, parse_qs(parsed.query)
        if path.startswith("/px/"):
            uid = path[4:].replace(".gif", "")
            row = db.query_one("SELECT * FROM messages WHERE message_id = ?", (uid,))
            if row:
                db.execute("UPDATE messages SET open_count = open_count + 1, "
                           "opened_at = COALESCE(opened_at, ?) WHERE id = ?", (db.now_iso(), row["id"]))
                if not row["opened_at"]:
                    db.log_event(row["contact_id"], row["campaign_id"], None, "email", "open", {})
            return self._send(200, PIXEL, "image/gif")
        if path.startswith("/u/"):
            token = path[3:]
            cid = (q.get("c") or ["0"])[0]
            if cid.isdigit() and unsub_token(int(cid)) == token:
                engine.unsubscribe(int(cid), "link")
                return self._send(200, b"<h2>You have been unsubscribed.</h2>", "text/html; charset=utf-8")
            return self._send(400, b"<h2>Invalid link.</h2>", "text/html; charset=utf-8")
        if not path.startswith("/api/"):
            return self._static(path)

        try:
            parts = [p for p in path[5:].split("/") if p]
            head = parts[0] if parts else ""
            if head == "bootstrap":
                return self._send(200, API.get_bootstrap(q))
            if head == "settings":
                return self._send(200, API.get_settings(q))
            if head == "contacts":
                if len(parts) > 1 and parts[1] == "ids":
                    return self._send(200, API.get_contact_ids(q))
                if len(parts) > 1:
                    return self._send(200, API.get_contact(q, int(parts[1])))
                return self._send(200, API.get_contacts(q))
            if head == "lists":
                return self._send(200, API.get_lists(q))
            if head == "sequences":
                return self._send(200, API.get_sequences(q))
            if head == "campaigns":
                return self._send(200, API.get_campaigns(q))
            if head == "tasks":
                return self._send(200, API.get_tasks(q))
            if head == "inbox":
                if len(parts) > 1:
                    return self._send(200, API.get_thread(q, int(parts[1])))
                return self._send(200, API.get_inbox(q))
            if head == "reports":
                return self._send(200, API.get_reports(q))
            if head == "engine":
                return self._send(200, API.get_engine_status(q))
            if head == "export":
                return self._export(q)
            return self._send(404, {"error": "unknown endpoint"})
        except Exception as exc:  # noqa: BLE001 - always answer the browser
            return self._send(500, {"error": "%s: %s" % (type(exc).__name__, exc)})

    def do_POST(self):
        parsed = urlparse(self.path)
        path, q = parsed.path, parse_qs(parsed.query)
        body = self._body()
        try:
            parts = [p for p in path[5:].split("/") if p]
            head = parts[0] if parts else ""
            tail = parts[1] if len(parts) > 1 else ""
            rest = parts[2] if len(parts) > 2 else ""

            if head == "settings":
                if tail == "test":
                    return self._send(200, API.post_settings_test(q, body))
                return self._send(200, API.post_settings(q, body))
            if head == "contacts":
                if tail == "bulk":
                    return self._send(200, API.post_contacts_bulk(q, body))
                if tail.isdigit():
                    return self._send(200, API.post_contact(q, body, int(tail)))
                return self._send(200, API.post_contact(q, body))
            if head == "import":
                if tail == "preview":
                    return self._send(200, API.post_import_preview(q, body))
                return self._send(200, API.post_import_commit(q, body))
            if head == "sequences":
                if tail.isdigit():
                    return self._send(200, API.post_sequence(q, body, int(tail)))
                return self._send(200, API.post_sequence(q, body))
            if head == "campaigns":
                if tail.isdigit() and rest == "enroll":
                    return self._send(200, API.post_campaign_enroll(q, body, int(tail)))
                if tail.isdigit() and rest == "status":
                    return self._send(200, API.post_campaign_status(q, body, int(tail)))
                if tail.isdigit():
                    return self._send(200, API.post_campaign(q, body, int(tail)))
                return self._send(200, API.post_campaign(q, body))
            if head == "tasks" and tail.isdigit():
                if rest == "complete":
                    return self._send(200, API.post_task_complete(q, body, int(tail)))
                if rest == "skip":
                    return self._send(200, API.post_task_skip(q, body, int(tail)))
                if rest == "snooze":
                    return self._send(200, API.post_task_snooze(q, body, int(tail)))
            if head == "inbox":
                if tail == "sync":
                    return self._send(200, API.post_inbox_sync(q, body))
                if tail.isdigit() and rest == "reply":
                    return self._send(200, API.post_thread_reply(q, body, int(tail)))
                if tail.isdigit() and rest == "log":
                    return self._send(200, API.post_thread_log(q, body, int(tail)))
                if tail.isdigit() and rest == "state":
                    return self._send(200, API.post_thread_state(q, body, int(tail)))
            if head == "engine":
                return self._send(200, API.post_engine_tick(q, body))
            if head == "preview":
                return self._send(200, API.post_preview(q, body))
            return self._send(404, {"error": "unknown endpoint"})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": "%s: %s" % (type(exc).__name__, exc)})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path[5:].split("/") if p]
        q = parse_qs(parsed.query)
        try:
            if len(parts) > 1 and parts[1].isdigit():
                target, ident = parts[0], int(parts[1])
                if target == "sequences":
                    return self._send(200, API.delete_sequence(q, ident))
                if target == "campaigns":
                    return self._send(200, API.delete_campaign(q, ident))
                if target == "lists":
                    return self._send(200, API.delete_list(q, ident))
            return self._send(404, {"error": "unknown endpoint"})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": "%s: %s" % (type(exc).__name__, exc)})

    def _export(self, q):
        what = (q.get("what") or ["contacts"])[0]
        buf = io.StringIO()
        if what == "contacts":
            clause, args = contact_filter_sql(q)
            rows = db.query("SELECT * FROM contacts" + clause + " ORDER BY id", tuple(args))
            fields = ["id"] + list(CONTACT_FIELDS) + ["status", "source", "created_at"]
            writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        elif what == "messages":
            rows = db.query(
                "SELECT m.id, m.created_at, m.channel, m.direction, m.status, m.subject, m.body, "
                "c.first_name, c.last_name, c.email, c.company FROM messages m "
                "JOIN contacts c ON c.id = m.contact_id ORDER BY m.id")
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["id"])
            writer.writeheader()
            writer.writerows(rows)
        else:
            rows = db.query(
                "SELECT t.id, t.created_at, t.completed_at, t.channel, t.status, t.outcome, t.notes, "
                "c.first_name, c.last_name, c.company, c.email, c.phone FROM tasks t "
                "JOIN contacts c ON c.id = t.contact_id ORDER BY t.id")
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["id"])
            writer.writeheader()
            writer.writerows(rows)
        data = buf.getvalue().encode()
        self._send(200, data, "text/csv; charset=utf-8",
                   {"Content-Disposition": 'attachment; filename="%s.csv"' % what})


def bootstrap_settings():
    db.init()
    if not db.get_settings().get("secret"):
        db.set_settings({"secret": uuid.uuid4().hex})


def main():
    parser = argparse.ArgumentParser(description="Local outreach MVP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="open a browser window")
    parser.add_argument("--no-engine", action="store_true", help="do not run the scheduler loop")
    args = parser.parse_args()

    bootstrap_settings()
    db.set_settings({"base_url": "http://%s:%s" % (args.host, args.port)})
    if not args.no_engine:
        engine.start_background()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = "http://%s:%s" % (args.host, args.port)
    print("Outreach MVP running at %s  (Ctrl+C to stop)" % url)
    print("Database: %s" % db.DB_PATH)
    if db.get_settings().get("dry_run") == "1":
        print("Mode: DRY RUN - emails are recorded, not delivered. Configure SMTP in Settings to send.")
    if args.open:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
