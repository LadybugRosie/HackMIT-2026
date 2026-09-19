#!/usr/bin/env bash
set -euo pipefail

cd factcheck-service
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
