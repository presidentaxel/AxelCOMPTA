#!/usr/bin/env bash
# Première préparation d'un droplet Ubuntu vierge. À lancer en root, une fois.
#
# Avant :
#   - droplet 4 Go de RAM au moins (le modèle de catégorisation tient en
#     mémoire dans l'API et dans le worker), région Francfort ou Amsterdam ;
#   - deux noms DNS vers son adresse : le front et l'API.
# Après :
#   1. copier la clé privée affichée dans le secret GitHub DROPLET_SSH_KEY,
#      puis supprimer /root/axelcompta-ci ;
#   2. DROPLET_HOST (adresse du droplet), DROPLET_USER=deploy,
#      DROPLET_KNOWN_HOSTS (le bloc ssh-keyscan affiché) ;
#   3. déposer /opt/axelcompta/.env (voir .env.example, section Déploiement) ;
#   4. dans Supabase, autoriser https://<front>/auth/lien ;
#   5. pousser la branche prod : le workflow déploie.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Lancer ce script en root, sur le droplet." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi
# shellcheck disable=SC1091
. /etc/os-release
archi="$(dpkg --print-architecture)"
echo "deb [arch=${archi} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin rsync ufw
systemctl enable --now docker

if ! id deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash --groups docker deploy
fi
usermod -aG docker deploy

install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
touch /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

if [[ ! -f /root/axelcompta-ci ]]; then
  ssh-keygen -t ed25519 -f /root/axelcompta-ci -N "" -C "axelcompta-ci"
  cat /root/axelcompta-ci.pub >> /home/deploy/.ssh/authorized_keys
fi

install -d -o deploy -g deploy /opt/axelcompta

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo
if [[ -f /root/axelcompta-ci ]]; then
  echo "Clé privée pour le secret DROPLET_SSH_KEY (puis : shred -u /root/axelcompta-ci) :"
  echo "-----"
  cat /root/axelcompta-ci
  echo "-----"
else
  echo "Pas de /root/axelcompta-ci : la clé a déjà été retirée, ou authorized_keys a été rempli à la main."
fi
echo
ip_publique="$(curl -4 -fsSL https://ifconfig.me || true)"
echo "DROPLET_HOST=${ip_publique}"
echo "DROPLET_USER=deploy"
echo
echo "DROPLET_KNOWN_HOSTS :"
if [[ -n "${ip_publique}" ]]; then
  ssh-keyscan -H "${ip_publique}" || true
fi
echo
echo "Déposer ensuite /opt/axelcompta/.env, propriétaire deploy, mode 600."
