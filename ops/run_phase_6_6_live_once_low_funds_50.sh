#!/usr/bin/env bash
set -euo pipefail

RUNNER_CONTAINER="quant-phase-6-6-live-one-batch-low-funds-50"
BASE="/Users/albertlz/Downloads/private_proj"
HBOT_HOME="${BASE}/hummingbot"
EVENT_LOG="${HBOT_HOME}/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl"
SCRIPT_SOURCE="${HBOT_HOME}/scripts/quant_system_live_one_batch.py"
SCRIPT_CONFIG="${HBOT_HOME}/conf/scripts/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml"
CONFIG_NAME="crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml"
IMAGE="hummingbot/hummingbot:latest"

echo "Phase 6.6 low-funds live runner"
echo "Scope: at most 1 BTC-USDT market buy, batch cap 50 USDT."
echo

if [[ -e "${EVENT_LOG}" ]]; then
  echo "Refusing to start: event log already exists:"
  echo "${EVENT_LOG}"
  echo "Archive or inspect it before another live run."
  exit 1
fi

if [[ ! -f "${SCRIPT_SOURCE}" ]]; then
  echo "Missing live script: ${SCRIPT_SOURCE}"
  exit 1
fi

if [[ ! -f "${SCRIPT_CONFIG}" ]]; then
  echo "Missing live config: ${SCRIPT_CONFIG}"
  exit 1
fi

if docker ps --format '{{.Names}}' | grep -qx "${RUNNER_CONTAINER}"; then
  echo "Refusing to start: runner container is already running: ${RUNNER_CONTAINER}"
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx "${RUNNER_CONTAINER}"; then
  echo "Removing old stopped runner container: ${RUNNER_CONTAINER}"
  docker rm "${RUNNER_CONTAINER}" >/dev/null
fi

read -rsp "Hummingbot password: " HBOT_PASSWORD
echo
if [[ -z "${HBOT_PASSWORD}" ]]; then
  echo "Password is empty; aborting."
  exit 1
fi
export HBOT_PASSWORD
trap 'unset HBOT_PASSWORD' EXIT

if docker ps --format '{{.Names}}' | grep -qx hummingbot; then
  echo "Stopping existing hummingbot container..."
  docker stop hummingbot >/dev/null
fi

echo "Starting one-shot live runner..."
docker run --rm --name "${RUNNER_CONTAINER}" \
  -e HBOT_PASSWORD \
  -v "${HBOT_HOME}/conf:/home/hummingbot/conf" \
  -v "${HBOT_HOME}/conf/connectors:/home/hummingbot/conf/connectors" \
  -v "${HBOT_HOME}/conf/scripts:/home/hummingbot/conf/scripts" \
  -v "${HBOT_HOME}/data:/home/hummingbot/data" \
  -v "${HBOT_HOME}/logs:/home/hummingbot/logs" \
  -v "${HBOT_HOME}/scripts:/home/hummingbot/scripts" \
  "${IMAGE}" \
  /bin/bash -lc 'conda activate hummingbot && ./bin/hummingbot_quickstart.py --headless --config-password "$HBOT_PASSWORD" --v2 '"${CONFIG_NAME}"

echo
echo "Runner exited. Event log:"
echo "${EVENT_LOG}"
