#!/bin/bash

# Production Deployment Script
set -e

echo "🚀 Starting Editorrah Production Deployment..."

# Check if .env files exist
if [ ! -f ".env.production" ]; then
    echo "❌ .env.production not found!"
    echo "📝 Copying from example..."
    cp .env.production.example .env.production
    echo "⚠️  Please edit .env.production with production values"
    exit 1
fi

if [ ! -f "integrity-backend/.env" ]; then
    echo "❌ integrity-backend/.env not found!"
    echo "📝 Copying from example..."
    cp integrity-backend/env.example integrity-backend/.env
    echo "⚠️  Please edit integrity-backend/.env with production values"
    exit 1
fi

# Check for required environment variables
echo "🔍 Checking environment variables..."
source .env.production
source integrity-backend/.env

if [ -z "$INTEGRITY_SIGNING_KEY" ] || [ "$INTEGRITY_SIGNING_KEY" == "change-this-to-a-secure-random-key-in-production" ]; then
    echo "❌ INTEGRITY_SIGNING_KEY not set or using default!"
    echo "🔑 Generating secure key..."
    NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
    echo "Add this to integrity-backend/.env:"
    echo "INTEGRITY_SIGNING_KEY=$NEW_KEY"
    exit 1
fi

# Build Docker images
echo "🏗️  Building Docker images..."
docker-compose build --no-cache

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Start services
echo "▶️  Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Check health
echo "🏥 Checking health..."
FRONTEND_HEALTH=$(curl -s http://localhost/health || echo "failed")
BACKEND_HEALTH=$(curl -s http://localhost:8080/health || echo "failed")

if [ "$FRONTEND_HEALTH" == "healthy" ]; then
    echo "✅ Frontend is healthy"
else
    echo "❌ Frontend health check failed"
fi

if echo "$BACKEND_HEALTH" | grep -q "healthy"; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend health check failed"
fi

# Show logs
echo "📋 Recent logs:"
docker-compose logs --tail=20

echo ""
echo "✅ Deployment complete!"
echo "📊 View logs: docker-compose logs -f"
echo "🛑 Stop services: docker-compose down"

