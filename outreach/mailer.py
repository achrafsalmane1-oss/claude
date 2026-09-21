"""Email transport (SMTP out, IMAP in) and template rendering. Standard library only."""
import email
import hashlib
import imaplib
import json
import re
import smtplib
import ssl
import uuid
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import db

TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*(?:\|\s*([^}]*?))?\s*\}\}")


def contact_context(contact):
    ctx = {k: (contact.get(k) or "") for k in (
        "first_name", "last_name", "email", "phone", "linkedin_url",
        "company", "title", "website",
    )}
    ctx["full_name"] = (" ".join(x for x in [ctx["first_name"], ctx["last_name"]] if x)).strip()
    try:
        custom = json.loads(contact.get("custom") or "{}")
    except (ValueError, TypeError):
        custom = {}
    for k, v in custom.items():
        ctx.setdefault(k, "" if v is None else str(v))
        ctx["custom." + k] = "" if v is None else str(v)
    st = db.get_settings()
    ctx["signature"] = st.get("signature", "")
    ctx.setdefault("sender_name", st.get("from_name", ""))
    if contact.get("id"):
        token = hashlib.sha256(
            ("%s:%s" % (contact["id"], st.get("secret", "outreach"))).encode()
        ).hexdigest()[:16]
        ctx["unsubscribe_url"] = "%s/u/%s?c=%s" % (
            st.get("base_url", "http://127.0.0.1:8000").rstrip("/"), token, contact["id"])
    return ctx


def render(template, contact):
    """Replace {{field}} / {{field|fallback}} merge tags."""
    if not template:
        return ""
    ctx = contact_context(contact)

    def sub(m):
        key, fallback = m.group(1), m.group(2)
        val = ctx.get(key, "")
        if not str(val).strip():
            return (fallback or "").strip()
        return str(val)

    return TOKEN_RE.sub(sub, template)


def missing_tokens(template, contact):
    """Merge tags that would render empty with no fallback."""
    ctx = contact_context(contact)
    out = []
    for m in TOKEN_RE.finditer(template or ""):
        key, fallback = m.group(1), m.group(2)
        if not str(ctx.get(key, "")).strip() and not (fallback or "").strip():
            out.append(key)
    return sorted(set(out))


def text_to_html(text):
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    esc = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', esc)
    return "<div style=\"font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.55;color:#111\">" \
        + esc.replace("\n", "<br>") + "</div>"


def is_suppressed(emaddr):
    if not emaddr:
        return False
    e = emaddr.strip().lower()
    domain = e.split("@")[-1] if "@" in e else ""
    row = db.query_one(
        "SELECT id FROM suppressions WHERE (kind='email' AND value=?) OR (kind='domain' AND value=?)",
        (e, domain),
    )
    return bool(row)


