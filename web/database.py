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
                saida_final TEXT,
                corrigido_manual BOOLEAN NOT NULL DEFAULT FALSE,
                motivo_correcao TEXT,
                corrigido_em TEXT
            )
        """)
        cursor.execute("ALTER TABLE registros ADD COLUMN IF NOT EXISTS corrigido_manual BOOLEAN NOT NULL DEFAULT FALSE")
        cursor.execute("ALTER TABLE registros ADD COLUMN IF NOT EXISTS motivo_correcao TEXT")
        cursor.execute("ALTER TABLE registros ADD COLUMN IF NOT EXISTS corrigido_em TEXT")
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
                corrigido_manual INTEGER NOT NULL DEFAULT 0,
                motivo_correcao TEXT,
                corrigido_em TEXT,
                FOREIGN KEY(user_id) REFERENCES usuarios(id)
            )
        """)
        cursor.execute("PRAGMA table_info(registros)")
        colunas_registros = {row[1] for row in cursor.fetchall()}
        for coluna, tipo in (
            ("corrigido_manual", "INTEGER NOT NULL DEFAULT 0"),
            ("motivo_correcao", "TEXT"),
            ("corrigido_em", "TEXT"),
        ):
            if coluna not in colunas_registros:
                cursor.execute(f"ALTER TABLE registros ADD COLUMN {coluna} {tipo}")

    conn.commit()
    conn.close()
