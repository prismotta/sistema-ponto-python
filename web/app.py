"""
Sistema de Ponto - Aplicação Web

Aplicação Flask responsável por:

- Autenticação de usuários
- Registro de ponto
- Cálculo de horas trabalhadas
- Persistência híbrida (SQLite local / PostgreSQL produção)

Compatível com:
- Render (PostgreSQL via DATABASE_URL)
- Execução local (SQLite)

O banco é selecionado automaticamente via variável de ambiente.
"""

import os
import sqlite3
from urllib.parse import urlparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Any

import psycopg2
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash


# ==========================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# ==========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_secret_key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE_PATH = os.getenv("DATABASE_PATH", "web/database.db")
DATABASE_URL = os.getenv("DATABASE_URL")
TIMEZONE = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")

IS_POSTGRES = bool(DATABASE_URL)


# ==========================================================
# BANCO DE DADOS
# ==========================================================

def conectar():
    """
    Retorna conexão com banco de dados.

    - Se DATABASE_URL estiver definida → PostgreSQL.
    - Caso contrário → SQLite local.
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
    Converte placeholders automaticamente.

    SQLite usa '?'.
    PostgreSQL usa '%s'.

    Essa função garante compatibilidade entre os dois.
    """
    if IS_POSTGRES:
        return query.replace("?", "%s")
    return query


def criar_banco() -> None:
    """
    Cria as tabelas necessárias caso não existam.
    Não altera estrutura existente.
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


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================

def agora() -> datetime:
    """
    Retorna datetime atual considerando timezone configurado.
    """
    return datetime.now(ZoneInfo(TIMEZONE))


def usuario_logado() -> bool:
    """
    Verifica se existe usuário autenticado na sessão.
    """
    return "user_id" in session


def calcular_total_registro(registro: Tuple[Any, ...]) -> timedelta:
    """
    Calcula o total trabalhado de um registro.

    Recebe tupla retornada do banco.
    Retorna timedelta correspondente ao total do dia.
    """
    entrada, saida_almoco, volta_almoco, saida_final = (
        registro[3],
        registro[4],
        registro[5],
        registro[6],
    )

    total = timedelta()

    if entrada and saida_almoco:
        total += (
            datetime.strptime(saida_almoco, "%H:%M:%S")
            - datetime.strptime(entrada, "%H:%M:%S")
        )

    if volta_almoco and saida_final:
        total += (
            datetime.strptime(saida_final, "%H:%M:%S")
            - datetime.strptime(volta_almoco, "%H:%M:%S")
        )

    return total


# ==========================================================
# ROTAS
# ==========================================================

@app.route("/", methods=["GET", "POST"])
def login():
    """
    Realiza autenticação do usuário.
    """
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("login.html", erro="Preencha todos os campos")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            sql("SELECT * FROM usuarios WHERE username=?"),
            (username,)
        )
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            return redirect("/dashboard")

        return render_template("login.html", erro="Usuário ou senha inválidos")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registra novo usuário.
    """
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("register.html", erro="Preencha todos os campos")

        senha_hash = generate_password_hash(password)

        conn = conectar()
        cursor = conn.cursor()

        try:
            cursor.execute(
                sql("INSERT INTO usuarios (username, password) VALUES (?, ?)"),
                (username, senha_hash)
            )
            conn.commit()
        except Exception:
            conn.close()
            return render_template("register.html", erro="Usuário já existe")

        conn.close()
        return redirect("/")

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    """
    Exibe histórico de registros e totais (dia atual e acumulado).
    """
    if not usuario_logado():
        return redirect("/")

    hoje = agora().strftime("%Y-%m-%d")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        sql("""
            SELECT *
            FROM registros
            WHERE user_id=?
            ORDER BY data DESC, id DESC
        """),
        (session["user_id"],)
    )

    registros_db = cursor.fetchall()
    conn.close()

    registros = []
    total_hoje = timedelta()
    total_acumulado = timedelta()

    for registro in registros_db:
        total_linha = calcular_total_registro(registro)
        total_acumulado += total_linha
        if registro[2] == hoje:
            total_hoje += total_linha

        registros.append({
            "data": registro[2],
            "entrada": registro[3],
            "saida_almoco": registro[4],
            "volta_almoco": registro[5],
            "saida_final": registro[6],
            "total": total_linha
        })

    return render_template(
        "dashboard.html",
        registros=registros,
        total_hoje=total_hoje,
        total_acumulado=total_acumulado,
    )


@app.route("/bater")
def bater():
    """
    Registra próxima etapa do ponto:
    - Entrada
    - Saída almoço
    - Volta almoço
    - Saída final
    """
    if not usuario_logado():
        return redirect("/")

    agora_local = agora()
    hoje = agora_local.strftime("%Y-%m-%d")
    hora_atual = agora_local.strftime("%H:%M:%S")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        sql("""
            SELECT * FROM registros
            WHERE user_id=? AND data=?
            ORDER BY id DESC LIMIT 1
        """),
        (session["user_id"], hoje)
    )

    registro = cursor.fetchone()

    if not registro:
        cursor.execute(
            sql("INSERT INTO registros (user_id, data, entrada_manha) VALUES (?, ?, ?)"),
            (session["user_id"], hoje, hora_atual)
        )
    else:
        id_registro = registro[0]

        if not registro[4]:
            cursor.execute(
                sql("UPDATE registros SET saida_almoco=? WHERE id=?"),
                (hora_atual, id_registro)
            )
        elif not registro[5]:
            cursor.execute(
                sql("UPDATE registros SET volta_almoco=? WHERE id=?"),
                (hora_atual, id_registro)
            )
        elif not registro[6]:
            cursor.execute(
                sql("UPDATE registros SET saida_final=? WHERE id=?"),
                (hora_atual, id_registro)
            )
        else:
            cursor.execute(
                sql("INSERT INTO registros (user_id, data, entrada_manha) VALUES (?, ?, ?)"),
                (session["user_id"], hoje, hora_atual)
            )

    conn.commit()
    conn.close()

    return redirect("/dashboard")


@app.route("/logout")
def logout():
    """
    Encerra sessão do usuário.
    """
    session.clear()
    return redirect("/")


# ==========================================================
# INICIALIZAÇÃO
# ==========================================================

if __name__ == "__main__":
    criar_banco()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
