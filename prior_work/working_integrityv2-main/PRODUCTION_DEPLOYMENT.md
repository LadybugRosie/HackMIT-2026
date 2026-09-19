# 🚀 Editorrah Production Deployment Guide

## 📋 Pre-Deployment Checklist

### 0. **MongoDB Setup** ⭐ FIRST STEP!

**You need to set up MongoDB before deployment!**

See **[MONGODB_SETUP.md](./MONGODB_SETUP.md)** for complete instructions.

**Quick Options:**
- **MongoDB Atlas (Recommended):** Free cloud database - [Setup Guide](./MONGODB_SETUP.md#option-1-mongodb-atlas-cloud--recommended-)
- **Docker MongoDB:** Included in docker-compose.yml
- **Local MongoDB:** For development only

**After setup, test connection:**
```bash
cd integrity-backend
python test_mongodb.py
```

### 1. **Environment Configuration**

#### Frontend (.env)
```bash
VITE_INTEGRITY_API=https://api.editorrah.com
NODE_ENV=production
```

#### Backend (integrity-backend/.env)
```bash
# Database
MONGO_URI=mongodb://mongo:27017
DB_NAME=editorrah_integrity
MONGO_USERNAME=admin
MONGO_PASSWORD=<SECURE_PASSWORD>

# Security
INTEGRITY_SIGNING_KEY=<GENERATE_SECURE_64_CHAR_KEY>
CORS_ORIGINS=https://editorrah.com,https://www.editorrah.com

# Redis (for rate limiting)
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=<SECURE_PASSWORD>

# Environment
ENVIRONMENT=production
LOG_LEVEL=info
```

### 2. **Generate Secure Signing Key**
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 3. **Database Setup**
- MongoDB with authentication enabled
- Create indexes for performance
- Set up backups

### 4. **SSL/HTTPS**
- Configure SSL certificates (Let's Encrypt recommended)
- Force HTTPS redirects
- Update CORS origins to HTTPS only

---

## 🐳 Docker Deployment

### Quick Start
```bash
# 1. Set environment variables
cp .env.example .env
cp integrity-backend/env.example integrity-backend/.env

# 2. Edit .env files with production values

# 3. Build and start
docker-compose up -d --build

# 4. Check logs
docker-compose logs -f
```

### Production Commands
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart specific service
docker-compose restart backend

# Update and rebuild
docker-compose up -d --build
```

---

## ☁️ Cloud Deployment Options

### Option 1: Railway.app
1. Connect GitHub repository
2. Add services:
   - Frontend (Node.js)
   - Backend (Python)
   - MongoDB (addon)
   - Redis (addon)
3. Set environment variables
4. Deploy

### Option 2: AWS (EC2 + RDS)
1. Launch EC2 instance
2. Install Docker
3. Set up RDS MongoDB
4. Configure security groups
5. Deploy with docker-compose

### Option 3: Google Cloud Run
1. Build container images
2. Push to Container Registry
3. Deploy to Cloud Run
4. Configure Cloud SQL for MongoDB

### Option 4: DigitalOcean App Platform
1. Connect repository
2. Configure build settings
3. Add databases (MongoDB + Redis)
4. Set environment variables
5. Deploy

---

## 🔒 Security Checklist

- [ ] Change all default passwords
- [ ] Generate secure `INTEGRITY_SIGNING_KEY`
- [ ] Enable MongoDB authentication
- [ ] Configure firewall rules
- [ ] Set up SSL certificates
- [ ] Enable rate limiting
- [ ] Configure CORS properly
- [ ] Set up monitoring/alerts
- [ ] Enable database backups
- [ ] Review security headers
- [ ] Disable debug endpoints in production

---

## 📊 Monitoring & Logging

### Health Checks
- Frontend: `https://editorrah.com/health`
- Backend: `https://api.editorrah.com/health`

### Logs
```bash
# Docker logs
docker-compose logs -f backend

# Application logs
tail -f integrity-backend/logs/app.log
```

### Metrics to Monitor
- API response times
- Error rates
- Rate limit hits
- Database connection pool
- Memory usage
- CPU usage

---

## 🔄 Database Persistence

### MongoDB Indexes
```javascript
// Connect to MongoDB
use editorrah_integrity

// Create indexes
db.sessions.createIndex({ "session_id": 1 }, { unique: true })
db.sessions.createIndex({ "created_at": 1 })
db.events.createIndex({ "session_id": 1, "timestamp": 1 })
db.events.createIndex({ "timestamp": 1 })
```

### Backup Strategy
```bash
# Daily backup script
mongodump --uri="mongodb://admin:password@mongo:27017/editorrah_integrity" \
  --out=/backups/$(date +%Y%m%d)
```

---

## 🚨 Troubleshooting

### Backend won't start
- Check MongoDB connection
- Verify environment variables
- Check logs: `docker-compose logs backend`

### Rate limiting too strict
- Adjust limits in `app/middleware/rate_limit.py`
- Check Redis connection

### CORS errors
- Verify CORS_ORIGINS includes your domain
- Check frontend API URL

### Database connection failed
- Verify MONGO_URI
- Check MongoDB is running
- Verify credentials

---

## 📈 Scaling

### Horizontal Scaling
- Use load balancer (nginx/HAProxy)
- Multiple backend instances
- Shared Redis for rate limiting
- MongoDB replica set

### Vertical Scaling
- Increase container resources
- Optimize database queries
- Add caching layer

---

## 🔐 Secrets Management

### Option 1: Environment Variables (Simple)
- Set in deployment platform
- Never commit to git

### Option 2: AWS Secrets Manager
- Store secrets in AWS
- Retrieve at runtime

### Option 3: HashiCorp Vault
- Centralized secrets management
- Dynamic secrets rotation

---

## 📝 Post-Deployment

1. **Test all endpoints**
   ```bash
   curl https://api.editorrah.com/health
   curl https://api.editorrah.com/api/integrity/session/start
   ```

2. **Monitor for 24 hours**
   - Check error rates
   - Monitor performance
   - Watch for security alerts

3. **Set up alerts**
   - Error rate > 5%
   - Response time > 2s
   - Database connection failures
   - Disk space < 20%

---

## 🆘 Support

- Documentation: `/docs` endpoint (dev only)
- Logs: Check docker-compose logs
- Health: `/health` endpoint
- Issues: GitHub repository

---

## ✅ Production Readiness Checklist

- [ ] All environment variables set
- [ ] Secure signing key generated
- [ ] Database configured with auth
- [ ] SSL certificates installed
- [ ] CORS configured correctly
- [ ] Rate limiting enabled
- [ ] Monitoring set up
- [ ] Backups configured
- [ ] Health checks working
- [ ] Logs accessible
- [ ] Error handling tested
- [ ] Performance tested
- [ ] Security headers verified
- [ ] Documentation updated

---

**Ready for Production! 🎉**

