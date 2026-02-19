import os
import sys
from libsql_client import create_client_sync
from dotenv import load_dotenv

load_dotenv()

# Regular API keys
VALID_API_KEYS = [
    "65e8a49b49d172573cb8c68cd612a375",
    "adab3f6d8d4d357231cf8009ad5dea15",
]

# Admin API keys
ADMIN_API_KEYS = [
    "893704980be4ab97bfdeb062f4024cf8a7da8570c5627553b535490c48045546",
    "3d9a5cafeba42343dc1605c9004d9091fdc2a72a99c84bca0d4cc8c9ed2a483c",
]

# Turso database connection using HTTP client (works in serverless)
url = os.environ.get("TURSO_DATABASE_URL") or os.environ.get("DB_URL")
auth_token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("DB_AUTH_TOKEN")

# Validate environment variables
if not url:
    print("ERROR: Database URL not found in environment variables.")
    print("Please set TURSO_DATABASE_URL or DB_URL in your .env file")
    sys.exit(1)

if not auth_token:
    print("ERROR: Database auth token not found in environment variables.")
    print("Please set TURSO_AUTH_TOKEN or DB_AUTH_TOKEN in your .env file")
    sys.exit(1)

# Convert libsql:// or wss:// URLs to https:// for HTTP client
if url.startswith("libsql://"):
    url = url.replace("libsql://", "https://")
elif url.startswith("wss://"):
    url = url.replace("wss://", "https://")

# Use synchronous HTTP-based client with error handling
try:
    db = create_client_sync(url=url, auth_token=auth_token)
    print(f"Connected to Turso via HTTP: {url}")
except Exception as e:
    print(f"ERROR: Failed to create database connection: {e}")
    sys.exit(1)


def close_db():
    """Close database connection."""
    try:
        db.close()
    except Exception as e:
        print(f"Warning: Error closing database connection: {e}")
