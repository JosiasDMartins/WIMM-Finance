# SweetMoney - Example Configuration Files

This directory contains comprehensive example configuration files with detailed explanations and all available options.

## 📁 Files in This Directory

### 1. `.env.example`
**Infrastructure environment variables reference**

- Database credentials (PostgreSQL)
- Redis configuration (channel layer)
- Startup automation settings
- Optional advanced settings (logging, demo mode)

**Use this when:**
- Setting up PostgreSQL or Redis
- Configuring infrastructure-level settings
- Understanding environment variable options

**Note:** Django application settings (SECRET_KEY, DEBUG, ALLOWED_HOSTS, EMAIL) are configured in `local_settings.py`, not `.env`

### 2. `docker-compose.yml.example`
**Comprehensive Docker Compose configuration**

- Production-ready setup with security best practices
- Optional services (Redis, Nginx reverse proxy)
- Resource limits and health checks
- Advanced networking and volume options

**Use this when:**
- Deploying to production
- Setting up HTTPS with Nginx
- Scaling with Redis
- Configuring resource limits

### 3. `local_settings.py.example`
**Full Django settings reference**

- All configuration sections with detailed explanations
- Multiple database backends (SQLite, PostgreSQL, MySQL)
- Email providers (Gmail, Office365, custom SMTP)
- Caching strategies (Redis, Memcached, file-based)
- Security settings (CSP, HTTPS, session management)
- WebSocket and real-time configuration

**Use this when:**
- You need to understand all configuration options
- Setting up advanced features
- Migrating from SQLite to PostgreSQL
- Configuring email, caching, or logging

---

## 🚀 Quick Start vs. Full Configuration

### For Quick Start (Basic Installation)

See the **Installation Guide** in `DOC/WIKI/Installation Guide.md` for:
- Minimal `docker-compose.yml` (just what you need to start)
- Basic `local_settings.py` (essential settings only)
- Simple `.env` file (optional, for basic customization)

**These minimal configs are:**
- ✅ Optimized for quick setup (~10 minutes)
- ✅ Production-ready with good defaults
- ✅ Easy to understand (no clutter)

### For Full Configuration (Advanced Deployments)

Use the files in THIS directory (`example_files/`) when you need:
- Complete reference of all options
- Advanced features (Redis, PostgreSQL, Nginx)
- Fine-tuning performance and security
- Understanding what each setting does

---

## 📖 How to Use These Files

### Step 1: Choose Your Starting Point

**Option A: Quick Start (Recommended for beginners)**
1. Follow `DOC/WIKI/Installation Guide.md`
2. Use the minimal configurations provided there
3. Refer to files in THIS directory only when needed

**Option B: Advanced Setup (For experienced users)**
1. Copy example files from THIS directory to your deployment location
2. Customize based on your requirements
3. Remove unused sections to keep config clean

### Step 2: Copy and Customize

```bash
# Example: Using the comprehensive docker-compose.yml
cp example_files/docker-compose.yml.example ~/sweetmoney/docker-compose.yml

# Edit to match your environment
nano ~/sweetmoney/docker-compose.yml

# Remove sections you don't need (Redis, Nginx, etc.)
```

### Step 3: Reference Documentation

- **Lines/sections are commented** to explain each option
- **Examples provided** for common configurations
- **Links to external docs** where applicable

---

## 🎯 Configuration Hierarchy

SweetMoney uses a layered configuration approach:

```
Base Settings (settings.py)
    ↓
Environment Variables (.env) - Infrastructure only
    ↓
Local Settings (config/local_settings.py) - Django settings
    ↓
Runtime Overrides (not recommended)
```

