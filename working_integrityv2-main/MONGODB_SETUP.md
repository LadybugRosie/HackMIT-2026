# 🗄️ MongoDB Setup Guide for Editorrah Integrity System

## 📋 Overview

The Editorrah integrity system uses MongoDB to store:
- Session data
- Paste history
- Event chains
- Analysis history

---

## 🎯 Option 1: MongoDB Atlas (Cloud - RECOMMENDED) ⭐

**Best for:** Production deployment, no server management needed

### Step 1: Create MongoDB Atlas Account
1. Go to [https://www.mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
2. Click **"Try Free"** or **"Sign Up"**
3. Create your account (free tier available)

### Step 2: Create a Cluster
1. After login, click **"Build a Database"**
2. Choose **FREE** tier (M0 Sandbox)
3. Select **Cloud Provider** (AWS recommended)
4. Choose **Region** closest to your users
5. Click **"Create"** (takes 3-5 minutes)

### Step 3: Create Database User
1. Go to **"Database Access"** (left sidebar)
2. Click **"Add New Database User"**
3. Choose **"Password"** authentication
4. Enter username: `editorrah_admin`
5. Generate secure password (click 🔑 icon) or create your own
6. **SAVE THIS PASSWORD** - you'll need it!
7. Set privileges: **"Atlas Admin"** (or "Read and write to any database")
8. Click **"Add User"**

### Step 4: Configure Network Access
1. Go to **"Network Access"** (left sidebar)
2. Click **"Add IP Address"**
3. For development: Click **"Allow Access from Anywhere"** (0.0.0.0/0)
4. For production: Add your server IP addresses only
5. Click **"Confirm"**

### Step 5: Get Connection String
1. Go to **"Database"** (left sidebar)
2. Click **"Connect"** on your cluster
3. Choose **"Connect your application"**
4. Copy the connection string (looks like):
   ```
   mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
5. Replace `<username>` with your database user
6. Replace `<password>` with your database password
7. Add database name at the end:
   ```
   mongodb+srv://editorrah_admin:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/editorrah_integrity?retryWrites=true&w=majority
   ```

### Step 6: Add to Environment Variables
Add to `integrity-backend/.env`:
```bash
MONGO_URI=mongodb+srv://editorrah_admin:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/editorrah_integrity?retryWrites=true&w=majority
DB_NAME=editorrah_integrity
```

**✅ Done!** Your MongoDB Atlas is ready!

---

## 🖥️ Option 2: Local MongoDB (Development)

**Best for:** Local development, testing

### macOS (using Homebrew)
```bash
# Install MongoDB
brew tap mongodb/brew
brew install mongodb-community@7.0

# Start MongoDB
brew services start mongodb-community@7.0

# Verify it's running
mongosh
```

### Linux (Ubuntu/Debian)
```bash
# Import MongoDB public GPG key
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install MongoDB
sudo apt-get update
sudo apt-get install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod
```

### Windows
1. Download MongoDB from [https://www.mongodb.com/try/download/community](https://www.mongodb.com/try/download/community)
2. Run installer
3. Choose "Complete" installation
4. Install MongoDB as a Windows Service
5. MongoDB will start automatically

### Configure for Local Development
Add to `integrity-backend/.env`:
```bash
MONGO_URI=mongodb://localhost:27017
DB_NAME=editorrah_integrity
```

**✅ Done!** Local MongoDB is ready!

---

## 🐳 Option 3: Docker MongoDB (Recommended for Docker Deployments)

**Best for:** Docker Compose deployments

### Using Docker Compose (Already Included!)
The `docker-compose.yml` already includes MongoDB. Just:

1. Set environment variables in `.env`:
```bash
MONGO_USERNAME=admin
MONGO_PASSWORD=your_secure_password_here
DB_NAME=editorrah_integrity
```

2. Start services:
```bash
docker-compose up -d
```

3. MongoDB will be available at:
```bash
MONGO_URI=mongodb://admin:your_secure_password_here@mongo:27017/editorrah_integrity?authSource=admin
```

**✅ Done!** Docker MongoDB is ready!

---

## 🔐 Option 4: Managed MongoDB Services

### Railway.app
1. Go to Railway dashboard
2. Click **"New"** → **"Database"** → **"Add MongoDB"**
3. Railway provides connection string automatically
4. Copy to your environment variables

### DigitalOcean Managed MongoDB
1. Go to DigitalOcean dashboard
2. Create → Databases → MongoDB
3. Choose plan
4. Get connection string from database settings

### AWS DocumentDB
1. AWS Console → DocumentDB
2. Create cluster
3. Get connection string
4. Configure security groups

---

## ✅ Verify MongoDB Connection

### Test Connection (Python)
```python
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def test_connection():
    uri = "YOUR_MONGO_URI_HERE"
    client = AsyncIOMotorClient(uri)
    try:
        # Test connection
        await client.admin.command('ping')
        print("✅ MongoDB connection successful!")
        
        # List databases
        db_list = await client.list_database_names()
        print(f"📊 Databases: {db_list}")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        client.close()

asyncio.run(test_connection())
```

### Test Connection (MongoDB Shell)
```bash
# Connect
mongosh "YOUR_MONGO_URI_HERE"

# Or for local
mongosh

# Test
db.runCommand({ ping: 1 })

# Should return: { ok: 1 }
```

---

## 🔧 Create Required Indexes

After connecting, create indexes for better performance:

```javascript
// Connect to MongoDB
use editorrah_integrity

// Create indexes
db.sessions.createIndex({ "session_id": 1 }, { unique: true })
db.sessions.createIndex({ "created_at": 1 })
db.events.createIndex({ "session_id": 1, "timestamp": 1 })
db.events.createIndex({ "timestamp": 1 })
db.analysis_history.createIndex({ "session_id": 1, "timestamp": -1 })
```

---

## 🚨 Security Checklist

- [ ] Database user has strong password
- [ ] Network access restricted (production)
- [ ] Connection string uses SSL/TLS
- [ ] Regular backups configured
- [ ] Monitoring enabled
- [ ] Access logs reviewed

---

## 📊 MongoDB Atlas Free Tier Limits

- **Storage:** 512 MB
- **RAM:** Shared
- **Backups:** Manual only
- **Perfect for:** Development and small production deployments

**Upgrade when:** You exceed 512 MB or need automated backups

---

## 🆘 Troubleshooting

### Connection Failed
- ✅ Check username/password
- ✅ Verify network access (IP whitelist)
- ✅ Check connection string format
- ✅ Ensure MongoDB is running (local)

### Authentication Failed
- ✅ Verify username/password
- ✅ Check database user permissions
- ✅ Ensure `authSource` is correct

### Timeout Errors
- ✅ Check network connectivity
- ✅ Verify firewall rules
- ✅ Check MongoDB server status

---

## 📝 Quick Reference

### Connection String Format
```
mongodb://[username:password@]host[:port][/database][?options]
```

### Atlas Connection String Format
```
mongodb+srv://[username:password@]cluster.mongodb.net/[database][?options]
```

### Environment Variables
```bash
MONGO_URI=<connection_string>
DB_NAME=editorrah_integrity
MONGO_USERNAME=admin  # For Docker
MONGO_PASSWORD=secure_password  # For Docker
```

---

## ✅ Next Steps

1. **Choose your MongoDB option** (Atlas recommended)
2. **Set up connection** following steps above
3. **Add to `.env` file** in `integrity-backend/`
4. **Test connection** using test script
5. **Create indexes** for performance
6. **Deploy!** 🚀

---

**Need Help?** Check MongoDB documentation: [https://docs.mongodb.com](https://docs.mongodb.com)

