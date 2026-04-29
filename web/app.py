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
from typing import Optional, Tuple, Any, Dict
import threading
from io import BytesIO

import psycopg2
from flask import Flask, render_template, request, redirect, session, flash, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


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

_db_init_lock = threading.Lock()
_db_init_done = False


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
    Garante também compatibilidade com bancos legados:
    - Adiciona colunas ausentes na tabela `registros` (quando a estrutura antiga
      não possuía campos de almoço/saída final).
    """
    conn = conectar()
    cursor = conn.cursor()

    if IS_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nome_funcionario TEXT,
                nome_exibicao TEXT,
                nome_empresa TEXT,
                horas_diarias_esperadas_min INTEGER
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

        # Migração: adiciona colunas ausentes em bases antigas
        for coluna in ("entrada_manha", "saida_almoco", "volta_almoco", "saida_final"):
            cursor.execute(f"ALTER TABLE registros ADD COLUMN IF NOT EXISTS {coluna} TEXT")

        # Migração: adiciona colunas do perfil em bases antigas
        cursor.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_funcionario TEXT")
        cursor.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_exibicao TEXT")
        cursor.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_empresa TEXT")
        cursor.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS horas_diarias_esperadas_min INTEGER")
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nome_funcionario TEXT,
                nome_exibicao TEXT,
                nome_empresa TEXT,
                horas_diarias_esperadas_min INTEGER
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

        # Migração: adiciona colunas ausentes em bases antigas (SQLite)
        cursor.execute("PRAGMA table_info(registros)")
        colunas_existentes = {row[1] for row in cursor.fetchall()}
        for coluna in ("entrada_manha", "saida_almoco", "volta_almoco", "saida_final"):
            if coluna not in colunas_existentes:
                try:
                    cursor.execute(f"ALTER TABLE registros ADD COLUMN {coluna} TEXT")
                except sqlite3.OperationalError as e:
                    # Se dois processos tentarem migrar ao mesmo tempo, o segundo pode
                    # receber "duplicate column name". Nesse caso, basta ignorar.
                    if "duplicate column name" not in str(e).lower():
                        raise

        # Migração: adiciona colunas do perfil em bases antigas (SQLite)
        cursor.execute("PRAGMA table_info(usuarios)")
        colunas_usuarios = {row[1] for row in cursor.fetchall()}
        for coluna, tipo in (
            ("nome_funcionario", "TEXT"),
            ("nome_exibicao", "TEXT"),
            ("nome_empresa", "TEXT"),
            ("horas_diarias_esperadas_min", "INTEGER"),
        ):
            if coluna not in colunas_usuarios:
                try:
                    cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {coluna} {tipo}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise

    conn.commit()
    conn.close()


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================

def parse_hora(hora: Optional[str]) -> Optional[datetime]:
    """
    Faz parse de strings de hora vindas do banco.

    Aceita formatos legados como:
    - HH:MM
    - HH:MM:SS
    - HH:MM:SS.ffffff
    """
    if not hora:
        return None

    for fmt in ("%H:%M:%S", "%H:%M", "%H:%M:%S.%f"):
        try:
            return datetime.strptime(hora, fmt)
        except ValueError:
            continue

    return None


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


def api_erro(mensagem: str, status_code: int = 400):
    return jsonify({"success": False, "error": mensagem}), status_code


def api_ok(payload: Optional[Dict[str, Any]] = None, status_code: int = 200):
    data: Dict[str, Any] = {"success": True}
    if payload:
        data.update(payload)
    return jsonify(data), status_code


def exigir_login_api():
    if not usuario_logado():
        return api_erro("Não autenticado", 401)
    return None


def obter_perfil_usuario(user_id: int) -> Dict[str, Any]:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        sql("""
            SELECT nome_funcionario, nome_exibicao, nome_empresa, horas_diarias_esperadas_min
            FROM usuarios
            WHERE id=?
        """),
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"nome_funcionario": None, "nome_exibicao": None, "nome_empresa": None, "horas_diarias_esperadas_min": None}

    return {"nome_funcionario": row[0], "nome_exibicao": row[1], "nome_empresa": row[2], "horas_diarias_esperadas_min": row[3]}


def primeiro_nome(nome: Optional[str]) -> Optional[str]:
    if not nome:
        return None
    partes = [p for p in nome.strip().split() if p]
    return partes[0] if partes else None


def perfil_para_json(perfil: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "nome_funcionario": perfil.get("nome_funcionario"),
        "nome_exibicao": perfil.get("nome_exibicao"),
        "nome_empresa": perfil.get("nome_empresa"),
        "horas_diarias_esperadas_min": perfil.get("horas_diarias_esperadas_min"),
    }


def atualizar_perfil_usuario(user_id: int, dados: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    nome_funcionario = (dados.get("nome_funcionario") or "").strip() or None
    nome_exibicao = (dados.get("nome_exibicao") or "").strip() or None
    nome_empresa = (dados.get("nome_empresa") or "").strip() or None
    horas_texto = dados.get("horas_diarias_esperadas") or ""

    horas_min = parse_horas_esperadas_min(horas_texto)
    if str(horas_texto).strip() and horas_min is None:
        return False, "Formato inválido em horas diárias esperadas. Use 8, 8.5 ou 08:00."

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        sql("""
            UPDATE usuarios
            SET nome_funcionario=?, nome_exibicao=?, nome_empresa=?, horas_diarias_esperadas_min=?
            WHERE id=?
        """),
        (nome_funcionario, nome_exibicao, nome_empresa, horas_min, user_id),
    )
    conn.commit()
    conn.close()

    return True, None


def excluir_registro_usuario(user_id: int, registro_id: int) -> bool:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(sql("DELETE FROM registros WHERE id=? AND user_id=?"), (registro_id, user_id))
    apagados = cursor.rowcount
    conn.commit()
    conn.close()
    return bool(apagados)


def excluir_conta_usuario(user_id: int) -> None:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(sql("DELETE FROM registros WHERE user_id=?"), (user_id,))
    cursor.execute(sql("DELETE FROM usuarios WHERE id=?"), (user_id,))
    conn.commit()
    conn.close()


def registrar_ponto(user_id: int, quando: datetime) -> Dict[str, Any]:
    hoje = quando.strftime("%Y-%m-%d")
    hora_atual = quando.strftime("%H:%M:%S")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        sql("""
            SELECT id, entrada_manha, saida_almoco, volta_almoco, saida_final
            FROM registros
            WHERE user_id=? AND data=?
            ORDER BY id DESC LIMIT 1
        """),
        (user_id, hoje),
    )
    registro = cursor.fetchone()

    acao = "criado"
    campo = "entrada_manha"
    registro_id = None

    if not registro:
        cursor.execute(
            sql("INSERT INTO registros (user_id, data, entrada_manha) VALUES (?, ?, ?)"),
            (user_id, hoje, hora_atual),
        )
        registro_id = cursor.lastrowid if not IS_POSTGRES else None
    else:
        registro_id = registro[0]
        saida_almoco = registro[2]
        volta_almoco = registro[3]
        saida_final = registro[4]

        if not saida_almoco:
            cursor.execute(sql("UPDATE registros SET saida_almoco=? WHERE id=?"), (hora_atual, registro_id))
            acao = "atualizado"
            campo = "saida_almoco"
        elif not volta_almoco:
            cursor.execute(sql("UPDATE registros SET volta_almoco=? WHERE id=?"), (hora_atual, registro_id))
            acao = "atualizado"
            campo = "volta_almoco"
        elif not saida_final:
            cursor.execute(sql("UPDATE registros SET saida_final=? WHERE id=?"), (hora_atual, registro_id))
            acao = "atualizado"
            campo = "saida_final"
        else:
            cursor.execute(
                sql("INSERT INTO registros (user_id, data, entrada_manha) VALUES (?, ?, ?)"),
                (user_id, hoje, hora_atual),
            )
            acao = "criado"
            campo = "entrada_manha"
            registro_id = cursor.lastrowid if not IS_POSTGRES else None

    conn.commit()
    conn.close()

    return {"acao": acao, "campo": campo, "data": hoje, "hora": hora_atual, "registro_id": registro_id}


def parse_horas_esperadas_min(valor: Optional[str]) -> Optional[int]:
    """
    Aceita entrada do perfil como:
    - "8" ou "8.5" (horas)
    - "08:00" ou "8:30" (HH:MM)
    Retorna minutos (int) ou None.
    """
    if valor is None:
        return None

    texto = valor.strip()
    if not texto:
        return None

    if ":" in texto:
        partes = texto.split(":")
        if len(partes) != 2:
            return None
        try:
            horas = int(partes[0])
            minutos = int(partes[1])
        except ValueError:
            return None
        if horas < 0 or minutos < 0 or minutos >= 60:
            return None
        return horas * 60 + minutos

    try:
        horas_float = float(texto.replace(",", "."))
    except ValueError:
        return None
    if horas_float < 0:
        return None
    return int(round(horas_float * 60))


def formatar_horas_minutos(delta: timedelta) -> str:
    total_min = int(round(delta.total_seconds() / 60))
    sinal = "+" if total_min >= 0 else "-"
    total_min_abs = abs(total_min)
    horas = total_min_abs // 60
    minutos = total_min_abs % 60
    return f"{sinal}{horas}h {minutos:02d}m"


def calcular_saldo_dia(total_trabalhado: timedelta, esperado_min: Optional[int]) -> Optional[timedelta]:
    if esperado_min is None:
        return None
    return total_trabalhado - timedelta(minutes=int(esperado_min))


def horas_decimal(delta: timedelta) -> float:
    return round(delta.total_seconds() / 3600, 2)


def formatar_duracao_sem_sinal(delta: timedelta) -> str:
    total_min = int(round(delta.total_seconds() / 60))
    total_min_abs = abs(total_min)
    horas = total_min_abs // 60
    minutos = total_min_abs % 60
    return f"{horas}h {minutos:02d}m"


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

    entrada_dt = parse_hora(entrada)
    saida_almoco_dt = parse_hora(saida_almoco)
    volta_almoco_dt = parse_hora(volta_almoco)
    saida_final_dt = parse_hora(saida_final)

    if entrada_dt and saida_almoco_dt and saida_almoco_dt >= entrada_dt:
        total += (saida_almoco_dt - entrada_dt)

    if volta_almoco_dt and saida_final_dt and saida_final_dt >= volta_almoco_dt:
        total += (saida_final_dt - volta_almoco_dt)

    return total


# ==========================================================
# ROTAS
# ==========================================================

@app.before_request
def garantir_banco():
    global _db_init_done
    if _db_init_done:
        return

    with _db_init_lock:
        if _db_init_done:
            return
        criar_banco()
        _db_init_done = True


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
    Exibe histórico de registros e total do dia atual.
    """
    if not usuario_logado():
        return redirect("/")

    hoje = agora().strftime("%Y-%m-%d")

    conn = conectar()
    cursor = conn.cursor()

    perfil = obter_perfil_usuario(session["user_id"])
    esperado_min = perfil.get("horas_diarias_esperadas_min")
    if esperado_min is None:
        esperado_min = 8 * 60
    nome_exibicao = (perfil.get("nome_exibicao") or "").strip()
    nome_funcionario = (perfil.get("nome_funcionario") or "").strip()
    nome_dashboard = (
        nome_exibicao
        or (primeiro_nome(nome_funcionario) or "")
        or "não informado"
    )

    cursor.execute(
        sql("""
            SELECT id, user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final
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
    graf_labels: list[str] = []
    graf_saldo: list[float] = []

    for registro in registros_db:
        total_linha = calcular_total_registro(registro)
        if registro[2] == hoje:
            total_hoje += total_linha

        saida_final = registro[6]
        em_aberto = not bool(parse_hora(saida_final))
        saldo_delta = None if em_aberto else calcular_saldo_dia(total_linha, esperado_min)
        saldo_str = "em aberto" if em_aberto else (formatar_horas_minutos(saldo_delta) if saldo_delta is not None else "-")

        if not em_aberto:
            graf_labels.append(registro[2])
            graf_saldo.append(horas_decimal(saldo_delta or timedelta()))

        registros.append({
            "id": registro[0],
            "data": registro[2],
            "entrada": registro[3],
            "saida_almoco": registro[4],
            "volta_almoco": registro[5],
            "saida_final": registro[6],
            "total": total_linha,
            "esperado": timedelta(minutes=int(esperado_min)) if esperado_min is not None else None,
            "saldo": saldo_str,
        })

    return render_template(
        "dashboard.html",
        registros=registros,
        total_hoje=total_hoje,
        nome_funcionario=nome_dashboard,
        graf_labels=graf_labels,
        graf_saldo=graf_saldo,
    )


@app.route("/perfil", methods=["GET", "POST"])
def perfil():
    if not usuario_logado():
        return redirect("/")

    if request.method == "POST":
        ok, erro = atualizar_perfil_usuario(
            session["user_id"],
            {
                "nome_funcionario": request.form.get("nome_funcionario"),
                "nome_exibicao": request.form.get("nome_exibicao"),
                "nome_empresa": request.form.get("nome_empresa"),
                "horas_diarias_esperadas": request.form.get("horas_diarias_esperadas"),
            },
        )
        if not ok:
            flash(erro or "Não foi possível salvar o perfil.", "danger")
            return redirect("/perfil")

        flash("Perfil salvo com sucesso.", "success")
        return redirect("/perfil")

    perfil_atual = obter_perfil_usuario(session["user_id"])
    horas_min = perfil_atual.get("horas_diarias_esperadas_min")
    horas_str = ""
    if horas_min is not None:
        horas_str = f"{int(horas_min // 60)}:{int(horas_min % 60):02d}"

    return render_template(
        "perfil.html",
        perfil=perfil_atual,
        horas_diarias_esperadas=horas_str,
    )


@app.route("/registros/<int:registro_id>/excluir", methods=["POST"])
def excluir_registro(registro_id: int):
    if not usuario_logado():
        return redirect("/")

    if excluir_registro_usuario(session["user_id"], registro_id):
        flash("Registro excluído com sucesso.", "success")
    else:
        flash("Registro não encontrado.", "danger")

    return redirect("/dashboard")


@app.route("/perfil/excluir-conta", methods=["POST"])
def excluir_conta():
    if not usuario_logado():
        return redirect("/")

    confirmacao = (request.form.get("confirmacao") or "").strip()
    if confirmacao != "EXCLUIR":
        flash("Confirmação inválida. Digite EXCLUIR para apagar sua conta.", "danger")
        return redirect("/perfil")

    user_id = session["user_id"]
    excluir_conta_usuario(user_id)

    session.clear()
    flash("Conta excluída com sucesso.", "success")
    return redirect("/")


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

    registrar_ponto(session["user_id"], agora())

    return redirect("/dashboard")


# ==========================================================
# API REST (JSON)
# ==========================================================

@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    erro = exigir_login_api()
    if erro:
        return erro

    perfil = obter_perfil_usuario(session["user_id"])
    return api_ok({"profile": perfil_para_json(perfil)})


@app.route("/api/profile", methods=["PUT"])
def api_put_profile():
    erro = exigir_login_api()
    if erro:
        return erro

    dados = request.get_json(silent=True) or {}
    ok, mensagem = atualizar_perfil_usuario(session["user_id"], dados)
    if not ok:
        return api_erro(mensagem or "Dados inválidos", 400)

    perfil = obter_perfil_usuario(session["user_id"])
    return api_ok({"profile": perfil_para_json(perfil)})


@app.route("/api/registros", methods=["GET"])
def api_listar_registros():
    erro = exigir_login_api()
    if erro:
        return erro

    perfil = obter_perfil_usuario(session["user_id"])
    esperado_min = perfil.get("horas_diarias_esperadas_min")
    if esperado_min is None:
        esperado_min = 8 * 60

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        sql("""
            SELECT id, user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final
            FROM registros
            WHERE user_id=?
            ORDER BY data DESC, id DESC
        """),
        (session["user_id"],),
    )
    registros_db = cursor.fetchall()
    conn.close()

    registros: list[Dict[str, Any]] = []
    for registro in registros_db:
        total_linha = calcular_total_registro(registro)
        saida_final = registro[6]
        em_aberto = not bool(parse_hora(saida_final))
        saldo_delta = None if em_aberto else calcular_saldo_dia(total_linha, esperado_min)
        saldo_str = "em aberto" if em_aberto else (formatar_horas_minutos(saldo_delta) if saldo_delta is not None else "-")

        registros.append(
            {
                "id": registro[0],
                "data": registro[2],
                "entrada_manha": registro[3],
                "saida_almoco": registro[4],
                "volta_almoco": registro[5],
                "saida_final": registro[6],
                "total_seconds": int(total_linha.total_seconds()),
                "saldo": saldo_str,
                "em_aberto": em_aberto,
            }
        )

    return api_ok({"registros": registros})


@app.route("/api/ponto", methods=["POST"])
def api_registrar_ponto():
    erro = exigir_login_api()
    if erro:
        return erro

    resultado = registrar_ponto(session["user_id"], agora())
    return api_ok({"ponto": resultado}, 201)


@app.route("/api/registros/<int:registro_id>", methods=["DELETE"])
def api_excluir_registro(registro_id: int):
    erro = exigir_login_api()
    if erro:
        return erro

    if not excluir_registro_usuario(session["user_id"], registro_id):
        return api_erro("Registro não encontrado", 404)
    return api_ok({"deleted_id": registro_id})


@app.route("/api/account", methods=["DELETE"])
def api_excluir_conta():
    erro = exigir_login_api()
    if erro:
        return erro

    dados = request.get_json(silent=True) or {}
    confirmacao = (dados.get("confirmacao") or "").strip()
    if confirmacao != "EXCLUIR":
        return api_erro("Confirmação inválida. Envie confirmacao=EXCLUIR.", 400)

    user_id = session["user_id"]
    excluir_conta_usuario(user_id)
    session.clear()

    return api_ok({"deleted": True})


@app.route("/logout")
def logout():
    """
    Encerra sessão do usuário.
    """
    session.clear()
    return redirect("/")


@app.route("/export/excel")
def export_excel():
    """
    Exporta registros do usuário logado em Excel (.xlsx).
    """
    if not usuario_logado():
        return redirect("/")

    user_id = session["user_id"]
    perfil = obter_perfil_usuario(user_id)
    esperado_min = perfil.get("horas_diarias_esperadas_min")
    if esperado_min is None:
        esperado_min = 8 * 60

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        sql("""
            SELECT id, user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final
            FROM registros
            WHERE user_id=?
            ORDER BY data DESC, id DESC
        """),
        (user_id,),
    )
    registros_db = cursor.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Registros"

    headers = [
        "Data",
        "Entrada",
        "Saída Almoço",
        "Volta Almoço",
        "Saída Final",
        "Total Trabalhado",
        "Saldo do Dia",
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)

    for registro in registros_db:
        total_linha = calcular_total_registro(registro)
        saida_final = registro[6]
        em_aberto = not bool(parse_hora(saida_final))
        saldo_delta = None if em_aberto else calcular_saldo_dia(total_linha, esperado_min)
        saldo_str = "em aberto" if em_aberto else (formatar_horas_minutos(saldo_delta) if saldo_delta is not None else "-")

        ws.append(
            [
                registro[2],
                registro[3] or "",
                registro[4] or "",
                registro[5] or "",
                registro[6] or "",
                formatar_duracao_sem_sinal(total_linha),
                saldo_str,
            ]
        )

    ws.freeze_panes = "A2"

    # Ajuste simples de largura das colunas
    for col_idx, _ in enumerate(headers, start=1):
        max_len = 0
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=True):
            value = row[0]
            if value is None:
                continue
            max_len = max(max_len, len(str(value)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="registros_ponto.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ==========================================================
# INICIALIZAÇÃO
# ==========================================================

if __name__ == "__main__":
    criar_banco()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
