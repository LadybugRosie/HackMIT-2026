#!/bin/bash

# Setup MongoDB connection script
# USAGE: MONGO_URI="your-mongodb-uri" ./setup_mongodb.sh
set -e

# Check if MONGO_URI is provided
if [ -z "$MONGO_URI" ]; then
    echo "❌ Error: MONGO_URI environment variable is required"
    echo ""
    echo "Usage:"
    echo "  MONGO_URI=\"mongodb+srv://user:pass@cluster.mongodb.net/db\" ./setup_mongodb.sh"
    echo ""
    exit 1
fi

DB_NAME="${DB_NAME:-editorrah_integrity}"

echo "🔧 Setting up MongoDB connection..."
echo ""

# Update .env file
if [ -f ".env" ]; then
    echo "📝 Updating .env file..."
    
    # Backup existing .env
    cp .env .env.backup
    echo "✅ Backed up existing .env to .env.backup"
    
    # Update MONGO_URI (use a different delimiter to avoid issues with special chars)
    if grep -q "MONGO_URI=" .env; then
        grep -v "MONGO_URI=" .env > .env.tmp && mv .env.tmp .env
    fi
    echo "MONGO_URI=$MONGO_URI" > .env.tmp
    cat .env >> .env.tmp
    mv .env.tmp .env
    
    # Update DB_NAME
    if grep -q "DB_NAME=" .env; then
        grep -v "DB_NAME=" .env > .env.tmp && mv .env.tmp .env
    fi
    awk '/^MONGO_URI=/ {print; print "DB_NAME='$DB_NAME'"; next} 1' .env > .env.tmp && mv .env.tmp .env
    
    echo "✅ .env file updated"
else
    echo "📝 Creating .env file..."
    cat > .env << EOF
MONGO_URI=$MONGO_URI
DB_NAME=$DB_NAME
CORS_ORIGINS=http://localhost:9000,http://localhost:3000
INTEGRITY_SIGNING_KEY=change-this-to-a-secure-random-key-in-production
EOF
    echo "✅ .env file created"
fi

echo ""
echo "🧪 Testing MongoDB connection..."
echo ""

# Test connection
python3 test_mongodb.py

echo ""
echo "✅ MongoDB setup complete!"
echo "   Database: $DB_NAME"
echo ""

