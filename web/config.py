import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_PATH = os.getenv("DATABASE_PATH", "web/database.db")
TIMEZONE = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
