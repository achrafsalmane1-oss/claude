# -*- coding: utf-8 -*-
"""Tests du kit reunion.

Pas de Docker ici : un faux serveur Vexa (http.server) rejoue les reponses
reelles de l'API, documentees dans docs.vexa.ai. On verifie le parsing des
liens, l'extraction du compte rendu, le client HTTP et la CLI de bout en bout.

    python3 -m unittest discover -s meetings -v
    # ou
    python3 meetings/test_meetings.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import notes as notes_mod
from vexa import Vexa, VexaError, meeting_rows, parse_meeting_url, running_bots

KEY = "vxa_test_key"

# transcript type : un brouillon remplace par sa confirmation, un doublon,
# du francais et de l'anglais, des engagements avec et sans echeance.
SEGMENTS = [
    {"speaker": "Achraf", "text": "Merci d'avoir pris le temps aujourd'hui.",
     "start": 0.0, "end": 3.2, "language": "fr", "completed": True},
    {"speaker": "Claire", "text": "Avec plaisir. On a regarde votre proposition.",
     "start": 3.4, "end": 7.0, "language": "fr", "completed": True},
    {"speaker": "Claire", "text": "Honnetement c'est un peu trop cher pour notre budget actuel.",
     "start": 7.1, "end": 11.5, "language": "fr", "completed": True},
    # brouillon : doit disparaitre au profit de la version confirmee
    {"speaker": "Achraf", "text": "Je vais vous envoyer",
     "start": 12.0, "end": 13.0, "language": "fr", "completed": False},
    {"speaker": "Achraf", "text": "Je vais vous envoyer une version revue d'ici vendredi.",
     "start": 12.0, "end": 16.4, "language": "fr", "completed": True},
    # doublon strict du precedent : doit etre ignore
    {"speaker": "Achraf", "text": "Je vais vous envoyer une version revue d'ici vendredi.",
     "start": 16.5, "end": 16.6, "language": "fr", "completed": True},
    {"speaker": "Claire", "text": "On part sur cette base alors.",
     "start": 17.0, "end": 19.8, "language": "fr", "completed": True},
    {"speaker": "Claire", "text": "Can you also send the security questionnaire by Monday?",
     "start": 20.0, "end": 24.5, "language": "en", "completed": True},
]


class StubVexa(BaseHTTPRequestHandler):
    """Rejoue les formes de reponse de l'API Vexa 0.12."""

    no_stt = False          # True -> POST /bots repond 503 comme sans STT
    status_field = "running_bots"

    def log_message(self, *a):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        if self.path == "/health":
            return True
        if self.headers.get("X-API-Key") != KEY:
            self._send(401, {"detail": "invalid api key"})
            return False
        return True

    def do_GET(self):
        if not self._auth():
            return
        if self.path == "/health":
            return self._send(200, {"status": "ok"})
        if self.path == "/bots/status":
            return self._send(200, {
                type(self).status_field: [{
                    "platform": "google_meet", "native_meeting_id": "abc-defg-hij",
                    "status": "active", "created_at": "2026-10-16T09:00:00"}],
                "count": 1})
        if self.path.startswith("/transcripts/google_meet/abc-defg-hij"):
            return self._send(200, {
                "id": 42, "platform": "google_meet",
                "native_meeting_id": "abc-defg-hij", "status": "completed",
                "start_time": "2026-10-16T09:00:00", "segments": SEGMENTS})
        if self.path.startswith("/transcripts/"):
            return self._send(404, {"detail": "meeting not found"})
        if self.path == "/meetings":
            return self._send(200, {"meetings": [{
                "id": 42, "platform": "google_meet",
                "native_meeting_id": "abc-defg-hij", "status": "completed",
                "start_time": "2026-10-16T09:00:00"}]})
        return self._send(404, {"detail": "no route"})

    def do_POST(self):
        if not self._auth():
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or "{}")
        if self.path == "/bots":
            if type(self).no_stt and body.get("transcribe_enabled", True):
                return self._send(503, {"detail": "no transcription backend configured "
                                                  "— set TRANSCRIPTION_SERVICE_URL"})
            if not body.get("meeting_url") and not body.get("native_meeting_id"):
                return self._send(422, {"detail": [
                    {"loc": ["body", "native_meeting_id"], "msg": "field required"}]})
            return self._send(201, {
                "id": 42, "platform": "google_meet",
                "native_meeting_id": "abc-defg-hij", "status": "requested",
                "bot_name": body.get("bot_name"), "echo": body})
        return self._send(404, {"detail": "no route"})

    def do_DELETE(self):
        if not self._auth():
            return
        if self.path == "/bots/google_meet/abc-defg-hij":
            return self._send(200, {"status": "stopping", "meeting_id": 42,
                                    "also_stopped": [], "cancelled": []})
        return self._send(404, {"detail": "no active bot"})


