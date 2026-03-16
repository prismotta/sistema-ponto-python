"""
Camada de persistência da aplicação.

Responsável por:
- Conectar ao banco (SQLite ou PostgreSQL)
- Normalizar placeholders
- Criar estrutura inicial

Essa camada isola completamente a aplicação da tecnologia de banco.
"""

import os
import sqlite3
import psycopg2
from urllib.parse import urlparse
from typing import Any

DATABASE_PATH = os.getenv("DATABASE_PATH", "web/database.db")
DATABASE_URL = os.getenv("DATABASE_URL")

IS_POSTGRES = bool(DATABASE_URL)


def conectar():
    """
    Retorna conexão ativa com banco configurado.

    - Se DATABASE_URL estiver definida → PostgreSQL.
    - Caso contrário → SQLite.
    """
    if IS_POSTGRES:
        result = urlparse(DATABASE_URL)
        return psycopg2.connect(
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
        )

    return sqlite3.connect(DATABASE_PATH)


def sql(query: str) -> str:
    """
    Converte placeholders automaticamente:

    SQLite  -> ?
    Postgres -> %s
    """
    if IS_POSTGRES:
        return query.replace("?", "%s")
    return query


def criar_banco() -> None:
    """
    Cria tabelas caso não existam.
    Compatível com SQLite e PostgreSQL.
    """
    conn = conectar()
    cursor = conn.cursor()

    if IS_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registros (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES usuarios(id),
                data TEXT,
                entrada_manha TEXT,
                saida_almoco TEXT,
                volta_almoco TEXT,
                saida_final TEXT
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                data TEXT,
                entrada_manha TEXT,
                saida_almoco TEXT,
                volta_almoco TEXT,
                saida_final TEXT,
                FOREIGN KEY(user_id) REFERENCES usuarios(id)
            )
        """)

    conn.commit()
    conn.close()
