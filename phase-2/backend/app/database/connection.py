import os
import sqlite3
from typing import Dict
from app.database.models import init_database

_connections: Dict[str, sqlite3.Connection] = {}

def get_tenant_db_path(tenant_id: str) -> str:
    """Returns the absolute path to the tenant's SQLite database file."""
    # Store database in the tenant's subdirectory to enforce isolation
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "tenants", tenant_id))
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "metadata.db")

def get_tenant_connection(tenant_id: str) -> sqlite3.Connection:
    """
    Returns (and caches) a sqlite3 connection for the specified tenant,
    ensuring that database tables are initialized.
    """
    global _connections
    if tenant_id in _connections:
        try:
            # Check if connection is active
            _connections[tenant_id].execute("SELECT 1")
            return _connections[tenant_id]
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            # Connection was closed, reconnect
            pass

    db_path = get_tenant_db_path(tenant_id)
    
    # Establish connection with foreign keys enabled
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    
    # Run migrations/init schema
    init_database(conn)
    
    _connections[tenant_id] = conn
    return conn

def close_all_connections():
    """Closes all cached tenant connections."""
    global _connections
    for tenant_id, conn in list(_connections.items()):
        try:
            conn.close()
        except Exception:
            pass
    _connections.clear()
