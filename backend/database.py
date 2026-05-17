"""
Database Configuration
======================

Centralizes MongoDB connection for the application.
Connection is resilient  app can start even if DB is temporarily unreachable.
"""

import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ConnectionFailure, OperationFailure
from dotenv import load_dotenv

try:
    import dns.resolver
except ImportError:
    logging.warning(
        "[WARN] 'dnspython' is not installed. "
        "mongodb+srv:// URIs will fail. Run: pip install dnspython"
    )

load_dotenv(override=True)

logger = logging.getLogger("database")

# Prefer the env var name MONGODB_URI but accept legacy MONGO_URI
MONGODB_URI = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/'
# Default DB name aligns with FastAPI app expectations
DB_NAME = os.environ.get('DB_NAME', 'exam_system')


def _create_client():
    """Create MongoDB client with error resilience."""
    try:
        _client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        # Quick connectivity check (non-blocking at import time)
        _client.admin.command('ping')
        logger.info(f"[OK] Connected to MongoDB: {DB_NAME}")
        return _client
    except (ConfigurationError, ConnectionFailure, OperationFailure) as e:
        logger.warning(
            f"[WARN] MongoDB connection failed ({type(e).__name__}: {e}). "
            f"Falling back to localhost. Set MONGODB_URI correctly in .env"
        )
        try:
            _client = MongoClient(
                'mongodb://localhost:27017/',
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            return _client
        except Exception as fallback_err:
            logger.error(f"[ERROR] Localhost MongoDB also failed: {fallback_err}")
            # Return a client anyway  it will fail on actual operations
            return MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=3000)


client = _create_client()
db = client[DB_NAME]

# Export commonly used collections so other modules import them from here
users = db['users']
exams = db['exams']
uploads = db['uploads']

# Backwards-compatible aliases (some modules used submissions/results)
submissions = uploads
results = db['results']