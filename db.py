import psycopg2
import psycopg2.extras
from config import Config

def get_db():
    conn = psycopg2.connect(Config.DATABASE_URL)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn
