#!/usr/bin/env python3
"""Utility script to create API keys."""
import sys
import uuid
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.cost.database import SessionLocal, init_db
from app.cost.models import APIKey
from app.auth.api_key import hash_api_key


def create_api_key(name: str, plain_key: str, rate_limit_per_minute: int = 60):
    """Create a new API key."""
    db = SessionLocal()
    try:
        # Check if key already exists (simple check)
        existing = db.query(APIKey).filter(APIKey.name == name).first()
        if existing:
            print(f"API key with name '{name}' already exists!")
            return

        api_key_record = APIKey(
            id=uuid.uuid4(),
            key_hash=hash_api_key(plain_key),
            name=name,
            rate_limit_per_minute=rate_limit_per_minute,
            is_active=True,
        )
        db.add(api_key_record)
        db.commit()
        print(f"API key '{name}' created successfully!")
        print(f"Key ID: {api_key_record.id}")
        print(f"Plain key (save this securely): {plain_key}")
        print(f"Rate limit: {rate_limit_per_minute} requests/minute")
    except Exception as e:
        db.rollback()
        print(f"Error creating API key: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/create_api_key.py <name> <plain_key> [rate_limit]")
        print("Example: python scripts/create_api_key.py 'test-key' 'my-secret-key' 60")
        sys.exit(1)

    name = sys.argv[1]
    plain_key = sys.argv[2]
    rate_limit = int(sys.argv[3]) if len(sys.argv) > 3 else 60

    init_db()
    create_api_key(name, plain_key, rate_limit)

