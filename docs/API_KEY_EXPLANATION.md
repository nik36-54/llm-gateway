# API Key System Explained

## Who Creates API Keys?

**You (the admin/system operator)** create API keys, **NOT** the end users/customers.

## How It Works

### 1. Admin Creates API Keys

As the service administrator, you create API keys for your users/customers using the provided script:

```bash
python scripts/create_api_key.py "customer-company-a" "their-secret-api-key-123" 100
```

This creates:
- A named API key (e.g., "customer-company-a")
- The actual key value (e.g., "their-secret-api-key-123")
- Rate limit (e.g., 100 requests/minute)

### 2. Admin Distributes Keys to Customers

You give the API key to your customer:
- Email it securely
- Share via a secure portal
- Provide through your customer dashboard

**Important**: The customer only gets the plain key (e.g., "their-secret-api-key-123"), not the hash stored in the database.

### 3. Customers Use the Key in Requests

Your customers use the API key you gave them:

```bash
curl -X POST http://your-gateway.com/v1/chat/completions \
  -H "Authorization: Bearer their-secret-api-key-123" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

## Typical Workflow

```
┌─────────────┐
│   Admin     │ Creates API key → Stores hash in database
│   (You)     │
└──────┬──────┘
       │
       │ Gives plain key to customer
       │
       ▼
┌─────────────┐
│  Customer   │ Uses key in API requests
│  / User     │
└─────────────┘
```

## Security Model

- **API keys are hashed** using bcrypt before storage
- **Only the hash is stored** in the database (not the plain key)
- **You must save the plain key** when creating it (it's only shown once!)
- **Customers authenticate** by sending the plain key, which gets verified against the hash

## Creating API Keys

### Method 1: Using the Script (Manual Key)

```bash
python scripts/create_api_key.py "customer-name" "their-custom-key" 60
```

**Output:**
```
API key 'customer-name' created successfully!
Key ID: 123e4567-e89b-12d3-a456-426614174000
Plain key (save this securely): their-custom-key
Rate limit: 60 requests/minute
```

**⚠️ Save the plain key immediately** - you won't see it again!

### Method 2: Generate Secure Random Key

```bash
# Generate a secure random key
RANDOM_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Create API key with the random key
python scripts/create_api_key.py "customer-company-b" "$RANDOM_KEY" 100
```

## Example: Complete Setup

```bash
# 1. Generate a secure API key
export CUSTOMER_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Generated key: $CUSTOMER_KEY"

# 2. Create the API key in database
python scripts/create_api_key.py "customer-acme-corp" "$CUSTOMER_KEY" 200

# 3. Share $CUSTOMER_KEY with your customer securely
# (Send via encrypted email, secure portal, etc.)

# 4. Customer uses it in their requests
curl -X POST http://your-gateway.com/v1/chat/completions \
  -H "Authorization: Bearer $CUSTOMER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

## Key Features Per API Key

Each API key you create has:
- **Unique identifier** (UUID)
- **Name** (for your reference, e.g., "customer-company-a")
- **Rate limit** (requests per minute)
- **Active status** (can be disabled)
- **Cost tracking** (all costs linked to that key)

## Best Practices

1. **Use secure random keys** for production (not predictable strings)
2. **Store keys securely** when creating them (you only see them once)
3. **Name keys meaningfully** (customer name, environment, etc.)
4. **Set appropriate rate limits** per customer
5. **Monitor usage** via cost analytics endpoints
6. **Disable keys** by setting `is_active=False` in database if compromised

## Managing API Keys

### List All API Keys (via database query)

```python
from app.cost.database import SessionLocal
from app.cost.models import APIKey

db = SessionLocal()
keys = db.query(APIKey).all()
for key in keys:
    print(f"Name: {key.name}, ID: {key.id}, Active: {key.is_active}, Rate Limit: {key.rate_limit_per_minute}")
```

### Disable an API Key

```python
from app.cost.database import SessionLocal
from app.cost.models import APIKey

db = SessionLocal()
key = db.query(APIKey).filter(APIKey.name == "customer-name").first()
if key:
    key.is_active = False
    db.commit()
    print("API key disabled")
```

## FAQ

**Q: Can customers create their own API keys?**  
A: No, only admins create keys. Customers use keys you provide.

**Q: Can I see the plain key again after creating it?**  
A: No, only the hash is stored. You must save the plain key when creating it.

**Q: What if a customer's key is compromised?**  
A: Disable it in the database (set `is_active=False`) and create a new key.

**Q: Can I change a customer's rate limit?**  
A: Yes, update `rate_limit_per_minute` in the database for that API key.

**Q: How many API keys can I create?**  
A: Unlimited - create as many as you need for different customers/environments.

