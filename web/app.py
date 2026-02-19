import os
import sqlite3
from urllib.parse import urlparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg2
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash


# =====================================
# CONFIGURAÇÕES
# =====================================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")
DATABASE_PATH = os.getenv("DATABASE_PATH", "web/database.db")
DATABASE_URL = os.getenv("DATABASE_URL")
TIMEZONE = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")

IS_POSTGRES = bool(DATABASE_URL)


# =====================================
# BANCO DE DADOS
# =====================================

def conectar():
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


def criar_banco():
    conn = conectar()
    cursor = conn.cursor()

    if IS_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
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
                username TEXT UNIQUE,
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


# =====================================
# HELPERS
# =====================================

def agora():
    return datetime.now(ZoneInfo(TIMEZONE))


def usuario_logado():
    return "user_id" in session


# =====================================
# ROTAS
# =====================================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

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
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = conectar()
        cursor = conn.cursor()

        try:
            cursor.execute(
                sql("INSERT INTO usuarios (username, password) VALUES (?, ?)"),
                (username, password)
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
    if not usuario_logado():
        return redirect("/")

    hoje = agora().strftime("%Y-%m-%d")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        sql("""
            SELECT *
            FROM registros
            WHERE user_id=? AND data=?
            ORDER BY id DESC
        """),
        (session["user_id"], hoje)
    )

    registros_db = cursor.fetchall()
    conn.close()

    registros = []
    total_geral = timedelta()

    for r in registros_db:
        entrada, saida_almoco, volta_almoco, saida_final = r[3], r[4], r[5], r[6]
        total_linha = timedelta()

        if entrada and saida_almoco:
            total_linha += (
                datetime.strptime(saida_almoco, "%H:%M:%S")
                - datetime.strptime(entrada, "%H:%M:%S")
            )

        if volta_almoco and saida_final:
            total_linha += (
                datetime.strptime(saida_final, "%H:%M:%S")
                - datetime.strptime(volta_almoco, "%H:%M:%S")
            )

        total_geral += total_linha

        registros.append({
            "data": r[2],
            "entrada": entrada,
            "saida_almoco": saida_almoco,
            "volta_almoco": volta_almoco,
            "saida_final": saida_final,
            "total": total_linha
        })

    return render_template("dashboard.html", registros=registros, total=total_geral)


@app.route("/bater")
def bater():
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
            cursor.execute(sql("UPDATE registros SET saida_almoco=? WHERE id=?"),
                           (hora_atual, id_registro))
        elif not registro[5]:
            cursor.execute(sql("UPDATE registros SET volta_almoco=? WHERE id=?"),
                           (hora_atual, id_registro))
        elif not registro[6]:
            cursor.execute(sql("UPDATE registros SET saida_final=? WHERE id=?"),
                           (hora_atual, id_registro))
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
    session.clear()
    return redirect("/")


# =====================================
# START
# =====================================

if __name__ == "__main__":
    criar_banco()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