class ServerCase(unittest.TestCase):
    """Demarre le faux serveur une fois pour toute la classe."""

    @classmethod
    def setUpClass(cls):
        StubVexa.no_stt = False
        StubVexa.status_field = "running_bots"
        cls.httpd = HTTPServer(("127.0.0.1", 0), StubVexa)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def client(self):
        return Vexa(base=self.base, key=KEY, timeout=10)


# --- parsing des liens ------------------------------------------------------

class TestParsing(unittest.TestCase):

    def test_meet_standard(self):
        self.assertEqual(parse_meeting_url("https://meet.google.com/abc-defg-hij"),
                         ("google_meet", "abc-defg-hij", None))

    def test_meet_sans_schema(self):
        self.assertEqual(parse_meeting_url("meet.google.com/abc-defg-hij")[1],
                         "abc-defg-hij")

    def test_meet_nickname_workspace(self):
        plat, nid, _ = parse_meeting_url("https://meet.google.com/haven-weekly-sync")
        self.assertEqual((plat, nid), ("google_meet", "haven-weekly-sync"))

    def test_meet_lookup_refuse(self):
        with self.assertRaises(ValueError):
            parse_meeting_url("https://meet.google.com/lookup/abcdef")

    def test_meet_code_invalide(self):
        with self.assertRaises(ValueError):
            parse_meeting_url("https://meet.google.com/AB")

    def test_teams_personnel_avec_passcode(self):
        self.assertEqual(
            parse_meeting_url("https://teams.live.com/meet/397421056486982?p=X8hcQVTnGN"),
            ("teams", "397421056486982", "X8hcQVTnGN"))

    def test_teams_entreprise_deep_link(self):
        plat, nid, pc = parse_meeting_url(
            "https://teams.microsoft.com/v2/?meetingjoin=true#/meet/397421056486982?p=abc")
        self.assertEqual((plat, nid, pc), ("teams", "397421056486982", "abc"))

    def test_teams_thread_id(self):
        plat, nid, _ = parse_meeting_url(
            "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc123%40thread.v2/0")
        self.assertEqual(plat, "teams")
        self.assertIn("thread.v2", nid)

    def test_zoom_avec_pwd(self):
        self.assertEqual(parse_meeting_url("https://us05web.zoom.us/j/81234567890?pwd=secret"),
                         ("zoom", "81234567890", "secret"))

    def test_zoom_gov(self):
        self.assertEqual(parse_meeting_url("https://frbmeetings.zoomgov.com/j/1612345678")[0],
                         "zoom")

    def test_jitsi(self):
        self.assertEqual(parse_meeting_url("https://meet.jit.si/HavenSync"),
                         ("jitsi", "HavenSync", None))

    def test_hote_usurpe_refuse(self):
        """zoom.us.evil.example appartient a l'attaquant : on refuse."""
        for bad in ("https://zoom.us.evil.example/j/81234567890",
                    "https://notzoom.us/j/81234567890",
                    "https://evilteams.live.com/meet/397421056486982"):
            with self.assertRaises(ValueError, msg=bad):
                parse_meeting_url(bad)

    def test_vide(self):
        with self.assertRaises(ValueError):
            parse_meeting_url("")


# --- nettoyage et extraction ------------------------------------------------

