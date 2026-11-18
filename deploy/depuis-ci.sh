#!/usr/bin/env bash
# Copie le dépôt sur le droplet et lance deploy/mettre-a-jour.sh.
# Sans DROPLET_HOST ni DROPLET_SSH_KEY, ne fait rien : la branche prod peut
# exister avant que le serveur soit prêt.
set -euo pipefail

if [[ -z "${DROPLET_HOST:-}" && -z "${DROPLET_SSH_KEY:-}" ]]; then
  echo "DROPLET_HOST et DROPLET_SSH_KEY absents : déploiement ignoré."
  echo "Les poser dans GitHub → Settings → Secrets, après deploy/bootstrap-droplet.sh."
  exit 0
fi

if [[ -z "${DROPLET_HOST:-}" || -z "${DROPLET_SSH_KEY:-}" ]]; then
  echo "DROPLET_HOST et DROPLET_SSH_KEY vont ensemble." >&2
  exit 1
fi

utilisateur="${DROPLET_USER:-deploy}"
port="${DROPLET_PORT:-22}"
dest="${DROPLET_DIR:-/opt/axelcompta}"
racine="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"
cle="${HOME}/.ssh/axelcompta_droplet"
printf '%s\n' "${DROPLET_SSH_KEY}" > "${cle}"
chmod 600 "${cle}"

verification="accept-new"
if [[ -n "${DROPLET_KNOWN_HOSTS:-}" ]]; then
  printf '%s\n' "${DROPLET_KNOWN_HOSTS}" > "${HOME}/.ssh/known_hosts"
  verification="yes"
fi

ssh_opts=(-i "${cle}" -p "${port}" -o IdentitiesOnly=yes -o BatchMode=yes -o "StrictHostKeyChecking=${verification}")
cible="${utilisateur}@${DROPLET_HOST}"
export RSYNC_RSH="ssh -i ${cle} -p ${port} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=${verification}"

rsync -az --delete \
  --exclude .env \
  --exclude .git \
  --exclude frontend/node_modules \
  --exclude frontend/.next \
  --exclude backend/.venv \
  --exclude backend/_demo_output \
  --exclude _AUDIT_DONNEES/modeles \
  --exclude _AUDIT_DONNEES/resultats \
  --exclude _AUDIT_DONNEES/sortie \
  --exclude '_AUDIT_DONNEES/*.csv' \
  --exclude _AUDIT_DONNEES/rapport_audit_dataset.md \
  --exclude _AUDIT_DONNEES/.venv \
  "${racine}/" "${cible}:${dest}/"

script="$(printf '%q' "${dest}/deploy/mettre-a-jour.sh")"
ssh "${ssh_opts[@]}" "${cible}" "bash ${script}"
