# meetings — enregistreur de reunion auto-heberge

Un bot rejoint tes Google Meet / Zoom / Teams comme un participant, transcrit
en direct avec attribution des locuteurs, et sort un compte rendu markdown
(engagements, decisions, objections, temps de parole). Tout tourne chez toi.

Pas d'abonnement, pas de transcript qui part chez un tiers.

Le moteur est [Vexa](https://github.com/Vexa-ai/vexa) (Apache-2.0). Ce dossier
est la couche au-dessus : installation en une commande, CLI utilisable au
quotidien, compte rendu oriente GTM, et sortie webhook vers Make / n8n / Clay.

---

## Ce que ca coute vraiment

| | Fireflies / Otter | ce dossier |
|---|---|---|
| Logiciel | 10 a 19 $/utilisateur/mois | **0 EUR** (Apache-2.0) |
| Transcription | incluse, cloud du vendeur | **0 EUR** — Whisper sur ton CPU |
| Ou vivent tes transcripts | serveurs du vendeur | ton disque |
| Materiel | — | ta machine allumee pendant l'appel, ou un VPS a ~15-25 EUR/mois |
| Resume redige (option) | inclus | ~0,05 a 0,15 EUR/heure d'appel, **et seulement si tu l'actives** |

Le piege a eviter : si tu prends un VPS dedie pour ca, tu paies ~20 EUR/mois
et tu n'as rien gagne face a Fireflies. **Le vrai interet, c'est de le faire
tourner sur ta propre machine** (Mac avec Docker Desktop, ou un Linux que tu as
deja), ou sur un serveur qui sert deja a autre chose.

---

## Installation

Sur **ta** machine, pas dans un CI : le bot doit sortir sur internet pour
rejoindre l'appel.

```bash
./meetings/setup.sh
```

Il verifie les prerequis (Docker >= 26, make, git, place disque), clone Vexa
dans `~/vexa`, demarre la stack **avec Whisper CPU local** (donc sans cle de
transcription et sans GPU), recupere la cle d'API et l'ecrit dans
`meetings/.env`, puis lance le diagnostic.

Premiere fois : 10 a 25 minutes (images Docker + modele). Ensuite, immediat.

Reglages utiles :

```bash
VEXA_DIR=/srv/vexa ./meetings/setup.sh                            # installer ailleurs
WHISPER_MODEL=Systran/faster-whisper-tiny.en ./meetings/setup.sh   # + rapide, ANGLAIS seulement
```

---

## Au quotidien

```bash
cd meetings

./meet.py join https://meet.google.com/abc-defg-hij   # le bot rejoint
./meet.py watch                                       # transcript en direct
./meet.py notes                                       # compte rendu markdown
./meet.py stop                                        # faire sortir le bot

./meet.py status     # bots en cours
./meet.py list       # reunions enregistrees
./meet.py doctor     # qu'est-ce qui est casse, et quoi faire
```

La cible par defaut est la derniere reunion rejointe (memorisee dans
`state.json`). Sinon : une URL complete, ou `google_meet/abc-defg-hij`.

Les comptes rendus atterrissent dans `meetings/notes/` (hors git : ce sont des
conversations). Exemple de sortie :

```markdown
## Engagements reperes
- [ ] **Achraf** (00:12) : Je vais vous envoyer une version revue d'ici vendredi. — *vendredi*
- [ ] **Claire** (00:20) : Can you also send the security questionnaire by Monday? — *Monday*

## Decisions
- **Claire** (00:17) : On part sur cette base alors.

## Objections et risques
- **Claire** (00:07) : Honnetement c'est un peu trop cher pour notre budget actuel.

## Temps de parole
| Claire | 00:15 | 67% |
| Achraf | 00:07 | 33% |
```

Les engagements / decisions / objections sont reperes par formules
declencheuses, en francais **et** en anglais (les appels melangent les deux).
C'est deterministe : aucun appel reseau, aucun cout, et ca ne rajoute jamais un
engagement que personne n'a pris. En revanche ca cite des phrases, ca ne redige
pas de synthese.

Pour une synthese redigee :

```bash
pip install anthropic          # une seule fois
export ANTHROPIC_API_KEY=sk-ant-...
./meet.py notes --ai
```

C'est la **seule** partie payante, et si la cle manque ou que l'appel echoue,
la commande retombe sur le compte rendu deterministe au lieu de planter.

---

## Brancher sur le reste de la stack

```bash
# dans meetings/.env
MEETING_WEBHOOK_URL=https://hook.eu1.make.com/xxxx
```

`./meet.py notes` POSTe alors ce JSON :

```json
{
  "source": "vexa-self-hosted",
  "platform": "google_meet",
  "native_meeting_id": "abc-defg-hij",
  "title": "...", "start_time": "...", "status": "completed",
  "markdown": "# ...",
  "actions":    [{"speaker": "Achraf", "text": "...", "dates": ["vendredi"]}],
  "decisions":  [{"speaker": "Claire", "text": "..."}],
  "objections": [{"speaker": "Claire", "text": "..."}]
}
```

De la, c'est du terrain connu : creer la tache dans le CRM, pousser une note
sur le contact, declencher la sequence de relance. `DRY_RUN=1` journalise la
charge utile sans l'envoyer.

Vexa sait aussi pousser ses propres webhooks (`meeting.completed`,
`bot.failed`) si tu preferes etre notifie sans lancer `notes` a la main :
`PUT /user/webhook`, signature HMAC `X-Webhook-Signature`.

---

## Les cinq choses qui surprennent

1. **Le bot attend parfois dans le hall.** Sur Meet et Teams, admets-le comme
   un invite, sinon il ne transcrit rien.
2. **Le bot part tout seul apres 10 minutes sans audio.** C'est voulu. Pour un
   appel avec de longs silences, augmente la fenetre :
   `automatic_leave.max_time_left_alone` cote API.
3. **`POST /bots` qui repond 503 = pas de moteur de transcription.** C'est
   l'erreur n1 d'une install maison. `./meet.py doctor` te le dit, et
   `setup.sh` cable la STT locale precisement pour eviter ca.
4. **Whisper `small` sur CPU est moins bon que le cloud de Fireflies.** Noms
   propres, acronymes et accents marques en souffrent. C'est le prix du zero
   euro. Si la precision compte : `WHISPER_MODEL=Systran/faster-whisper-medium`
   sur une machine avec GPU, ou monte l'unite GPU dediee
   (`deploy/transcription` dans le depot Vexa).
5. **Un bot nomme dans la liste des participants, ce n'est pas un accord pour
   enregistrer.** Selon les pays et les Etats, enregistrer un appel demande le
   consentement de tous. Garde `VEXA_BOT_NAME` explicite et dis-le a l'oral :
   c'est aussi ce qui evite que ton bot se fasse virer de l'appel.

---

## Depannage

```bash
./meet.py doctor                      # commence toujours par la
docker ps | grep vexa                 # la stack tourne ?
docker logs --tail 50 vexa-lite       # erreurs du plan de controle
docker logs --tail 50 vexa-lite-whisper   # erreurs de transcription
curl -s localhost:8083/health         # la STT locale repond ?
```

| Symptome | Cause probable |
|---|---|
| `Vexa injoignable` | stack eteinte -> `./meetings/setup.sh` (idempotent) |
| 503 a l'envoi du bot | pas de STT -> relancer setup.sh, voir logs whisper |
| bot rejoint, zero segment | meme cause : STT absente ou modele pas charge |
| 409 | un bot est deja dans cet appel |
| 403 / 429 | limite de bots simultanes -> `./meet.py stop` |
| port deja pris | `make -C ~/vexa/deploy/lite all LOCAL_STT=1 HOST_GATEWAY_PORT=18056` puis corriger `VEXA_API_BASE` |

Tout arreter sans perdre les donnees :
`make -C ~/vexa/deploy/lite down`

---

## Tests

```bash
python3 meetings/test_meetings.py      # 63 tests, ~5 s, aucun reseau requis
```

Un faux serveur Vexa rejoue les reponses reelles de l'API. Couvre le parsing
des liens (y compris le refus de `zoom.us.evil.example`), le nettoyage des
segments brouillon/confirme, l'extraction FR+EN, le rendu markdown, les erreurs
HTTP (401/404/422/503) et la CLI en sous-processus.

---

## Ce qui n'a pas pu etre verifie ici

Les tests ci-dessus passent, mais ils rejouent l'API : ils ne prouvent pas que
la stack demarre. Le conteneur ou ce dossier a ete ecrit n'avait **pas de demon
Docker**, donc ces trois choses restent a valider sur ta machine, au premier
`setup.sh` :

- la mise en route de Vexa Lite elle-meme (`make -C deploy/lite all LOCAL_STT=1`) ;
- le bot qui rejoint pour de vrai un Meet / Zoom / Teams ;
- la qualite reelle de Whisper `small` sur CPU pour tes appels.

Les commandes, ports (`8056` passerelle, `3001` interface web, `8083` STT),
noms de conteneurs (`vexa-lite`, `vexa-lite-whisper`) et le chemin de la cle
(`/run/vexa/key.env`) sont lus dans `deploy/lite/Makefile` et
`bin/provision-key.sh` du depot Vexa, pas devines.

## Fichiers

| | |
|---|---|
| `setup.sh` | installation + demarrage + recuperation de la cle |
| `meet.py` | la CLI (join / watch / notes / stop / status / list / doctor) |
| `vexa.py` | client API et parsing des liens de reunion |
| `notes.py` | transcript -> markdown, et resume Claude optionnel |
| `test_meetings.py` | les tests |
| `.env.example` | tous les reglages, commentes |
