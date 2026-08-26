"""Fetching and merging one day of events across every connected account."""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import store

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# Meeting links that live in the location or description rather than in
# Google's own conferenceData (Zoom, Teams, Meet pasted by hand, ...).
MEETING_LINK_RE = re.compile(
    r"https?://(?:[\w-]+\.)*(?:zoom\.us|teams\.microsoft\.com|meet\.google\.com|"
    r"whereby\.com|meet\.jit\.si|around\.co|webex\.com|slack\.com)/[^\s<>\"]+",
    re.I,
)

# Requests are network-bound, so a small thread pool keeps a 6-account fetch
# roughly as fast as a 1-account fetch.
MAX_WORKERS = 12


class NeedsReconnect(Exception):
    pass


def credentials_for(acct, client_id, client_secret):
    if not acct.get("refresh_token"):
        raise NeedsReconnect(acct["email"])
    creds = Credentials(
        token=acct.get("token"),
        refresh_token=acct["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=acct.get("scopes") or SCOPES,
    )
    try:
        creds.refresh(Request())
    except RefreshError as exc:
        store.mark_needs_reconnect(acct["email"])
        raise NeedsReconnect(acct["email"]) from exc
    store.update_tokens(
        acct["email"],
        creds.token,
        creds.expiry.isoformat() if creds.expiry else None,
    )
    return creds


def _service(creds):
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _meeting_link(event):
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    for entry in (event.get("conferenceData") or {}).get("entryPoints", []):
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return entry["uri"]
    for field in ("location", "description"):
        match = MEETING_LINK_RE.search(event.get(field) or "")
        if match:
            return match.group(0).rstrip(".,)")
    return None


def _self_response(event):
    for attendee in event.get("attendees", []):
        if attendee.get("self"):
            return attendee.get("responseStatus", "needsAction")
    if (event.get("organizer") or {}).get("self"):
        return "accepted"
    return None


def _normalize(event, acct, calendar, tz):
    start_raw = event.get("start", {})
    end_raw = event.get("end", {})
    all_day = "date" in start_raw

    if all_day:
        start = datetime.combine(
            datetime.fromisoformat(start_raw["date"]).date(), time.min, tzinfo=tz
        )
        # Google's all-day end date is exclusive.
        end = datetime.combine(
            datetime.fromisoformat(end_raw["date"]).date(), time.min, tzinfo=tz
        )
    else:
        start = datetime.fromisoformat(start_raw["dateTime"]).astimezone(tz)
        end = datetime.fromisoformat(end_raw["dateTime"]).astimezone(tz)

    attendees = [a for a in event.get("attendees", []) if not a.get("resource")]
    response = _self_response(event)

    return {
        "uid": f"{acct['email']}::{calendar['id']}::{event['id']}",
        "title": event.get("summary") or "(no title)",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "start_ts": start.timestamp(),
        "end_ts": end.timestamp(),
        "duration_min": max(0, int((end - start).total_seconds() // 60)),
        "all_day": all_day,
        "account": acct["email"],
        "account_label": acct.get("label") or acct["email"],
        "color": acct.get("color"),
        "calendar": calendar.get("summary") or calendar["id"],
        "calendar_id": calendar["id"],
        "location": event.get("location"),
        "meeting_link": _meeting_link(event),
        "html_link": event.get("htmlLink"),
        "organizer": (event.get("organizer") or {}).get("email"),
        "organizer_self": bool((event.get("organizer") or {}).get("self")),
        "attendees": [
            {
                "email": a.get("email"),
                "name": a.get("displayName"),
                "status": a.get("responseStatus"),
                "self": bool(a.get("self")),
            }
            for a in attendees
        ],
        "attendee_count": len(attendees),
        "response": response,
        "declined": response == "declined",
        "tentative": response == "tentative",
        "needs_action": response == "needsAction",
        "recurring": bool(event.get("recurringEventId")),
        "status": event.get("status"),
        "description": (event.get("description") or "")[:400] or None,
    }


def _calendars(service, acct):
    muted = set(acct.get("muted_calendars") or [])
    result = service.calendarList().list(showHidden=False, maxResults=250).execute()
    calendars = []
    for cal in result.get("items", []):
        if cal.get("deleted") or cal.get("selected") is False:
            continue
        if cal.get("id") in muted:
            continue
        calendars.append(cal)
    return calendars


def _fetch_account(acct, day_start, day_end, tz, client_id, client_secret):
    """One account's events for the window. Failures are reported, not raised."""
    result = {
        "account": acct["email"],
        "label": acct.get("label") or acct["email"],
        "color": acct.get("color"),
        "events": [],
        "calendars": [],
        "error": None,
    }
    try:
        creds = credentials_for(acct, client_id, client_secret)
        service = _service(creds)
        calendars = _calendars(service, acct)
    except NeedsReconnect:
        result["error"] = "reconnect"
        return result
    except HttpError as exc:
        result["error"] = f"Google API error: {exc.status_code or ''} {exc.reason}".strip()
        return result

    result["calendars"] = [
        {"id": c["id"], "summary": c.get("summary"), "primary": bool(c.get("primary"))}
        for c in calendars
    ]

    time_min = day_start.isoformat()
    time_max = day_end.isoformat()

    def one_calendar(cal):
        events = []
        page_token = None
        while True:
            resp = (
                service.events()
                .list(
                    calendarId=cal["id"],
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                    pageToken=page_token,
                )
                .execute()
            )
            for event in resp.get("items", []):
                if event.get("status") == "cancelled":
                    continue
                events.append(_normalize(event, acct, cal, tz))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return events

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(calendars)))) as pool:
        for events in pool.map(one_calendar, calendars):
            result["events"].extend(events)

    return result


