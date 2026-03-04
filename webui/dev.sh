#!/bin/bash
# Start both backend and frontend for development
echo "Starting SEED4D Web UI..."

# Start backend
cd "$(dirname "$0")"
echo "Starting backend on :8000..."
(cd .. && uv run --group webui uvicorn webui.backend.main:app --reload --port 8000) &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend on :5173..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
