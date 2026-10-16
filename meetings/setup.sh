#!/usr/bin/env bash
# =============================================================================
# Installe et demarre un enregistreur de reunion auto-heberge (Vexa, Apache-2.0)
# =============================================================================
# A lancer sur TA machine (Mac avec Docker Desktop, ou un Linux / VPS), pas
# dans un conteneur de CI : le bot doit pouvoir sortir sur internet pour
# rejoindre la reunion.
#
#   ./meetings/setup.sh
#
# Ce que ca fait, dans l'ordre :
#   1. verifie docker (>= 26), make, git, curl, et la place disque
#   2. clone (ou met a jour) Vexa dans $VEXA_DIR
#   3. demarre Vexa Lite AVEC Whisper CPU local  -> zero cle, zero GPU, 0 EUR
#   4. recupere la cle d'API et l'ecrit dans meetings/.env
#   5. lance le diagnostic
#
# Reglages (variables d'environnement) :
#   VEXA_DIR       ou installer Vexa            (defaut $HOME/vexa)
#   WHISPER_MODEL  modele de transcription      (defaut Systran/faster-whisper-small)
#                  small = multilingue, tient le direct sur ~4-6 vCPU.
#                  tiny.en = plus rapide mais ANGLAIS SEULEMENT.
#                  medium / large-v3 = meilleur, mais il faut un GPU.
#   SKIP_PULL=1    ne pas refaire un git pull si Vexa est deja la
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VEXA_DIR="${VEXA_DIR:-$HOME/vexa}"
WHISPER_MODEL="${WHISPER_MODEL:-Systran/faster-whisper-small}"
GATEWAY="http://localhost:8056"
TERMINAL="http://localhost:3001"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mok\033[0m   %s\n' "$*"; }
warn() { printf '  \033[33mnote\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31mKO\033[0m   %s\n' "$*"; }
fail() { bad "$*"; exit 1; }

# --- 1. prerequis -----------------------------------------------------------
say "1/5  Prerequis"

for bin in docker make git curl; do
  command -v "$bin" >/dev/null 2>&1 || fail "$bin manquant. Sur Mac : installe Docker Desktop (docker+make), sinon apt install $bin"
done
ok "docker, make, git, curl presents"

if ! docker info >/dev/null 2>&1; then
  fail "le demon Docker ne repond pas. Lance Docker Desktop (ou: sudo systemctl start docker) puis relance ce script."
fi
ok "demon Docker actif"

DV="$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 0)"
DMAJ="${DV%%.*}"
if [ "${DMAJ:-0}" -lt 26 ] 2>/dev/null; then
  warn "Docker $DV : Vexa demande >= 26, la mise en route peut echouer"
else
  ok "Docker $DV"
fi

CORES="$( (nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null) || echo '?')"
ok "coeurs CPU disponibles : $CORES"
case "$WHISPER_MODEL" in
  *tiny*) : ;;
  *small*)
    if [ "$CORES" != "?" ] && [ "$CORES" -lt 4 ] 2>/dev/null; then
      warn "moins de 4 coeurs : 'small' risque de prendre du retard sur le direct."
      warn "pour alleger : WHISPER_MODEL=Systran/faster-whisper-tiny.en (anglais seulement)"
    fi
    ;;
  *medium*|*large*)
    warn "$WHISPER_MODEL sans GPU ne tiendra PAS le direct : garde small sur CPU."
    ;;
esac

AVAIL_GB="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2{printf "%d", $4/1048576}')"
if [ -n "${AVAIL_GB:-}" ] && [ "$AVAIL_GB" -lt 15 ] 2>/dev/null; then
  warn "seulement ${AVAIL_GB} Go libres : les images Vexa + le modele en demandent ~15"
else
  ok "place disque : ${AVAIL_GB:-?} Go libres"
fi

# --- 2. recuperer Vexa ------------------------------------------------------
say "2/5  Code de Vexa dans $VEXA_DIR"

if [ -d "$VEXA_DIR/.git" ]; then
  if [ "${SKIP_PULL:-}" = "1" ]; then
    ok "deja present (pull ignore)"
  else
    git -C "$VEXA_DIR" pull --ff-only >/dev/null 2>&1 && ok "mis a jour" || warn "git pull impossible, on garde la copie locale"
  fi
else
  git clone --depth 1 https://github.com/Vexa-ai/vexa.git "$VEXA_DIR" >/dev/null 2>&1 \
    || fail "clone impossible (reseau ?)"
  ok "clone effectue"
fi

# --- 3. demarrage avec Whisper CPU local ------------------------------------
say "3/5  Demarrage de la stack (modele $WHISPER_MODEL)"
warn "premiere fois : telechargement d'images + du modele, compte 10 a 25 minutes."
warn "la suite est instantanee (tout reste en cache)."

if ! make -C "$VEXA_DIR/deploy/lite" all LOCAL_STT=1 WHISPER_MODEL="$WHISPER_MODEL"; then
  bad "la mise en route a echoue."
  echo "       Journaux utiles :"
  echo "         docker logs --tail 50 vexa-lite"
  echo "         docker logs --tail 50 vexa-lite-whisper"
  echo "       Ports deja pris ? relance avec :"
  echo "         make -C $VEXA_DIR/deploy/lite all LOCAL_STT=1 HOST_GATEWAY_PORT=18056"
  exit 1
fi
ok "stack demarree"

# --- 4. cle d'API -----------------------------------------------------------
say "4/5  Cle d'API"

KEY=""
for _ in $(seq 1 30); do
  KEY="$(docker exec vexa-lite sh -c 'cat /run/vexa/key.env 2>/dev/null' 2>/dev/null \
         | sed -n 's/^VEXA_API_KEY=//p' | tr -d '\r' | head -1 || true)"
  [ -n "$KEY" ] && break
  sleep 4
done

if [ -z "$KEY" ]; then
  bad "cle non recuperee automatiquement."
  echo "       Recupere-la a la main puis colle-la dans $HERE/.env :"
  echo "         docker exec vexa-lite cat /run/vexa/key.env"
  exit 1
fi
ok "cle recuperee (${KEY:0:10}...)"

ENVF="$HERE/.env"
TMPF="$(mktemp)"
# on preserve les reglages deja ecrits (webhook, langue...) et on remplace la cle
if [ -f "$ENVF" ]; then
  grep -v -E '^(VEXA_API_KEY|VEXA_API_BASE)=' "$ENVF" > "$TMPF" || true
fi
{
  echo "VEXA_API_KEY=$KEY"
  echo "VEXA_API_BASE=$GATEWAY"
} >> "$TMPF"
mv "$TMPF" "$ENVF"
chmod 600 "$ENVF"
ok "ecrite dans $ENVF (chmod 600)"

# --- 5. diagnostic ----------------------------------------------------------
say "5/5  Diagnostic"
python3 "$HERE/meet.py" doctor || true

say "Pret."
cat <<EOF
  Interface web : $TERMINAL
  API           : $GATEWAY
  Compte rendus : $HERE/notes/

  Envoyer un bot :
    python3 $HERE/meet.py join https://meet.google.com/abc-defg-hij
    python3 $HERE/meet.py watch
    python3 $HERE/meet.py notes

  Tout arreter (les donnees restent) :
    make -C $VEXA_DIR/deploy/lite down
EOF