def _mark_conflicts(events):
    """Flag timed events that overlap another timed event (any account)."""
    timed = [e for e in events if not e["all_day"] and not e["declined"]]
    timed.sort(key=lambda e: (e["start_ts"], e["end_ts"]))
    for event in events:
        event["conflict"] = False
    for i, event in enumerate(timed):
        for other in timed[i + 1:]:
            if other["start_ts"] >= event["end_ts"]:
                break
            if other["start_ts"] < event["end_ts"] and event["start_ts"] < other["end_ts"]:
                event["conflict"] = True
                other["conflict"] = True
    return events


def _gaps(events, min_minutes=30):
    """Free blocks between the first and last meeting of the day."""
    timed = sorted(
        (e for e in events if not e["all_day"] and not e["declined"]),
        key=lambda e: e["start_ts"],
    )
    gaps = []
    cursor = None
    for event in timed:
        if cursor is not None and event["start_ts"] - cursor >= min_minutes * 60:
            gaps.append(
                {
                    "start_ts": cursor,
                    "end_ts": event["start_ts"],
                    "minutes": int((event["start_ts"] - cursor) // 60),
                }
            )
        cursor = max(cursor or 0, event["end_ts"])
    return gaps


def day_bounds(day, tz):
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def fetch_day(day, tz_name, client_id, client_secret, include_hidden=False):
    tz = ZoneInfo(tz_name)
    day_start, day_end = day_bounds(day, tz)

    accounts = [
        a for a in store.list_accounts() if include_hidden or not a.get("hidden")
    ]
    results = []
    if accounts:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(accounts))) as pool:
            results = list(
                pool.map(
                    lambda a: _fetch_account(
                        a, day_start, day_end, tz, client_id, client_secret
                    ),
                    accounts,
                )
            )

    events = [e for r in results for e in r["events"]]
    events.sort(key=lambda e: (not e["all_day"], e["start_ts"], e["title"].lower()))
    _mark_conflicts(events)

    live = [e for e in events if not e["declined"] and not e["all_day"]]
    booked = sum(e["duration_min"] for e in live)
    gaps = _gaps(events)

    return {
        "date": day.isoformat(),
        "timezone": tz_name,
        "generated_at": datetime.now(tz).isoformat(),
        "events": events,
        "accounts": [
            {k: v for k, v in r.items() if k != "events"} | {"count": len(r["events"])}
            for r in results
        ],
        "summary": {
            "meetings": len(live),
            "declined": sum(1 for e in events if e["declined"]),
            "all_day": sum(1 for e in events if e["all_day"]),
            "booked_minutes": booked,
            "conflicts": sum(1 for e in events if e.get("conflict")),
            "first_start": min((e["start"] for e in live), default=None),
            "last_end": max((e["end"] for e in live), default=None),
            "longest_gap": max((g["minutes"] for g in gaps), default=0),
            "gaps": gaps,
            "errors": [r["account"] for r in results if r["error"]],
        },
    }
