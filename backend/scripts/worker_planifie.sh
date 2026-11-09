#!/usr/bin/env bash
# Worker de la file de jobs (AXE-845) : exécute les demandes de synchro du
# bouton « Synchroniser » et les dossiers acceptés dans Entreprises.
#
# Chaque minute, à côté des tâches planifiées (taches_planifiees.sh) :
#
#   * * * * * /chemin/vers/AxeLCompta/backend/scripts/worker_planifie.sh
#
# Une passe traite toutes les demandes en attente puis s'arrête. `flock -n` :
# si la passe précédente tourne encore (synchro longue), celle-ci s'efface.
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

cd "$BACKEND"
exec flock -n "$JOURNAUX/.verrou-worker" .venv/bin/python -m axelcompta.worker "$@" \
  >> "$JOURNAUX/worker.log" 2>&1
