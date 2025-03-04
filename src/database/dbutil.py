import os
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "llm_poc"),
    "user": os.getenv("DB_USER", "dev_user"),
    "password": os.getenv("DB_PASS", "devpassword"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432),
}

class Database:
    def __init__(self):
        self.conn = None
    
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def connect(self):
        if not self.conn:
            self.conn = psycopg2.connect(**DB_CONFIG)
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute_query(self, query, params=None, fetch=False, close_after=True):
        self.connect()
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(query, params or ())
            if fetch:
                result = cursor.fetchall()
                self.conn.commit()
                if close_after:
                    self.close()
                return result
            self.conn.commit()
            if close_after:
                self.close()

    def initialize_db(self):
        create_tables_query = """
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER REFERENCES organizations(id),
            email VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            organization_id INTEGER REFERENCES organizations(id),
            created_by_user INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            file_name VARCHAR(255) NOT NULL,
            project_id INTEGER REFERENCES projects(id),
            source_url VARCHAR(255) NOT NULL,
            source_page INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        self.execute_query(create_tables_query)

# Initialize DB on first run
if __name__ == "__main__":
    db = Database()
    db.initialize_db()
    print("Database initialized successfully.")