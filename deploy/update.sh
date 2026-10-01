#!/bin/sh
# Pull the latest code and redeploy. Run on the server: ./deploy/update.sh
set -e
cd "$(dirname "$0")/.."
git pull
docker compose -f deploy/docker-compose.prod.yml up -d --build
docker image prune -f
