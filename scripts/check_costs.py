# scripts/check_costs.py
#!/usr/bin/env python3
"""Query cost records from database."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.cost.database import SessionLocal
from app.cost.models import CostRecord, APIKey
from sqlalchemy import func
from datetime import datetime, timedelta

def show_costs():
    db = SessionLocal()
    try:
        # Get all cost records
        records = db.query(CostRecord).order_by(CostRecord.created_at.desc()).limit(20).all()
        
        print("\n=== Recent Cost Records ===\n")
        total_cost = 0
        for record in records:
            print(f"Request ID: {record.request_id}")
            print(f"  Provider: {record.provider}")
            print(f"  Model: {record.model}")
            print(f"  Tokens: {record.tokens_in} in + {record.tokens_out} out = {record.tokens_in + record.tokens_out} total")
            print(f"  Cost: ${float(record.cost_usd):.6f}")
            print(f"  Latency: {record.latency_ms}ms")
            print(f"  Time: {record.created_at}")
            print()
            total_cost += float(record.cost_usd)
        
        print(f"Total Cost (last 20 requests): ${total_cost:.6f}\n")
        
        # Aggregate by provider
        print("=== Cost by Provider ===\n")
        provider_costs = db.query(
            CostRecord.provider,
            func.sum(CostRecord.cost_usd).label('total_cost'),
            func.count(CostRecord.id).label('request_count')
        ).group_by(CostRecord.provider).all()
        
        for provider, cost, count in provider_costs:
            print(f"{provider}: ${float(cost):.6f} ({count} requests)")
        
        # Aggregate by API key
        print("\n=== Cost by API Key ===\n")
        key_costs = db.query(
            APIKey.name,
            func.sum(CostRecord.cost_usd).label('total_cost'),
            func.count(CostRecord.id).label('request_count')
        ).join(CostRecord, APIKey.id == CostRecord.api_key_id).group_by(APIKey.name).all()
        
        for key_name, cost, count in key_costs:
            print(f"{key_name}: ${float(cost):.6f} ({count} requests)")
            
    finally:
        db.close()

if __name__ == "__main__":
    show_costs()