#!/usr/bin/env bash
# Tâches planifiées (`python -m axelcompta.taches`) : synchro Digifactory puis
# notifications internes, pour tous les portefeuilles.
#
# Même script sur le poste de Louis (démo) et sur le serveur (production) ;
# seul le planificateur change. Ligne crontab, toutes les heures :
#
#   7 * * * * /chemin/vers/AxeLCompta/backend/scripts/taches_planifiees.sh
#
# Variables : le `.env` racine s'il existe, puis `.env.dev` qui l'emporte
# (poste de dev, ENV=dev). Sur le serveur, pas de ces fichiers :
# l'environnement vient du service (EnvironmentFile d'un timer systemd,
# ou variables de l'utilisateur du crontab).
# Journaux : `AXELCOMPTA_JOURNAUX` (par défaut backend/_demo_output/journaux,
# ignoré par git ; /var/log/axelcompta sur un serveur).
set -euo pipefail

BACKEND="$(cd "$(dirname "$0")/.." && pwd)"
RACINE="$(dirname "$BACKEND")"
JOURNAUX="${AXELCOMPTA_JOURNAUX:-$BACKEND/_demo_output/journaux}"
mkdir -p "$JOURNAUX"

if [ -f "$RACINE/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$RACINE/.env"
  set +a
fi
if [ -f "$RACINE/.env.dev" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$RACINE/.env.dev"
  set +a
fi

cd "$BACKEND"
# -n : si le passage précédent tourne encore, celui-ci s'efface au lieu
# d'empiler deux synchros sur les mêmes curseurs.
exec flock -n "$JOURNAUX/.verrou" .venv/bin/python -m axelcompta.taches "$@" \
  >> "$JOURNAUX/taches.log" 2>&1
