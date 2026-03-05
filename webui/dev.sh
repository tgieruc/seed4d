#!/bin/bash
# Start both backend and frontend for development
set -e
cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

echo "Starting SEED4D Web UI..."

# ── Docker (CARLA) ──────────────────────────────────────────────────
CONTAINER_NAME="${SEED4D_CONTAINER:-carla}"
DOCKER_IMAGE="${SEED4D_IMAGE:-seed4d}"

if docker inspect --format='{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | grep -q true; then
    echo "Docker: container '$CONTAINER_NAME' already running"
elif docker inspect "$CONTAINER_NAME" &>/dev/null; then
    echo "Docker: starting stopped container '$CONTAINER_NAME'..."
    docker start "$CONTAINER_NAME"
else
    echo "Docker: creating container '$CONTAINER_NAME' (image: $DOCKER_IMAGE)..."
    docker run --name "$CONTAINER_NAME" \
        --gpus all -d \
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
        -v /usr/share/vulkan/icd.d:/usr/share/vulkan/icd.d \
        -v "$PROJECT_ROOT:/seed4d" \
        "$DOCKER_IMAGE" \
        sleep infinity
fi
echo ""

# ── Backend ─────────────────────────────────────────────────────────
echo "Starting backend on :8000..."
(uv run --group webui uvicorn webui.backend.main:app --reload --port 8000) &
BACKEND_PID=$!

# ── Frontend ────────────────────────────────────────────────────────
echo "Starting frontend on :5173..."
(cd webui/frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
