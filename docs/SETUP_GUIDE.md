# Complete Setup Guide

This guide walks you through setting up the LLM Gateway from scratch, including local development and production deployment.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Supabase PostgreSQL Setup](#supabase-postgresql-setup)
4. [API Keys Setup](#api-keys-setup)
5. [Database Initialization](#database-initialization)
6. [Running the Application](#running-the-application)
7. [Testing](#testing)
8. [Production Deployment (GCP)](#production-deployment-gcp)

---

## Prerequisites

### Required Software

1. **Python 3.11+**
   ```bash
   python3 --version  # Should be 3.11 or higher
   ```

2. **pip** (Python package manager)
   ```bash
   pip3 --version
   ```

3. **Docker & Docker Compose** (for local development)
   ```bash
   docker --version
   docker-compose --version
   ```

4. **Git** (to clone the repository)
   ```bash
   git --version
   ```

### Required Accounts & API Keys

You'll need accounts and API keys from:

1. **Supabase** (for PostgreSQL database)
2. **OpenAI** (for GPT models)
3. **DeepSeek** (for cost-effective models)
4. **HuggingFace** (for open-source models: Llama-3, Mixtral, Qwen)

---

## Local Development Setup

### Step 1: Clone and Navigate to Project

```bash
cd /Users/niraj/llm-production
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
# .venv\Scripts\activate
```

**Verify activation:**
- Your terminal prompt should show `(.venv)` at the start
- `which python` should point to `.venv/bin/python`

### Step 3: Install Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt
```

**Verify installation:**
```bash
pip list | grep fastapi
pip list | grep sqlalchemy
```

---

## Supabase PostgreSQL Setup

### Step 1: Create Supabase Account

1. Go to [https://supabase.com](https://supabase.com)
2. Sign up / Sign in
3. Click "New Project"

### Step 2: Create a New Project

1. **Project Name**: `llm-gateway` 
2. **Database Password**: Create a strong password (save it securely!)
3. **Region**: Choose closest to you
4. Click "Create new project"
5. Wait 2-3 minutes for setup to complete

### Step 3: Get Database Connection String

1. In Supabase dashboard, go to **Settings** → **Database**
2. Scroll to **Connection string** section
3. Copy the **URI** connection string
4. It looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```

**Important**: Replace `[YOUR-PASSWORD]` with the password you set during project creation!

### Step 4: Update Environment Variables

Create a `.env` file in the project root:

```bash
# Create .env file
touch .env
```

Add the following content (replace with your actual values):

```bash
# Supabase PostgreSQL Database
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres

# Provider API Keys
OPENAI_API_KEY=sk-your-openai-api-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key-here
HUGGINGFACE_API_KEY=hf_your-huggingface-api-key-here

# Security: code to generate -> openssl rand -base64 24
SECRET_KEY=generate-a-random-string-here-min-32-characters

# Logging
LOG_LEVEL=INFO
ENVIRONMENT=dev

# Provider timeout (seconds)
PROVIDER_TIMEOUT=30
```

**Generate SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## API Keys Setup

### OpenAI API Key

1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Sign in / Sign up
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)
5. Add to `.env` file as `OPENAI_API_KEY`

### DeepSeek API Key

1. Go to [https://platform.deepseek.com](https://platform.deepseek.com)
2. Sign in / Sign up
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key
6. Add to `.env` file as `DEEPSEEK_API_KEY`

### HuggingFace API Key

1. Go to [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Sign in / Sign up
3. Click "New token"
4. Name it (e.g., "llm-gateway")
5. Select "Read" permissions (for Inference API)
6. Copy the token (starts with `hf_`)
7. Add to `.env` file as `HUGGINGFACE_API_KEY`

**Note**: HuggingFace Inference API is free, but you need an account and token.

---

## Database Initialization

### Step 1: Test Database Connection

```bash
# With virtual environment activated
python scripts/init_db.py
```

This should create all database tables. If you see errors, check:
- Database URL is correct in `.env`
- Password is correct
- Network connection is working

### Step 2: Run Alembic Migrations (Alternative)

```bash
# Create initial migration (first time only)
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### Step 3: Create Your First API Key

```bash
# Create an API key for testing
python scripts/create_api_key.py "test-key" "my-secret-api-key-12345" 60
```

**Save the plain key** - you'll need it to make API requests!

**Example output:**
```
API key 'test-key' created successfully!
Key ID: 123e4567-e89b-12d3-a456-426614174000
Plain key (save this securely): my-secret-api-key-12345
Rate limit: 60 requests/minute
```

---

## Running the Application

### Option 1: Run Locally (Development)

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health
- **Metrics**: http://localhost:8000/metrics

### Option 2: Run with Docker Compose

```bash
# Start services (database + app)
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

**Note**: For Docker, update `docker-compose.yml` to use your Supabase DATABASE_URL or use `.env` file.

---

## Testing

### Step 1: Run Unit Tests

```bash
# With virtual environment activated
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_routing.py
```

### Step 2: Test API Endpoint

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test chat completion (replace YOUR_API_KEY with the key you created)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ]
  }'
```

### Step 3: Check Metrics

```bash
curl http://localhost:8000/metrics
```

---

## Production Deployment (GCP)

### Prerequisites for GCP

1. **Google Cloud Account**: [https://cloud.google.com](https://cloud.google.com)
2. **gcloud CLI**: Install from [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)
3. **Docker** (for building images)

### Step 1: Set Up GCP Project

```bash
# Login to GCP
gcloud auth login

# Create a new project (or use existing)
gcloud projects create llm-gateway-prod --name="LLM Gateway Production"

# Set as default project
gcloud config set project llm-gateway-prod

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### Step 2: Build and Push Docker Image

```bash
# Set project ID (replace with your project ID)
export PROJECT_ID=$(gcloud config get-value project)

# Configure Docker to use gcloud
gcloud auth configure-docker

# Build Docker image
docker build -t gcr.io/${PROJECT_ID}/llm-gateway:latest .

# Push to Google Container Registry
docker push gcr.io/${PROJECT_ID}/llm-gateway:latest
```

### Step 3: Deploy to Cloud Run

```bash
# Deploy to Cloud Run
gcloud run deploy llm-gateway \
  --image gcr.io/${PROJECT_ID}/llm-gateway:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "DATABASE_URL=your-supabase-connection-string" \
  --set-env-vars "OPENAI_API_KEY=your-openai-key" \
  --set-env-vars "DEEPSEEK_API_KEY=your-deepseek-key" \
  --set-env-vars "HUGGINGFACE_API_KEY=your-hf-key" \
  --set-env-vars "SECRET_KEY=your-secret-key" \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10
```

**Better Approach: Use Secret Manager**

```bash
# Create secrets
echo -n "your-database-url" | gcloud secrets create database-url --data-file=-
echo -n "your-openai-key" | gcloud secrets create openai-api-key --data-file=-
echo -n "your-deepseek-key" | gcloud secrets create deepseek-api-key --data-file=-
echo -n "your-hf-key" | gcloud secrets create huggingface-api-key --data-file=-
echo -n "your-secret-key" | gcloud secrets create secret-key --data-file=-

# Deploy with secrets
gcloud run deploy llm-gateway \
  --image gcr.io/${PROJECT_ID}/llm-gateway:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --update-secrets DATABASE_URL=database-url:latest,OPENAI_API_KEY=openai-api-key:latest,DEEPSEEK_API_KEY=deepseek-api-key:latest,HUGGINGFACE_API_KEY=huggingface-api-key:latest,SECRET_KEY=secret-key:latest \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10
```

### Step 4: Run Database Migrations

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe llm-gateway --region us-central1 --format 'value(status.url)')

# Run migrations (you'll need to connect to Cloud Run instance)
# Option 1: Run locally pointing to production database
DATABASE_URL="your-supabase-url" alembic upgrade head

# Option 2: Use Cloud SQL Proxy or run migration script
```

### Step 5: Verify Deployment

```bash
# Get service URL
gcloud run services describe llm-gateway --region us-central1 --format 'value(status.url)'

# Test health endpoint
curl https://YOUR-SERVICE-URL/health

# Test metrics
curl https://YOUR-SERVICE-URL/metrics
```

---

## Troubleshooting

### Database Connection Issues

**Error**: `could not connect to server`

**Solutions**:
1. Check Supabase database URL is correct
2. Verify password is correct (no special characters need URL encoding)
3. Check Supabase project is active (not paused)
4. Ensure network can reach Supabase (firewall rules)

**Test connection:**
```bash
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"
```

### API Key Authentication Issues

**Error**: `Invalid or missing API key`

**Solutions**:
1. Verify API key exists in database:
   ```bash
   # Connect to database and check
   SELECT name, is_active FROM api_keys;
   ```
2. Ensure you're using the plain key (not the hash)
3. Check Authorization header format: `Bearer YOUR_KEY`

### Provider API Errors

**Error**: `Provider API error: 401`

**Solutions**:
1. Check API keys in `.env` file are correct
2. Verify API keys are active in provider dashboard
3. Check API key has correct permissions

### Migration Issues

**Error**: `Target database is not up to date`

**Solutions**:
```bash
# Check current revision
alembic current

# Show migration history
alembic history

# Upgrade to latest
alembic upgrade head
```

---

## Quick Reference

### Environment Variables Summary

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DATABASE_URL` | Yes | Supabase PostgreSQL connection string | `postgresql://postgres:pass@db.xxx.supabase.co:5432/postgres` |
| `OPENAI_API_KEY` | Yes | OpenAI API key | `sk-...` |
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key | `...` |
| `HUGGINGFACE_API_KEY` | Yes | HuggingFace API token | `hf_...` |
| `SECRET_KEY` | Yes | Secret for hashing (min 32 chars) | Random string |
| `LOG_LEVEL` | No | Logging level (default: INFO) | `INFO`, `DEBUG` |
| `ENVIRONMENT` | No | Environment name (default: dev) | `dev`, `prod` |
| `PROVIDER_TIMEOUT` | No | Provider timeout in seconds (default: 30) | `30` |

### Common Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run application
uvicorn app.main:app --reload

# Run tests
pytest

# Create API key
python scripts/create_api_key.py "key-name" "plain-key" 60

# Initialize database
python scripts/init_db.py

# Run migrations
alembic upgrade head

# View logs (Docker)
docker-compose logs -f app
```

---

## Next Steps

1. ✅ Set up all API keys
2. ✅ Initialize database
3. ✅ Create your first API key
4. ✅ Test the API endpoints
5. ✅ Review routing rules and customize if needed
6. ✅ Set up monitoring (Prometheus metrics)
7. ✅ Deploy to production (GCP Cloud Run)
8. ✅ Configure custom domain (optional)

---

## Support

For issues or questions:
- Check the [README.md](README.md) for API documentation
- Review logs: `docker-compose logs -f app`
- Check metrics: `curl http://localhost:8000/metrics`

