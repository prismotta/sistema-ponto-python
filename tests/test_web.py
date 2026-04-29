import pytest
import os
from web.app import app, criar_banco, parse_hora
import sqlite3
from datetime import datetime, timedelta

@pytest.fixture
def client():
    # Usa banco de teste separado
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test"

    # Remove banco antigo se existir
    if os.path.exists("web/database.db"):
        os.remove("web/database.db")

    criar_banco()

    with app.test_client() as client:
        yield client


def test_login_valido(client):
    # Criar usuário
    client.post("/register", data={
        "username": "teste",
        "password": "1234"
    })

    # Fazer login
    response = client.post("/", data={
        "username": "teste",
        "password": "1234"
    }, follow_redirects=False)

    # Verifica redirecionamento para dashboard
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]

def test_login_invalido(client):
    # Criar usuário válido
    client.post("/register", data={
        "username": "teste",
        "password": "1234"
    })

    # Tentar login com senha errada
    response = client.post("/", data={
        "username": "teste",
        "password": "senha_errada"
    }, follow_redirects=True)

    # Deve permanecer na página de login
    assert response.status_code == 200

    # Verifica mensagem de erro na resposta
    assert b"Usu\xc3\xa1rio ou senha inv\xc3\xa1lidos" in response.data

def test_dashboard_protegido_sem_login(client):
    response = client.get("/dashboard", follow_redirects=False)

    # Deve redirecionar
    assert response.status_code == 302

    # Deve redirecionar para login
    assert "/" in response.headers["Location"]

def test_logout(client):
    # Criar usuário
    client.post("/register", data={
        "username": "teste",
        "password": "1234"
    })

    # Fazer login
    client.post("/", data={
        "username": "teste",
        "password": "1234"
    })

    # Garantir que dashboard funciona logado
    response_dashboard = client.get("/dashboard")
    assert response_dashboard.status_code == 200

    # Fazer logout
    client.get("/logout")

    # Tentar acessar dashboard novamente
    response = client.get("/dashboard", follow_redirects=False)

    # Deve redirecionar para login
    assert response.status_code == 302
    assert "/" in response.headers["Location"]

def test_fluxo_bater_ponto(client):
    # Criar usuário
    client.post("/register", data={
        "username": "teste",
        "password": "1234"
    })

    # Login
    client.post("/", data={
        "username": "teste",
        "password": "1234"
    })

    # 1ª batida → entrada_manha
    client.get("/bater")

    # 2ª batida → saida_almoco
    client.get("/bater")

    # 3ª batida → volta_almoco
    client.get("/bater")

    # 4ª batida → saida_final
    client.get("/bater")

    # Acessar dashboard
    response = client.get("/dashboard")

    assert response.status_code == 200

    # Verificar que as colunas aparecem preenchidas
    assert b"Sa\xc3\xadda Final" in response.data or b"Sa\xc3\xadda Final" in response.data


def test_dashboard_mostra_historico_de_dias_anteriores(client):
    # Criar usuário e logar
    client.post("/register", data={
        "username": "teste",
        "password": "1234"
    })
    client.post("/", data={
        "username": "teste",
        "password": "1234"
    })

    # Cria ao menos um registro de hoje
    client.get("/bater")

    # Insere manualmente um registro completo de ontem para simular histórico
    import sqlite3
    from datetime import datetime, timedelta

    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        # Formatos legados (sem segundos) não devem quebrar o histórico.
        (1, ontem, "08:00", "12:00", "13:00", "17:00")
    )
    conn.commit()
    conn.close()

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Total de hoje" in response.data
    assert ontem.encode("utf-8") in response.data


def test_parse_hora_aceita_formatos_legados():
    assert parse_hora(None) is None
    assert parse_hora("") is None

    assert parse_hora("08:30").strftime("%H:%M:%S") == "08:30:00"
    assert parse_hora("08:30:15").strftime("%H:%M:%S") == "08:30:15"
    assert parse_hora("08:30:15.123456").microsecond == 123456


