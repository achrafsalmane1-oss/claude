#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""meet -- envoyer un bot en reunion, recuperer le transcript, sortir le CR.

Remplace Fireflies / Otter par une stack qu'on heberge soi-meme (Vexa,
Apache-2.0) : le bot rejoint Meet / Zoom / Teams / Jitsi comme un participant,
Whisper tourne en local sur CPU, rien ne sort du reseau et il n'y a pas
d'abonnement.

  ./meet.py join https://meet.google.com/abc-defg-hij
  ./meet.py watch                 # transcript en direct (derniere reunion)
  ./meet.py notes --ai            # compte rendu markdown
  ./meet.py stop
  ./meet.py status | list | doctor

La reunion visee est, par defaut, la derniere sur laquelle on a envoye un bot
(memorisee dans state.json). Sinon : une URL complete, ou `plateforme/id`.

Variables d'environnement : voir .env.example
  MEETING_WEBHOOK_URL   si defini, `notes` POSTe le CR en JSON (Make, n8n,
                        Clay, Zapier...). DRY_RUN=1 journalise sans envoyer.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import notes as notes_mod
from vexa import (PLATFORMS, Vexa, VexaError, load_env, meeting_rows,
                  parse_meeting_url, running_bots)

# surchargeables pour les tests (et si on veut ranger les CR ailleurs)
STATE = os.environ.get("MEETING_STATE") or os.path.join(HERE, "state.json")
NOTES_DIR = os.environ.get("MEETING_NOTES_DIR") or os.path.join(HERE, "notes")


# --- etat -------------------------------------------------------------------

def read_state():
    try:
        with open(STATE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def write_state(state):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE)


def remember(platform, native_id, extra=None):
    state = read_state()
    state["last"] = {"platform": platform, "native_meeting_id": native_id}
    if extra:
        state["last"].update(extra)
    seen = state.setdefault("meetings", {})
    seen["%s/%s" % (platform, native_id)] = dict(
        (extra or {}), platform=platform, native_meeting_id=native_id,
        seen_at=datetime.now().isoformat(timespec="seconds"))
    write_state(state)


def resolve(target):
    """`target` -> (platform, native_id). Vide = derniere reunion connue."""
    if not target:
        last = read_state().get("last") or {}
        if last.get("platform") and last.get("native_meeting_id"):
            return last["platform"], last["native_meeting_id"]
        die("aucune reunion en memoire : donne l'URL ou `plateforme/id`")
    target = target.strip()
    # forme plateforme/id
    if "/" in target and "://" not in target:
        plat, _, nid = target.partition("/")
        if plat in PLATFORMS and nid:
            return plat, nid
    try:
        plat, nid, _pass = parse_meeting_url(target)
        return plat, nid
    except ValueError as e:
        die(str(e))


def die(msg, code=1):
    sys.stderr.write("meet: %s\n" % msg)
    raise SystemExit(code)


# --- commandes --------------------------------------------------------------

def cmd_join(args):
    vexa = Vexa()
    try:
        res = vexa.send_bot(
            args.url,
            bot_name=args.name,
            language=args.lang,
            task="translate" if args.translate else None,
            passcode=args.passcode,
            transcribe=not args.no_transcribe,
            record=args.record,
        )
    except VexaError as e:
        if e.status == 503:
            die("Vexa refuse : aucun moteur de transcription configure.\n"
                "       `./meet.py doctor` dit quoi corriger "
                "(le plus souvent : relancer setup.sh avec LOCAL_STT=1).")
        if e.status == 409:
            die("un bot est deja dans cette reunion (`./meet.py status`)")
        if e.status in (403, 429):
            die("limite de bots simultanes atteinte : arrete un bot en cours "
                "(`./meet.py status` puis `./meet.py stop <id>`)")
        raise

    # l'API renvoie l'enregistrement de reunion : on lit ce qu'elle a compris
    rec = res if isinstance(res, dict) else {}
    inner = rec.get("meeting") if isinstance(rec.get("meeting"), dict) else rec
    platform = inner.get("platform")
    native_id = inner.get("native_meeting_id")
    if not (platform and native_id):
        platform, native_id, _ = parse_meeting_url(args.url)

    remember(platform, native_id, {
        "id": inner.get("id"),
        "status": inner.get("status"),
        "url": args.url,
    })
    print("Bot envoye -> %s/%s" % (platform, native_id))
    if inner.get("status"):
        print("Statut     : %s" % inner["status"])
    print("")
    print("  transcript en direct : ./meet.py watch")
    print("  compte rendu         : ./meet.py notes")
    print("")
    print("Sur Meet et Teams le bot peut attendre dans le hall : admets-le "
          "comme un invite.")
    return 0


