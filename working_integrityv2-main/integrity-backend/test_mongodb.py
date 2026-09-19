#!/usr/bin/env python3
"""
Test MongoDB connection script
Run: python test_mongodb.py
"""

import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_connection():
    """Test MongoDB connection"""
    
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "editorrah_integrity")
    
    print("🔍 Testing MongoDB Connection...")
    print(f"   URI: {mongo_uri.replace(os.getenv('MONGO_PASSWORD', ''), '***')}")
    print(f"   Database: {db_name}")
    print()
    
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Test connection
        print("⏳ Connecting...")
        await client.admin.command('ping')
        print("✅ Connection successful!")
        print()
        
        # List databases
        print("📊 Available databases:")
        db_list = await client.list_database_names()
        for db in db_list:
            print(f"   - {db}")
        print()
        
        # Check if our database exists
        if db_name in db_list:
            print(f"✅ Database '{db_name}' exists")
        else:
            print(f"ℹ️  Database '{db_name}' will be created on first use")
        print()
        
        # Test database operations
        db = client[db_name]
        test_collection = db.test_connection
        
        # Insert test document
        print("🧪 Testing write operation...")
        result = await test_collection.insert_one({
            "test": True,
            "timestamp": "test"
        })
        print(f"✅ Write successful! Document ID: {result.inserted_id}")
        
        # Read test document
        print("🧪 Testing read operation...")
        doc = await test_collection.find_one({"_id": result.inserted_id})
        if doc:
            print("✅ Read successful!")
        
        # Clean up test document
        await test_collection.delete_one({"_id": result.inserted_id})
        print("✅ Cleanup successful!")
        print()
        
        # Check collections
        print("📁 Collections in database:")
        collections = await db.list_collection_names()
        if collections:
            for coll in collections:
                count = await db[coll].count_documents({})
                print(f"   - {coll}: {count} documents")
        else:
            print("   (no collections yet)")
        print()
        
        print("🎉 All tests passed! MongoDB is ready to use.")
        
    except Exception as e:
        print(f"❌ Connection failed!")
        print(f"   Error: {e}")
        print()
        print("🔧 Troubleshooting:")
        print("   1. Check MONGO_URI in .env file")
        print("   2. Verify MongoDB is running")
        print("   3. Check network access (for Atlas)")
        print("   4. Verify username/password")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_connection())

