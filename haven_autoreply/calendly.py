# -*- coding: utf-8 -*-
"""Calendly : lire les vraies disponibilites, puis poser le rendez-vous.

Le prospect ne recoit jamais de lien. On lui propose des creneaux, et quand il
en accepte un c'est nous qui creons l'evenement (POST /invitees, "Scheduling
API"). Il recoit l'invitation Calendly habituelle, sans rien avoir a faire.

Necessite un plan Calendly payant et un jeton personnel :
calendly.com -> Integrations -> API & webhooks -> Personal access token.
"""
import json, os, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timedelta, timezone

BASE  = "https://api.calendly.com"
TOKEN = os.environ.get("CALENDLY_TOKEN", "")
# lien public du type d'evenement a utiliser (celui du message au prospect)
SLUG  = os.environ.get("CALENDLY_EVENT_SLUG", "haven-intro")


class CalendlyError(Exception):
    pass


def _call(method, path, body=None, params=None):
    url = BASE + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json"})
    last = ""
    for a in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read()[:400].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503):
                last = f"HTTP {e.code}: {detail}"
                time.sleep(min(2 ** a, 10)); continue
            raise CalendlyError(f"{method} {path} -> HTTP {e.code}: {detail}")
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            if a == 3:
                break
            time.sleep(2)
    raise CalendlyError(f"{method} {path} injoignable -- {last}")


def me():
    """Utilisateur courant : uri, fuseau, organisation."""
    return _call("GET", "/users/me")["resource"]


def event_type(user_uri):
    """Le type d'evenement dont le slug correspond a CALENDLY_EVENT_SLUG."""
    d = _call("GET", "/event_types", params={"user": user_uri, "count": 100})
    for et in d.get("collection", []):
        if et.get("slug") == SLUG:
            return et
    have = ", ".join(e.get("slug", "?") for e in d.get("collection", [])) or "aucun"
    raise CalendlyError(f"slug '{SLUG}' introuvable. Disponibles : {have}")


def available(et_uri, days=5, earliest_hours=14, max_per_day=None):
    """Creneaux reellement libres.

    `earliest_hours` ecarte les creneaux trop proches : proposer dans 2 heures
    fait perdre le rendez-vous. L'API refuse un intervalle de plus de 31 jours
    et n'accepte pas un debut dans le passe.
    """
    start = datetime.now(timezone.utc) + timedelta(hours=earliest_hours)
    end = start + timedelta(days=days)
    d = _call("GET", "/event_type_available_times", params={
        "event_type": et_uri,
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ")})
    out = []
    for s in d.get("collection", []):
        if s.get("status") and s["status"] != "available":
            continue
        try:
            out.append(datetime.fromisoformat(s["start_time"].replace("Z", "+00:00")))
        except Exception:
            continue
    out.sort()
    if max_per_day:
        seen = {}
        keep = []
        for t in out:
            k = t.date()
            seen[k] = seen.get(k, 0) + 1
            if seen[k] <= max_per_day:
                keep.append(t)
        out = keep
    return out


def spread(slots, n=3):
    """n creneaux repartis sur des jours differents plutot que colles.

    Trois heures le meme matin se lisent comme une seule proposition ; trois
    jours differents donnent une vraie chance d'en accepter un.
    """
    by_day = {}
    for t in slots:
        by_day.setdefault(t.date(), []).append(t)
    picked, days = [], sorted(by_day)
    # un creneau par jour, en tournant, jusqu'a en avoir n
    rank = 0
    while len(picked) < n and days:
        progressed = False
        for d in days:
            if len(picked) >= n:
                break
            if rank < len(by_day[d]):
                picked.append(by_day[d][rank]); progressed = True
        if not progressed:
            break
        rank += 1
    return sorted(picked)[:n]


def book(et_uri, when, name, email, tz, location_kind=None):
    """Cree le rendez-vous au nom du prospect. Renvoie la ressource creee."""
    body = {"event_type": et_uri,
            "start_time": when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "invitee": {"name": name or email.split("@")[0], "email": email,
                        "timezone": tz}}
    if location_kind:
        body["location"] = {"kind": location_kind}
    return _call("POST", "/invitees", body=body)


def still_free(et_uri, when):
    """Revalide juste avant de poser : entre la proposition et l'acceptation,
    le creneau a pu etre pris par quelqu'un d'autre."""
    for t in available(et_uri, days=31, earliest_hours=0):
        if abs((t - when).total_seconds()) < 60:
            return True
    return False
