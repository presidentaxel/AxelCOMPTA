#!/usr/bin/env bash
# Reçoit le code déjà copié dans ce dépôt et relance la production.
# Les migrations passent avant le remplacement des conteneurs : si elles
# échouent, l'API déjà en service n'est pas arrêtée.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Il manque le fichier .env à côté de docker-compose.prod.yml." >&2
  echo "Le déposer avant le premier déploiement (voir .env.example, section Déploiement)." >&2
  exit 1
fi

docker compose -f docker-compose.prod.yml build
docker compose --profile migration -f docker-compose.prod.yml run --rm --no-deps migrate
docker compose -f docker-compose.prod.yml up -d --force-recreate --remove-orphans --wait --wait-timeout 300
docker image prune -f