def test_criar_banco_migra_registros_legado_sem_colunas_novas():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test"

    if os.path.exists("web/database.db"):
        os.remove("web/database.db")

    import sqlite3

    # Simula um banco legado: tabela `registros` existe mas não tem as colunas novas
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            data TEXT,
            entrada_manha TEXT,
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
    """)
    conn.commit()
    conn.close()

    criar_banco()

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(registros)")
    colunas = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert {"entrada_manha", "saida_almoco", "volta_almoco", "saida_final"}.issubset(colunas)

    with app.test_client() as client:
        client.post("/register", data={"username": "teste", "password": "1234"})
        client.post("/", data={"username": "teste", "password": "1234"})

        # Deve conseguir fazer batidas sem erro, mesmo partindo de schema legado
        client.get("/bater")
        client.get("/bater")

        response = client.get("/dashboard")
        assert response.status_code == 200


def _criar_usuario_e_logar(client, username: str = "teste", password: str = "1234"):
    client.post("/register", data={"username": username, "password": password})
    client.post("/", data={"username": username, "password": password})


def test_salvar_perfil(client):
    _criar_usuario_e_logar(client)

    response = client.post(
        "/perfil",
        data={
            "nome_funcionario": "João da Silva",
            "nome_empresa": "Empresa X",
            "horas_diarias_esperadas": "08:30",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_funcionario, nome_empresa, horas_diarias_esperadas_min FROM usuarios WHERE id=1")
    row = cursor.fetchone()
    conn.close()

    assert row == ("João da Silva", "Empresa X", 8 * 60 + 30)


def test_deletar_registro_so_afeta_usuario_logado(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    client.get("/bater")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM registros WHERE user_id=1")
    registro_id = cursor.fetchone()[0]
    conn.close()

    client.get("/logout")
    _criar_usuario_e_logar(client, "u2", "1234")

    # Tentativa de excluir registro de outro usuário não deve apagar nada
    client.post(f"/registros/{registro_id}/excluir", follow_redirects=True)

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM registros WHERE id=?", (registro_id,))
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_deletar_registro_do_proprio_usuario(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    client.get("/bater")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM registros WHERE user_id=1")
    registro_id = cursor.fetchone()[0]
    conn.close()

    client.post(f"/registros/{registro_id}/excluir", follow_redirects=True)

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM registros WHERE id=?", (registro_id,))
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 0


def test_calcular_saldo_extra_faltante_e_em_aberto(client):
    _criar_usuario_e_logar(client)

    # Define esperado: 8h
    client.post("/perfil", data={"horas_diarias_esperadas": "8"}, follow_redirects=True)

    hoje = datetime.now().strftime("%Y-%m-%d")
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    # Ontem: 9h trabalhadas -> +1h
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, ontem, "08:00", "12:00", "13:00", "18:00"),
    )
    # Dois dias atrás: 7h trabalhadas -> -1h
    anteontem = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, anteontem, "08:00", "12:00", "13:00", "16:00"),
    )
    # Hoje: sem saída final -> em aberto
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha)
        VALUES (?, ?, ?)
        """,
        (1, hoje, "08:00"),
    )
    conn.commit()
    conn.close()

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"+1h 00m" in response.data
    assert b"-1h 00m" in response.data
    assert b"em aberto" in response.data


def test_deletar_conta_apaga_registros_e_desloga(client):
    _criar_usuario_e_logar(client)
    client.get("/bater")

    response = client.post("/perfil/excluir-conta", data={"confirmacao": "EXCLUIR"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    # Acessar dashboard deve redirecionar (sessão encerrada)
    response_dashboard = client.get("/dashboard", follow_redirects=False)
    assert response_dashboard.status_code == 302
    assert response_dashboard.headers["Location"].endswith("/")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    usuarios = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM registros")
    registros = cursor.fetchone()[0]
    conn.close()

    assert usuarios == 0
    assert registros == 0

