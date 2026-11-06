#!/usr/bin/env bash
# One-shot setup for a fresh Vultr Cloud Compute instance (Ubuntu 24.04, 2 vCPU / 4 GB+ recommended).
# Installs Docker + gVisor (runsc), builds the three images and starts GlyphSweep on port 80.
#   ssh root@<vm-ip>
#   git clone https://github.com/<you>/glyphsweep && cd glyphsweep
#   cp .env.example .env && nano .env        # paste VULTR_INFERENCE_API_KEY
#   bash deploy/setup_vultr.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

if ! command -v runsc >/dev/null; then
  curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" > /etc/apt/sources.list.d/gvisor.list
  apt-get update && apt-get install -y runsc
  runsc install
  systemctl restart docker
fi
docker info --format '{{json .Runtimes}}' | grep -q runsc && echo "gVisor runtime: OK"

[ -f .env ] || cp .env.example .env
docker compose --profile build build
docker compose up -d control

if command -v ufw >/dev/null; then ufw allow 22/tcp; ufw allow 80/tcp; ufw --force enable; fi
echo "GlyphSweep is up: http://$(curl -s https://api.ipify.org)/"
