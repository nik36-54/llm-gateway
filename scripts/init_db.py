#!/usr/bin/env python3
"""Initialize database with tables."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.cost.database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    try:
        init_db()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

