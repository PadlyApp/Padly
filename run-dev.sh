#!/bin/bash

# Padly Development Server Launcher
# Runs both frontend (Next.js) and backend (FastAPI) in one terminal

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Padly Development Server Launcher${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if backend virtual environment exists
if [ ! -d "$PROJECT_ROOT/backend/venv" ]; then
  echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
  cd "$PROJECT_ROOT/backend"
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  cd "$PROJECT_ROOT"
else
  source "$PROJECT_ROOT/backend/venv/bin/activate"
fi

# Check if frontend node_modules exists
if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
  echo -e "${YELLOW}Frontend dependencies not found. Installing...${NC}"
  cd "$PROJECT_ROOT/frontend"
  npm install
  cd "$PROJECT_ROOT"
fi

echo -e "${GREEN}Starting Padly services...${NC}\n"

# Function to handle cleanup on exit
cleanup() {
  echo -e "\n${RED}Shutting down services...${NC}"
  jobs -p | xargs -r kill 2>/dev/null || true
  exit 0
}

# Set trap to catch SIGINT (Ctrl+C)
trap cleanup SIGINT

# Start backend in background
echo -e "${BLUE}[BACKEND]${NC} Starting FastAPI server on http://localhost:8000..."
cd "$PROJECT_ROOT/backend"
uvicorn app.main:app --reload &
BACKEND_PID=$!

# Give backend a moment to start
sleep 2

# Start frontend in background
echo -e "${BLUE}[FRONTEND]${NC} Starting Next.js dev server on http://localhost:3000..."
cd "$PROJECT_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

# Wait for both processes
echo -e "\n${GREEN}Both services are running!${NC}"
echo -e "${YELLOW}Backend:${NC}  http://localhost:8000"
echo -e "${YELLOW}Frontend:${NC} http://localhost:3000"
echo -e "${YELLOW}API Docs:${NC} http://localhost:8000/docs\n"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}\n"

wait

cleanup
