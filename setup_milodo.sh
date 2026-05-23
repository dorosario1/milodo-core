#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p \
  "$ROOT_DIR/core" \
  "$ROOT_DIR/patterns/resource_exhaustion/1_incident" \
  "$ROOT_DIR/patterns/resource_exhaustion/1_fix" \
  "$ROOT_DIR/patterns/resource_exhaustion/3_analysis" \
  "$ROOT_DIR/patterns/resource_exhaustion/4_validation" \
  "$ROOT_DIR/patterns/service_health/1_incident" \
  "$ROOT_DIR/patterns/service_health/1_fix" \
  "$ROOT_DIR/patterns/service_health/3_analysis" \
  "$ROOT_DIR/patterns/service_health/4_validation" \
  "$ROOT_DIR/patterns/routing_priority/1_incident" \
  "$ROOT_DIR/patterns/routing_priority/1_fix" \
  "$ROOT_DIR/patterns/routing_priority/3_analysis" \
  "$ROOT_DIR/patterns/routing_priority/4_validation" \
  "$ROOT_DIR/memory" \
  "$ROOT_DIR/logs" \
  "$ROOT_DIR/tests"

touch "$ROOT_DIR/logs/.gitkeep"

python3 "$ROOT_DIR/milodo_cli.py" --healthcheck
