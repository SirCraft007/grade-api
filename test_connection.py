#!/usr/bin/env python3
"""Simple script to test database connection and queries"""
import sys
from typing import Union
from config import db, close_db


def to_int(value: Union[None, str, int, float, bytes]) -> int:
    """Safely convert a Value to int."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(float(value)) if value else 0
    if isinstance(value, bytes):
        return int(value.decode()) if value else 0
    return 0


try:
    print("Testing database connection...")
    
    # Test a simple query
    result = db.execute("SELECT COUNT(*) as count FROM users")
    count = result.rows[0]["count"]
    print("✓ Successfully connected to database")
    print(f"✓ Found {count} users in the database")
    
    # Test getting a user if any exist
    if count and to_int(count) > 0:
        result = db.execute("SELECT id, username FROM users LIMIT 1")
        user = result.rows[0]
        print(f"✓ Successfully queried user: {user['username']} (id: {user['id']})")
    
    print("\n✓ All tests passed! Database connection works correctly.")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    close_db()
    sys.exit(1)

# Close the database connection and exit
print("\nClosing database connection...")
close_db()
print("Done!")
sys.exit(0)
