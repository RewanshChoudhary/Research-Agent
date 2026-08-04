#!/usr/bin/env bash
#
# run-local.sh — Run Research-Agent WITHOUT rebuilding Docker images.
#
# Strategy:
#   - Infra (postgres, redis, weaviate) runs via `docker compose up` using the
#     official PREBUILT images (no `build:` => no image rebuild). Their ports are
#     published to localhost.
#   - The Spring Boot API runs locally with ./mvnw (Java 25).
#   - The Python worker runs locally with `uv run`.
#   - The frontend is served by a tiny zero-dependency Node server that proxies
#     /api -> the local API.
#
# Usage:
#   ./run-local.sh            # start everything
#   ./run-local.sh stop       # stop infra + local processes
#   ./run-local.sh infra-only # only bring up postgres/redis/weaviate
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Load .env (best-effort)
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# ---- Ports published to the host ----
DB_PORT="${DB_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
WEAVIATE_HTTP_PORT="${WEAVIATE_HTTP_PORT:-8081}"
WEAVIATE_GRPC_PORT="${WEAVIATE_GRPC_PORT:-50051}"
API_PORT="${API_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# ---- Build / process tracking ----
PID_FILE="$ROOT/.run-local.pids"
INFRA_COMPOSE=(docker compose up -d postgres redis weaviate)

cleanup() {
  echo
  echo "==> Shutting down local processes..."
  if [[ -f "$PID_FILE" ]]; then
    # kill tracked children, ignore errors
    xargs -r kill 2>/dev/null < "$PID_FILE" || true
    rm -f "$PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

stop_all() {
  echo "==> Stopping infra containers..."
  docker compose stop postgres redis weaviate 2>/dev/null || true
  cleanup
  echo "Done."
  exit 0
}

wait_for() {
  local desc="$1" cmd="$2" tries="${3:-60}" wait="${4:-2}"
  echo -n "==> Waiting for $desc"
  for ((i=0; i<tries; i++)); do
    if eval "$cmd" >/dev/null 2>&1; then
      echo " ready."
      return 0
    fi
    echo -n "."
    sleep "$wait"
  done
  echo " TIMEOUT."
  return 1
}

start_infra() {
  echo "==> Starting infra (postgres, redis, weaviate) via Docker prebuilt images..."
  "${INFRA_COMPOSE[@]}"
  wait_for "postgres" "pg_isready -h localhost -p $DB_PORT -U ${DB_USERNAME:-researchagent} -d ${DB_NAME:-researchagent} 2>/dev/null || docker exec research-agent-postgres pg_isready -U ${DB_USERNAME:-researchagent} >/dev/null 2>&1" 60 2 || \
    wait_for "postgres(container)" "docker exec research-agent-postgres pg_isready -U ${DB_USERNAME:-researchagent} >/dev/null 2>&1" 60 2
  wait_for "redis" "redis-cli -h localhost -p $REDIS_PORT ping 2>/dev/null | grep -q PONG || docker exec research-agent-redis redis-cli ping 2>/dev/null | grep -q PONG" 30 2
  wait_for "weaviate" "curl -fsS http://localhost:$WEAVIATE_HTTP_PORT/v1/.well-known/ready >/dev/null 2>&1" 40 3
}

start_api() {
  echo "==> Starting Spring Boot API on :$API_PORT (./mvnw)..."
  (
    cd "$ROOT/AIproject"
    DB_HOST=localhost DB_PORT="$DB_PORT" \
    DB_NAME="${DB_NAME:-researchagent}" DB_USERNAME="${DB_USERNAME:-researchagent}" DB_PASSWORD="${DB_PASSWORD:-researchagent}" \
    REDIS_HOST=localhost REDIS_PORT="$REDIS_PORT" \
    REDIS_JOB_STREAM="${REDIS_JOB_STREAM:-research:jobs:stream}" \
    REDIS_JOB_GROUP="${REDIS_JOB_GROUP:-research:workers}" \
    REDIS_DEAD_STREAM="${REDIS_DEAD_STREAM:-research:jobs:dead}" \
    WORKER_TOKEN="${WORKER_TOKEN:-dev-worker-secret}" \
    ./mvnw -q spring-boot:run
  ) &
  echo $! >> "$PID_FILE"
  wait_for "api (:${API_PORT})" "curl -fsS http://localhost:$API_PORT/actuator/health >/dev/null 2>&1" 90 3 || \
    wait_for "api (:${API_PORT})" "curl -fsS http://localhost:$API_PORT/ >/dev/null 2>&1" 30 3
}

start_worker() {
  echo "==> Starting Python worker (uv run)..."
  (
    cd "$ROOT/AIProject-Worker"
    REDIS_URL="redis://localhost:$REDIS_PORT/0" \
    REDIS_JOB_STREAM="${REDIS_JOB_STREAM:-research:jobs:stream}" \
    REDIS_JOB_GROUP="${REDIS_JOB_GROUP:-research:workers}" \
    REDIS_CONSUMER_NAME="${REDIS_CONSUMER_NAME:-worker-1}" \
    JAVA_SERVER_URL="http://localhost:$API_PORT" \
    WORKER_TOKEN="${WORKER_TOKEN:-dev-worker-secret}" \
    GROQ_API_KEY="${GROQ_API_KEY:-}" LLM_API_KEY="${LLM_API_KEY:-${GROQ_API_KEY:-}}" \
    LLM_BASE_URL="${LLM_BASE_URL:-https://api.groq.com/openai/v1}" \
    LLM_MODEL="${LLM_MODEL:-llama3-groq-8b-8192-tool-use-preview}" \
    WEAVIATE_URL="http://localhost:$WEAVIATE_HTTP_PORT" \
    WEAVIATE_GRPC_PORT="$WEAVIATE_GRPC_PORT" \
    uv run python main.py
  ) &
  echo $! >> "$PID_FILE"
}

start_frontend() {
  echo "==> Starting frontend dev server on :$FRONTEND_PORT..."
  (
    cd "$ROOT/frontend"
    API_TARGET="http://localhost:$API_PORT" FRONTEND_PORT="$FRONTEND_PORT" \
    node serve.js "$FRONTEND_PORT"
  ) &
  echo $! >> "$PID_FILE"
}

# ---- Main ----
case "${1:-}" in
  stop)
    stop_all
    ;;
  infra-only)
    start_infra
    echo "Infra up. Exiting (not running app processes)."
    exit 0
    ;;
  "")
    : # fall through to full start
    ;;
  *)
    echo "Unknown argument: $1" >&2
    echo "Usage: $0 [start|stop|infra-only]" >&2
    exit 1
    ;;
esac

: > "$PID_FILE"
start_infra
start_api
start_worker
start_frontend

echo
echo "============================================================"
echo " Research-Agent is running (locally, no image rebuild):"
echo "   Frontend : http://localhost:$FRONTEND_PORT"
echo "   API      : http://localhost:$API_PORT"
echo "   Worker   : local (uv)"
echo "   Postgres : localhost:$DB_PORT"
echo "   Redis    : localhost:$REDIS_PORT"
echo "   Weaviate : localhost:$WEAVIATE_HTTP_PORT (http) / $WEAVIATE_GRPC_PORT (grpc)"
echo " Press Ctrl-C to stop everything."
echo "============================================================"

# Wait for children
wait
