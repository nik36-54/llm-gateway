#!/usr/bin/env python3
"""Generate and create a secure API key automatically."""
import sys
import secrets
import uuid
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.cost.database import SessionLocal, init_db
from app.cost.models import APIKey
from app.auth.api_key import hash_api_key


def create_secure_api_key(name: str, rate_limit_per_minute: int = 60):
    """Create a new API key with a securely generated random key."""
    db = SessionLocal()
    try:
        # Check if key already exists
        existing = db.query(APIKey).filter(APIKey.name == name).first()
        if existing:
            print(f"❌ API key with name '{name}' already exists!")
            return None

        # Generate secure random API key (32 bytes = 43 chars base64)
        plain_key = secrets.token_urlsafe(32)

        api_key_record = APIKey(
            id=uuid.uuid4(),
            key_hash=hash_api_key(plain_key),
            name=name,
            rate_limit_per_minute=rate_limit_per_minute,
            is_active=True,
        )
        db.add(api_key_record)
        db.commit()

        print(f"✅ API key '{name}' created successfully!")
        print(f"\n📋 Key Details:")
        print(f"   Key ID: {api_key_record.id}")
        print(f"   Rate Limit: {rate_limit_per_minute} requests/minute")
        print(f"\n🔑 API Key (SAVE THIS - you won't see it again!):")
        print(f"   {plain_key}")
        print(f"\n💡 Share this key with your customer securely.")
        print(f"   They will use it as: Authorization: Bearer {plain_key}")
        
        return plain_key
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating API key: {e}")
        return None
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_api_key_secure.py <name> [rate_limit]")
        print("Example: python scripts/create_api_key_secure.py 'customer-acme-corp' 100")
        print("\nThis script automatically generates a secure random API key.")
        sys.exit(1)

    name = sys.argv[1]
    rate_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    init_db()
    create_secure_api_key(name, rate_limit)

