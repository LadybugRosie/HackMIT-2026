#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/factcheck-service"

python -m pip install --upgrade pip
pip install -r requirements.txt
