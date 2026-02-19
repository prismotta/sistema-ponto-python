import sqlite3
import psycopg2
from urllib.parse import urlparse
from config import DATABASE_URL, DATABASE_PATH


def conectar():
    if DATABASE_URL:
        result = urlparse(DATABASE_URL)
        return psycopg2.connect(
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
        )
    return sqlite3.connect(DATABASE_PATH)