class TestNotes(unittest.TestCase):

    def setUp(self):
        self.seg = notes_mod.clean_segments(SEGMENTS)

    def test_brouillon_remplace_par_confirme(self):
        textes = [s["text"] for s in self.seg]
        self.assertNotIn("Je vais vous envoyer", textes)
        self.assertIn("Je vais vous envoyer une version revue d'ici vendredi.", textes)

    def test_doublon_supprime(self):
        n = sum(1 for s in self.seg
                if s["text"] == "Je vais vous envoyer une version revue d'ici vendredi.")
        self.assertEqual(n, 1)

    def test_ordre_chronologique(self):
        starts = [s["start"] for s in self.seg]
        self.assertEqual(starts, sorted(starts))

    def test_tout_garde_si_rien_de_confirme(self):
        live = [{"speaker": "A", "text": "en cours", "start": 1, "end": 2,
                 "completed": False}]
        self.assertEqual(len(notes_mod.clean_segments(live)), 1)

    def test_segments_vides_ignores(self):
        self.assertEqual(notes_mod.clean_segments(
            [{"speaker": "A", "text": "   ", "start": 0, "end": 1, "completed": True}]), [])

    def test_liste_vide(self):
        self.assertEqual(notes_mod.clean_segments([]), [])
        self.assertEqual(notes_mod.clean_segments(None), [])

    def test_temps_de_parole(self):
        rows, total = notes_mod.talk_time(self.seg)
        self.assertGreater(total, 0)
        self.assertAlmostEqual(sum(p for _, _, p in rows), 100.0, places=4)
        self.assertEqual(rows[0][0], "Claire")  # Claire parle le plus

    def test_mmss(self):
        self.assertEqual(notes_mod.mmss(0), "00:00")
        self.assertEqual(notes_mod.mmss(75), "01:15")
        self.assertEqual(notes_mod.mmss(-5), "00:00")

    def test_engagement_francais(self):
        actions = notes_mod.extract(self.seg)["actions"]
        textes = " | ".join(a["text"] for a in actions)
        self.assertIn("version revue", textes)

    def test_engagement_anglais(self):
        actions = notes_mod.extract(self.seg)["actions"]
        self.assertTrue(any("security questionnaire" in a["text"] for a in actions))

    def test_echeance_reperee(self):
        actions = notes_mod.extract(self.seg)["actions"]
        dates = [d.lower() for a in actions for d in a["dates"]]
        self.assertIn("vendredi", dates)
        self.assertIn("monday", dates)

    def test_decision(self):
        decisions = notes_mod.extract(self.seg)["decisions"]
        self.assertTrue(any("On part sur" in d["text"] for d in decisions))

    def test_objection(self):
        objections = notes_mod.extract(self.seg)["objections"]
        self.assertTrue(any("trop cher" in o["text"] for o in objections))

    def test_tours_de_parole_fusionnes(self):
        turns = notes_mod.merge_turns(self.seg)
        speakers = [t["speaker"] for t in turns]
        for a, b in zip(speakers, speakers[1:]):
            self.assertNotEqual(a, b)

    def test_rendu_markdown(self):
        md = notes_mod.render(
            {"title": "Haven x Acme", "platform": "google_meet",
             "native_meeting_id": "abc-defg-hij"}, SEGMENTS)
        self.assertIn("# Haven x Acme", md)
        for section in ("## Engagements reperes", "## Decisions",
                        "## Objections et risques", "## Temps de parole",
                        "## Transcript"):
            self.assertIn(section, md)
        self.assertIn("Achraf", md)

    def test_rendu_sans_segment(self):
        md = notes_mod.render({"platform": "zoom", "native_meeting_id": "1"}, [])
        self.assertIn("Aucun segment transcrit", md)

    def test_rendu_avec_resume_remplace_les_sections(self):
        md = notes_mod.render({"native_meeting_id": "x"}, SEGMENTS,
                              summary="## Resume\n- tout va bien")
        self.assertIn("- tout va bien", md)
        self.assertNotIn("## Engagements reperes", md)

    def test_resume_ai_sans_cle_leve_une_erreur_claire(self):
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                notes_mod.ai_summary(self.seg)
            self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old


# --- client HTTP ------------------------------------------------------------

class TestClient(ServerCase):

    def test_envoi_bot_par_url(self):
        res = self.client().send_bot("https://meet.google.com/abc-defg-hij",
                                     bot_name="Notes")
        self.assertEqual(res["native_meeting_id"], "abc-defg-hij")
        self.assertEqual(res["echo"]["meeting_url"],
                         "https://meet.google.com/abc-defg-hij")
        self.assertEqual(res["echo"]["bot_name"], "Notes")
        self.assertTrue(res["echo"]["transcribe_enabled"])

    def test_langue_omise_par_defaut(self):
        """Sans langue explicite, Whisper detecte : ne jamais forcer."""
        os.environ.pop("VEXA_LANG", None)
        res = self.client().send_bot("https://meet.google.com/abc-defg-hij")
        self.assertNotIn("language", res["echo"])

    def test_langue_forcee(self):
        res = self.client().send_bot("https://meet.google.com/abc-defg-hij",
                                     language="fr")
        self.assertEqual(res["echo"]["language"], "fr")

    def test_capture_seule(self):
        res = self.client().send_bot("https://meet.google.com/abc-defg-hij",
                                     transcribe=False)
        self.assertFalse(res["echo"]["transcribe_enabled"])

    def test_id_nu_refuse(self):
        with self.assertRaises(ValueError):
            self.client().send_bot("abc-defg-hij")

    def test_transcript(self):
        payload = self.client().transcript("google_meet", "abc-defg-hij")
        self.assertEqual(len(payload["segments"]), len(SEGMENTS))

    def test_transcript_inconnu(self):
        with self.assertRaises(VexaError) as ctx:
            self.client().transcript("zoom", "000")
        self.assertEqual(ctx.exception.status, 404)

    def test_bots_status_nouveau_champ(self):
        try:
            StubVexa.status_field = "running"
            bots = running_bots(self.client().bots_status())
            self.assertEqual(len(bots), 1)
        finally:
            StubVexa.status_field = "running_bots"

    def test_bots_status_ancien_champ(self):
        self.assertEqual(len(running_bots(self.client().bots_status())), 1)

    def test_meetings(self):
        self.assertEqual(len(meeting_rows(self.client().meetings())), 1)

    def test_stop(self):
        self.assertEqual(self.client().stop_bot("google_meet", "abc-defg-hij")["status"],
                         "stopping")

    def test_cle_invalide(self):
        with self.assertRaises(VexaError) as ctx:
            Vexa(base=self.base, key="mauvaise", timeout=10).bots_status()
        self.assertEqual(ctx.exception.status, 401)

    def test_cle_absente_message_utile(self):
        with self.assertRaises(VexaError) as ctx:
            Vexa(base=self.base, key="", timeout=10).bots_status()
        self.assertIn("VEXA_API_KEY", ctx.exception.detail)

    def test_serveur_eteint(self):
        with self.assertRaises(VexaError) as ctx:
            Vexa(base="http://127.0.0.1:1", key=KEY, timeout=3).bots_status()
        self.assertIn("injoignable", ctx.exception.detail)

    def test_health(self):
        self.assertEqual(self.client().health()[0], 200)

    def test_erreur_422_lisible(self):
        """Les erreurs de validation FastAPI arrivent en liste : on les aplatit."""
        v = self.client()
        try:
            v._call("POST", "/bots", {})
        except VexaError as e:
            self.assertEqual(e.status, 422)
            self.assertIn("native_meeting_id", e.detail)
        else:
            self.fail("422 attendu")


class TestSansSTT(ServerCase):
    """Le piege n1 d'une install maison : le bot part sans moteur de transcription."""

    def test_503_explicite(self):
        try:
            StubVexa.no_stt = True
            with self.assertRaises(VexaError) as ctx:
                self.client().send_bot("https://meet.google.com/abc-defg-hij")
            self.assertEqual(ctx.exception.status, 503)
            self.assertIn("transcription", ctx.exception.detail.lower())
        finally:
            StubVexa.no_stt = False

    def test_capture_seule_passe_sans_stt(self):
        try:
            StubVexa.no_stt = True
            res = self.client().send_bot("https://meet.google.com/abc-defg-hij",
                                         transcribe=False)
            self.assertEqual(res["native_meeting_id"], "abc-defg-hij")
        finally:
            StubVexa.no_stt = False


# --- la CLI, en vrai (sous-processus) ---------------------------------------

class TestCLI(ServerCase):

    def run_meet(self, *argv, **kw):
        env = dict(os.environ)
        env.update({
            "VEXA_API_BASE": self.base,
            "VEXA_API_KEY": KEY,
            "MEETING_STATE": os.path.join(self.tmp, "state.json"),
            "MEETING_NOTES_DIR": os.path.join(self.tmp, "notes"),
        })
        env.pop("MEETING_WEBHOOK_URL", None)
        env.update(kw.get("env", {}))
        return subprocess.run(
            [sys.executable, os.path.join(HERE, "meet.py")] + list(argv),
            capture_output=True, text=True, env=env, timeout=60)

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_join_memorise_puis_notes_sans_argument(self):
        r = self.run_meet("join", "https://meet.google.com/abc-defg-hij")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("google_meet/abc-defg-hij", r.stdout)

        state = json.load(open(os.path.join(self.tmp, "state.json")))
        self.assertEqual(state["last"]["native_meeting_id"], "abc-defg-hij")

        # `notes` sans cible doit retrouver la derniere reunion
        r2 = self.run_meet("notes")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("Compte rendu", r2.stdout)

        produced = os.listdir(os.path.join(self.tmp, "notes"))
        self.assertEqual(len(produced), 1)
        md = open(os.path.join(self.tmp, "notes", produced[0]), encoding="utf-8").read()
        self.assertIn("## Transcript", md)
        self.assertIn("version revue", md)

    def test_notes_nom_de_fichier_date(self):
        self.run_meet("join", "https://meet.google.com/abc-defg-hij")
        self.run_meet("notes")
        name = os.listdir(os.path.join(self.tmp, "notes"))[0]
        self.assertTrue(name.startswith("2026-10-16-google_meet-abc-defg-hij"), name)

    def test_notes_cible_explicite(self):
        r = self.run_meet("notes", "google_meet/abc-defg-hij")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_notes_par_url(self):
        r = self.run_meet("notes", "https://meet.google.com/abc-defg-hij")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_notes_sans_memoire_echoue_proprement(self):
        r = self.run_meet("notes")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("aucune reunion en memoire", r.stderr)

    def test_status(self):
        r = self.run_meet("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("abc-defg-hij", r.stdout)

    def test_list(self):
        r = self.run_meet("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("google_meet", r.stdout)

    def test_stop(self):
        self.run_meet("join", "https://meet.google.com/abc-defg-hij")
        r = self.run_meet("stop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Arret demande", r.stdout)

    def test_watch_sort_quand_la_reunion_est_terminee(self):
        r = self.run_meet("watch", "google_meet/abc-defg-hij", "--interval", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Achraf", r.stdout)
        self.assertIn("Reunion completed", r.stdout)

    def test_doctor_ok(self):
        r = self.run_meet("doctor")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Diagnostic OK", r.stdout)

    def test_doctor_detecte_stack_eteinte(self):
        r = self.run_meet("doctor", env={"VEXA_API_BASE": "http://127.0.0.1:1"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("passerelle muette", r.stdout)

    def test_doctor_detecte_cle_absente(self):
        r = self.run_meet("doctor", env={"VEXA_API_KEY": ""})
        self.assertIn("VEXA_API_KEY absente", r.stdout)

    def test_webhook_dry_run(self):
        self.run_meet("join", "https://meet.google.com/abc-defg-hij")
        r = self.run_meet("notes", env={
            "MEETING_WEBHOOK_URL": "https://hook.example.com/x", "DRY_RUN": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DRY_RUN", r.stdout)

    def test_aide(self):
        r = self.run_meet()
        self.assertEqual(r.returncode, 0)
        self.assertIn("join", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
