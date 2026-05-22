#!/usr/bin/env bash
# ============================================================
# setup.sh — Run once on a fresh clone before `docker compose up`
# ============================================================
# What this does:
#   1. Installs the NVIDIA Container Toolkit (so Docker can use the GPU)
#   2. Configures Docker to use the nvidia runtime
#   3. Pre-creates data directories with the correct ownership so
#      Grafana (UID 472) and Prometheus (UID 65534 / nobody) can
#      write to their volumes without manual chown.
# ============================================================

set -euo pipefail

# ── 1. NVIDIA Container Toolkit ────────────────────────────────────────────────
echo ">>> Installing NVIDIA Container Toolkit..."

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update -qq
sudo apt-get install -y nvidia-container-toolkit

# ── 2. Configure Docker runtime ────────────────────────────────────────────────
echo ">>> Configuring Docker to use the nvidia runtime..."
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# ── 3. Verify GPU visibility ───────────────────────────────────────────────────
echo ">>> Verifying NVIDIA driver and Docker runtime..."
nvidia-smi

if docker info 2>/dev/null | grep -qi "nvidia"; then
  echo "✓ nvidia runtime is registered in Docker"
else
  echo "✗ nvidia runtime NOT found — check the toolkit install above"
  exit 1
fi

# ── 4. Pre-create data directories with correct ownership ──────────────────────
# These match the `user:` directives in docker-compose.yml so no manual
# chown is needed after cloning.
echo ">>> Creating data directories with correct ownership..."

# Grafana: UID 472 / GID 472
mkdir -p ./data/grafana
sudo chown -R 472:472 ./data/grafana

# Prometheus: UID 65534 (nobody) / GID 65534 (nogroup)
mkdir -p ./data/prometheus
sudo chown -R 65534:65534 ./data/prometheus
sudo chmod -R 755 ./data/prometheus

# Alertmanager: runs as nobody as well
mkdir -p ./data/alertmanager
sudo chown -R 65534:65534 ./data/alertmanager

echo ""
echo "✓ Setup complete. You can now run:  docker compose up -d"