**Priority (highest to lowest):**
1. **local_settings.py** - Django settings (SECRET_KEY, DEBUG, ALLOWED_HOSTS, EMAIL, etc.)
2. **.env file** - Infrastructure (PostgreSQL, Redis credentials)
3. **settings.py** - Application defaults (DON'T EDIT)

**What goes where:**
- **.env**: Database passwords, Redis credentials, startup automation
- **local_settings.py**: SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, EMAIL, CSP, HTTPS settings

---

## 📚 Configuration Files Comparison

| File | Location | Purpose | When to Use |
|------|----------|---------|-------------|
| **Minimal docker-compose.yml** | Installation Guide | Quick setup | First installation |
| **example_files/docker-compose.yml.example** | This directory | Full reference | Production, Redis, Nginx |
| **Minimal local_settings.py** | Installation Guide | Basic config | Simple deployments |
| **config/local_settings.py.example** | config/ | Production template | Recommended starting point |
| **example_files/local_settings.py.example** | This directory | Complete reference | Advanced features |
| **example_files/.env.example** | This directory | Environment vars | Container config |

---

## 💡 Best Practices

### 1. Start Simple
- Use minimal configs from Installation Guide
- Add complexity only when needed
- Test each change before adding more

### 2. Security First
- Always change `SECRET_KEY`
- Set `DEBUG = False` in production
- Configure `ALLOWED_HOSTS` properly
- Enable HTTPS in production

### 3. Keep It Clean
- Remove unused configuration sections
- Add comments for custom settings
- Document why you changed defaults

### 4. Version Control
**DO commit to Git:**
- ✅ `docker-compose.yml` (with placeholders for secrets)
- ✅ `config/local_settings.py.example`
- ✅ `.env.example`

**DON'T commit to Git:**
- ❌ `config/local_settings.py` (contains secrets)
- ❌ `.env` (contains secrets)
- ❌ `db/` (database files)

---

## 🔍 Finding the Right Configuration

### "I want to..."

| Goal | File to Check | Section |
|------|---------------|---------|
| Enable HTTPS | Installation Guide | 6.1 HTTPS with Nginx |
| Add CSP security | config/local_settings.py.example | Lines 133-230 |
| Use PostgreSQL | example_files/local_settings.py.example | Lines 95-110 |
| Configure email | Installation Guide | 3.1 Email Configuration |
| Add Redis | example_files/docker-compose.yml.example | Lines 70-95 |
| Tune performance | example_files/.env.example | GUNICORN_WORKERS |
| Set resource limits | example_files/docker-compose.yml.example | Lines 56-64 |
| Configure logging | example_files/local_settings.py.example | Lines 280-320 |
| Set up caching | example_files/local_settings.py.example | Lines 350-385 |

---

## 🆘 Need Help?

1. **Installation Guide** (`DOC/WIKI/Installation Guide.md`)
   - Step-by-step setup instructions
   - Troubleshooting common issues
   - Quick reference commands

2. **Security Documentation** (`DOC/security/`)
   - CSP configuration guide
   - Security best practices
   - XSS protection setup

3. **GitHub Wiki**
   - Community guides
   - Advanced tutorials
   - FAQ

4. **Example Files** (This directory)
   - Full configuration reference
   - All available options
   - Detailed explanations

---

## 📝 File Contents Preview

### `.env.example`
```env
# PostgreSQL Database
POSTGRES_DB=sweetmoney
POSTGRES_USER=sweetmoney
POSTGRES_PASSWORD=change-this-secure-password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis Channel Layer
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=change-this-redis-password

# Startup Automation
AUTO_MIGRATE=true
AUTO_COLLECTSTATIC=true

# Optional: LOG_LEVEL, DEMO_MODE, etc.
```

### `docker-compose.yml.example`
```yaml
services:
  sweetmoney:
    # Basic config
    image: josiasdmartins/sweetmoney:latest-amd64
    ports: ["8000:8000"]
    volumes: [...]

    # Advanced options:
    # - Resource limits
    # - Health checks
    # - Security settings
    # - Logging config

  # Optional services:
  # - Redis (WebSocket scaling)
  # - Nginx (HTTPS reverse proxy)
```

### `local_settings.py.example`
```python
# 13 sections with complete configuration:
# 1. Basic Configuration (SECRET_KEY, DEBUG, ALLOWED_HOSTS)
# 2. Security Settings (CSRF_TRUSTED_ORIGINS, HTTPS cookies)
# 3. Database (SQLite, PostgreSQL, MySQL)
# 4. WebSocket & Real-time (Redis channel layer)
# 5. Content Security Policy (CSP)
# 6. Email Configuration (SMTP, Gmail, Office365)
# 7. Logging
# 8. Caching
# 9. Demo Mode
# 10. Internationalization
# 11. File Uploads
# 12. Session Management
# 13. Custom Settings

# Django settings go here, NOT in .env!
```

---

**Last Updated:** 2025-12-23
**SweetMoney Version:** 1.5.0-beta
