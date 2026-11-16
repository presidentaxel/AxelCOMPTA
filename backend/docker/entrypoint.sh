#!/bin/sh
# Root le temps de rendre le dossier du modèle accessible, puis l'utilisateur
# axel. L'API reçoit le rôle soumis au RLS : DATABASE_URL (propriétaire) ne
# sert qu'aux migrations, au worker et aux tâches.
set -eu

mkdir -p /opt/axelcompta/_AUDIT_DONNEES/modeles
chown axel:axel /opt/axelcompta/_AUDIT_DONNEES/modeles

if [ "${1:-}" = "uvicorn" ]; then
  if [ -z "${DATABASE_URL_WEB:-}" ]; then
    echo "DATABASE_URL_WEB manquante : l'API ne démarre pas." >&2
    exit 1
  fi
  export DATABASE_URL="$DATABASE_URL_WEB"
fi

exec gosu axel "$@"