def send_email(contact, subject, body, campaign_id=None, task_id=None):
    """Send one email. Returns (ok, message_row_id, error)."""
    st = db.get_settings()
    to_addr = (contact.get("email") or "").strip()
    if not to_addr:
        return False, None, "contact has no email address"
    if is_suppressed(to_addr):
        return False, None, "address is suppressed"

    msg_uid = uuid.uuid4().hex
    dry = st.get("dry_run", "1") == "1" or not st.get("smtp_host")

    html = text_to_html(body)
    if st.get("track_opens", "1") == "1" and not dry:
        base = st.get("base_url", "http://127.0.0.1:8000").rstrip("/")
        html += '<img src="%s/px/%s.gif" width="1" height="1" alt="" style="display:none">' % (base, msg_uid)

    error = ""
    ok = True
    if dry:
        status = "dry_run"
    else:
        try:
            m = EmailMessage()
            from_email = st.get("from_email") or st.get("smtp_user")
            m["From"] = formataddr((st.get("from_name") or "", from_email))
            m["To"] = to_addr
            m["Subject"] = subject or "(no subject)"
            m["Message-ID"] = "<%s@outreach.local>" % msg_uid
            if st.get("reply_to"):
                m["Reply-To"] = st["reply_to"]
            m.set_content(body)
            m.add_alternative(html, subtype="html")

            port = int(st.get("smtp_port") or 587)
            if st.get("smtp_security") == "ssl":
                server = smtplib.SMTP_SSL(st["smtp_host"], port, timeout=30,
                                          context=ssl.create_default_context())
            else:
                server = smtplib.SMTP(st["smtp_host"], port, timeout=30)
                if st.get("smtp_security", "starttls") == "starttls":
                    server.starttls(context=ssl.create_default_context())
            with server:
                if st.get("smtp_user"):
                    server.login(st["smtp_user"], st.get("smtp_pass", ""))
                server.send_message(m)
            status = "sent"
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            ok = False
            status = "failed"
            error = "%s: %s" % (type(exc).__name__, exc)

    mid = db.insert("messages", {
        "contact_id": contact["id"],
        "campaign_id": campaign_id,
        "task_id": task_id,
        "channel": "email",
        "direction": "out",
        "subject": subject,
        "body": body,
        "status": status,
        "error": error,
        "message_id": msg_uid,
        "created_at": db.now_iso(),
    })
    db.touch_thread(contact["id"], "out", "email", subject or body)
    db.execute("UPDATE contacts SET status = 'active' WHERE id = ? AND status = 'new'", (contact["id"],))
    db.log_event(contact["id"], campaign_id, None, "email",
                 "sent" if ok else "failed", {"status": status, "error": error})
    return ok, mid, error


def _decode(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return str(value)


def _body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                part.get("Content-Disposition", "")
            ):
                try:
                    return part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", "replace"
                    )
                except Exception:  # noqa: BLE001
                    continue
        return ""
    try:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")
    except Exception:  # noqa: BLE001
        return str(msg.get_payload())


BOUNCE_HINTS = ("mailer-daemon", "postmaster", "delivery status notification",
                "undeliverable", "delivery has failed", "address not found")


def poll_inbox(limit=50):
    """Pull unseen mail over IMAP and file replies against contacts."""
    st = db.get_settings()
    if not st.get("imap_host") or not st.get("imap_user"):
        return {"ok": False, "error": "IMAP not configured", "imported": 0}
    imported = 0
    try:
        box = imaplib.IMAP4_SSL(st["imap_host"], int(st.get("imap_port") or 993),
                                ssl_context=ssl.create_default_context())
        box.login(st["imap_user"], st.get("imap_pass", ""))
        box.select(st.get("imap_folder") or "INBOX")
        typ, data = box.search(None, "UNSEEN")
        ids = data[0].split() if data and data[0] else []
        for num in ids[-limit:]:
            typ, raw = box.fetch(num, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            from_name, from_addr = parseaddr(_decode(msg.get("From")))
            subject = _decode(msg.get("Subject"))
            body = _body_text(msg).strip()
            addr = (from_addr or "").lower()
            contact = db.query_one("SELECT * FROM contacts WHERE lower(email) = ?", (addr,))
            if not contact:
                continue
            is_bounce = any(h in (addr + " " + subject).lower() for h in BOUNCE_HINTS)
            db.insert("messages", {
                "contact_id": contact["id"],
                "campaign_id": None,
                "task_id": None,
                "channel": "email",
                "direction": "in",
                "subject": subject,
                "body": body[:20000],
                "status": "received",
                "message_id": _decode(msg.get("Message-ID")),
                "created_at": db.now_iso(),
            })
            db.touch_thread(contact["id"], "in", "email", subject or body, unread=True)
            import engine  # local import avoids a cycle at module load
            if is_bounce:
                engine.register_bounce(contact["id"])
            else:
                engine.register_reply(contact["id"], "email")
            imported += 1
        box.close()
        box.logout()
        return {"ok": True, "imported": imported}
    except Exception as exc:  # noqa: BLE001 - reported in the UI
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc), "imported": imported}