def cmd_status(args):
    vexa = Vexa()
    bots = running_bots(vexa.bots_status())
    if not bots:
        print("Aucun bot en cours.")
        return 0
    print("%d bot(s) en cours :" % len(bots))
    for b in bots:
        if not isinstance(b, dict):
            print("  - %s" % b)
            continue
        print("  - %s/%s  statut=%s  depuis=%s" % (
            b.get("platform", "?"), b.get("native_meeting_id", "?"),
            b.get("status", "?"), b.get("created_at") or b.get("start_time") or "?"))
    return 0


def cmd_list(args):
    vexa = Vexa()
    rows = meeting_rows(vexa.meetings())
    if not rows:
        print("Aucune reunion enregistree.")
        return 0
    rows = rows[-args.limit:] if args.limit else rows
    for m in rows:
        if not isinstance(m, dict):
            continue
        print("%-12s %-20s %-10s %s" % (
            m.get("platform", "?"),
            m.get("native_meeting_id", "?"),
            m.get("status", "?"),
            (m.get("start_time") or m.get("created_at") or "")[:19]))
    return 0


def cmd_watch(args):
    platform, native_id = resolve(args.target)
    vexa = Vexa()
    print("Transcript %s/%s -- Ctrl-C pour arreter." % (platform, native_id))
    print("(les brouillons non confirmes ne sont pas affiches)")
    print("")
    printed = set()
    idle = 0
    try:
        while True:
            try:
                payload = vexa.transcript(platform, native_id)
            except VexaError as e:
                if e.status == 404:
                    die("reunion inconnue : %s/%s" % (platform, native_id))
                sys.stderr.write("  (erreur passagere : %s)\n" % e.detail[:120])
                time.sleep(args.interval)
                continue

            segs = notes_mod.clean_segments((payload or {}).get("segments") or [])
            new = 0
            for seg in segs:
                key = (seg["speaker"], round(seg["start"], 2), seg["text"][:60])
                if key in printed:
                    continue
                printed.add(key)
                new += 1
                print("[%s] %s : %s" % (
                    notes_mod.mmss(seg["start"]), seg["speaker"], seg["text"]))
            idle = 0 if new else idle + 1

            status = (payload or {}).get("status")
            if status in ("completed", "failed") and not new:
                print("")
                print("Reunion %s. Compte rendu : ./meet.py notes %s/%s" % (
                    status, platform, native_id))
                return 0
            if args.until_idle and idle * args.interval >= args.until_idle:
                print("")
                print("Rien de nouveau depuis %ds, j'arrete." % args.until_idle)
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("")
        return 0


