"""Database context manager for proper connection handling."""
import sys
from contextlib import contextmanager
from config import db, close_db


@contextmanager
def db_connection():
    """
    Context manager for database connections.
    
    Usage:
        with db_connection():
            result = db.execute("SELECT * FROM users")
            # ... do work ...
        # Connection is automatically closed when exiting the context
    """
    try:
        yield db
    finally:
        close_db()


def execute_and_exit(func):
    """
    Decorator for scripts that need to execute database operations and exit cleanly.
    
    Usage:
        @execute_and_exit
        def main():
            result = db.execute("SELECT * FROM users")
            print(result.rows)
        
        if __name__ == "__main__":
            main()
    """
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            close_db()
            sys.exit(0)
            return result
        except Exception as e:
            print(f"Error: {e}")
            close_db()
            sys.exit(1)
    return wrapper