def cmd_notes(args):
    platform, native_id = resolve(args.target)
    vexa = Vexa()
    try:
        payload = vexa.transcript(platform, native_id)
    except VexaError as e:
        if e.status == 404:
            die("reunion inconnue : %s/%s" % (platform, native_id))
        raise

    payload = payload or {}
    segments = payload.get("segments") or []
    meta = {
        "title": args.title or payload.get("title")
                 or (payload.get("data") or {}).get("title"),
        "platform": payload.get("platform") or platform,
        "native_meeting_id": payload.get("native_meeting_id") or native_id,
        "start_time": payload.get("start_time"),
        "status": payload.get("status"),
    }

    summary = None
    if args.ai:
        try:
            summary = notes_mod.ai_summary(notes_mod.clean_segments(segments),
                                           model=args.model)
        except Exception as e:
            sys.stderr.write("meet: resume Claude indisponible (%s)\n"
                             "      -> je rends le compte rendu deterministe.\n" % e)

    markdown = notes_mod.render(meta, segments, summary=summary)

    out = args.out
    if not out:
        os.makedirs(NOTES_DIR, exist_ok=True)
        stamp = (meta.get("start_time") or datetime.now().isoformat())[:10]
        out = os.path.join(NOTES_DIR, "%s-%s-%s.md" % (stamp, platform, native_id))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    print("Compte rendu : %s" % out)

    nb = len(notes_mod.clean_segments(segments))
    print("Segments     : %d" % nb)
    if nb == 0:
        print("")
        print("Zero segment : le bot a pu rejoindre sans que la STT tourne.")
        print("Diagnostic   : ./meet.py doctor")

    hook = os.environ.get("MEETING_WEBHOOK_URL", "").strip()
    if hook and nb:
        push_webhook(hook, meta, markdown, segments)
    return 0


def push_webhook(url, meta, markdown, segments):
    """POST du CR vers Make / n8n / Clay / Zapier."""
    facts = notes_mod.extract(notes_mod.clean_segments(segments))
    body = {
        "source": "vexa-self-hosted",
        "platform": meta.get("platform"),
        "native_meeting_id": meta.get("native_meeting_id"),
        "title": meta.get("title"),
        "start_time": meta.get("start_time"),
        "status": meta.get("status"),
        "markdown": markdown,
        "actions": [{"speaker": a["speaker"], "text": a["text"], "dates": a["dates"]}
                    for a in facts["actions"]],
        "decisions": [{"speaker": d["speaker"], "text": d["text"]}
                      for d in facts["decisions"]],
        "objections": [{"speaker": o["speaker"], "text": o["text"]}
                       for o in facts["objections"]],
    }
    if os.environ.get("DRY_RUN", "") not in ("", "0", "false", "False"):
        print("Webhook      : DRY_RUN, non envoye (%d octets)"
              % len(json.dumps(body)))
        return
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print("Webhook      : %s %s" % (r.status, url))
    except urllib.error.HTTPError as e:
        sys.stderr.write("meet: webhook refuse (%s) %s\n" % (e.code, url))
    except Exception as e:
        sys.stderr.write("meet: webhook injoignable (%s)\n" % e)


def cmd_stop(args):
    platform, native_id = resolve(args.target)
    vexa = Vexa()
    try:
        res = vexa.stop_bot(platform, native_id)
    except VexaError as e:
        if e.status == 404:
            die("aucun bot actif sur %s/%s" % (platform, native_id))
        raise
    print("Arret demande : %s/%s (%s)" % (
        platform, native_id, (res or {}).get("status", "ok")))
    print("Compte rendu  : ./meet.py notes %s/%s" % (platform, native_id))
    return 0


def cmd_doctor(args):
    """Dit precisement ce qui manque, dans l'ordre ou ca casse."""
    load_env()
    vexa = Vexa()
    ok = True
    print("Base API     : %s" % vexa.base)

    status, _body = vexa.health()
    if status == 200:
        print("  [ok] passerelle joignable")
    else:
        ok = False
        print("  [KO] passerelle muette (%s)" % (status or "connexion refusee"))
        print("       -> la stack tourne ? `docker ps | grep vexa-lite`")
        print("       -> sinon : ./meetings/setup.sh")

    if vexa.key:
        print("  [ok] VEXA_API_KEY presente (%s...)" % vexa.key[:10])
    else:
        ok = False
        print("  [KO] VEXA_API_KEY absente")
        print("       -> docker exec vexa-lite cat /run/vexa/key.env")

    if status == 200 and vexa.key:
        try:
            bots = running_bots(vexa.bots_status())
            print("  [ok] cle acceptee -- %d bot(s) en cours" % len(bots))
        except VexaError as e:
            ok = False
            print("  [KO] cle refusee : %s" % e.detail[:160])

    # la STT est le piege n1 d'une install auto-hebergee
    print("Transcription :")
    stt = os.environ.get("TRANSCRIPTION_SERVICE_URL", "")
    print("  info  TRANSCRIPTION_SERVICE_URL (cote hote) = %s" % (stt or "(non vu ici)"))
    print("  note  sur Vexa Lite la STT locale est cablee DANS le conteneur :")
    print("        docker ps --filter name=vexa-lite-whisper")
    print("        curl -s localhost:8083/health")
    print("        un POST /bots qui repond 503 = pas de STT configuree.")
    print("")
    print("Diagnostic %s" % ("OK" if ok else "INCOMPLET"))
    return 0 if ok else 1


# --- cli --------------------------------------------------------------------

def main(argv=None):
    load_env()
    p = argparse.ArgumentParser(
        prog="meet",
        description="Bot de reunion auto-heberge : rejoindre, transcrire, "
                    "sortir le compte rendu.")
    sub = p.add_subparsers(dest="cmd")

    j = sub.add_parser("join", help="envoyer un bot dans une reunion")
    j.add_argument("url", help="URL complete de la reunion")
    j.add_argument("--name", help="nom affiche du bot")
    j.add_argument("--lang", help="forcer la langue (fr, en...) ; vide = auto")
    j.add_argument("--passcode", help="code d'acces (Zoom/Teams) s'il n'est pas dans l'URL")
    j.add_argument("--translate", action="store_true", help="traduire au lieu de transcrire")
    j.add_argument("--no-transcribe", action="store_true",
                   help="capture seule, sans transcription")
    j.add_argument("--record", action="store_true", help="garder l'audio")
    j.set_defaults(func=cmd_join)

    w = sub.add_parser("watch", help="afficher le transcript en direct")
    w.add_argument("target", nargs="?", help="URL ou plateforme/id (defaut : derniere)")
    w.add_argument("--interval", type=int, default=5, help="secondes entre deux lectures")
    w.add_argument("--until-idle", type=int, default=0,
                   help="s'arreter apres N secondes sans nouveau segment")
    w.set_defaults(func=cmd_watch)

    n = sub.add_parser("notes", help="ecrire le compte rendu markdown")
    n.add_argument("target", nargs="?", help="URL ou plateforme/id (defaut : derniere)")
    n.add_argument("--ai", action="store_true",
                   help="resume redige par Claude (payant, ANTHROPIC_API_KEY)")
    n.add_argument("--model", help="modele pour --ai (defaut claude-opus-5-5)")
    n.add_argument("--out", help="chemin du fichier de sortie")
    n.add_argument("--title", help="titre de la reunion")
    n.set_defaults(func=cmd_notes)

    s = sub.add_parser("stop", help="faire sortir le bot")
    s.add_argument("target", nargs="?", help="URL ou plateforme/id (defaut : derniere)")
    s.set_defaults(func=cmd_stop)

    st = sub.add_parser("status", help="bots en cours")
    st.set_defaults(func=cmd_status)

    ls = sub.add_parser("list", help="reunions enregistrees")
    ls.add_argument("--limit", type=int, default=20)
    ls.set_defaults(func=cmd_list)

    d = sub.add_parser("doctor", help="diagnostiquer l'installation")
    d.set_defaults(func=cmd_doctor)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    try:
        return args.func(args)
    except VexaError as e:
        die(str(e))
    except ValueError as e:
        die(str(e))


if __name__ == "__main__":
    raise SystemExit(main())
