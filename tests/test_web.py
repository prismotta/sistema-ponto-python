import pytest
import os
from web.app import app, criar_banco, parse_hora
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO

import openpyxl

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
    assert b"Saldo do Dia" in response.data
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
            "nome_exibicao": "João",
            "nome_empresa": "Empresa X",
            "horas_diarias_esperadas": "08:30",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nome_funcionario, nome_exibicao, nome_empresa, horas_diarias_esperadas_min FROM usuarios WHERE id=1")
    row = cursor.fetchone()
    conn.close()

    assert row == ("João da Silva", "João", "Empresa X", 8 * 60 + 30)


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


def test_dashboard_exibe_nome_funcionario_ou_nao_informado(client):
    _criar_usuario_e_logar(client)

    # Sem nome no perfil
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Funcionário: não informado".encode("utf-8") in response.data

    # Com nome no perfil
    client.post("/perfil", data={"nome_funcionario": "Maria", "horas_diarias_esperadas": "8"}, follow_redirects=True)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Funcionário: Maria".encode("utf-8") in response.data


def test_dashboard_prioriza_nome_exibicao(client):
    _criar_usuario_e_logar(client)
    client.post(
        "/perfil",
        data={"nome_funcionario": "Priscila F. Motta", "nome_exibicao": "Pri", "horas_diarias_esperadas": "8"},
        follow_redirects=True,
    )

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Funcionário: Pri".encode("utf-8") in response.data


def test_dashboard_usa_primeiro_nome_quando_nome_exibicao_vazio(client):
    _criar_usuario_e_logar(client)
    client.post(
        "/perfil",
        data={"nome_funcionario": "Priscila F. Motta", "nome_exibicao": "", "horas_diarias_esperadas": "8"},
        follow_redirects=True,
    )

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Funcionário: Priscila".encode("utf-8") in response.data


def test_dashboard_botao_registrar_ponto(client):
    _criar_usuario_e_logar(client)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Registrar entrada".encode("utf-8") in response.data


def test_api_sem_login_deve_falhar(client):
    resp = client.get("/api/profile")
    assert resp.status_code == 401
    assert resp.is_json
    assert resp.json["success"] is False


def test_api_get_profile_logado(client):
    _criar_usuario_e_logar(client)
    client.put(
        "/api/profile",
        json={"nome_funcionario": "João da Silva", "nome_exibicao": "João", "nome_empresa": "Empresa X", "horas_diarias_esperadas": "8"},
    )
    resp = client.get("/api/profile")
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.json["success"] is True
    assert resp.json["profile"]["nome_funcionario"] == "João da Silva"
    assert resp.json["profile"]["nome_exibicao"] == "João"


def test_api_put_profile_atualiza_perfil(client):
    _criar_usuario_e_logar(client)
    resp = client.put(
        "/api/profile",
        json={"nome_funcionario": "Maria Souza", "nome_exibicao": "Mari", "nome_empresa": "ACME", "horas_diarias_esperadas": "08:30"},
    )
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.json["success"] is True
    assert resp.json["profile"]["horas_diarias_esperadas_min"] == 8 * 60 + 30


def test_api_listar_registros_apenas_do_usuario(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    client.post("/api/ponto")

    client.get("/logout")
    _criar_usuario_e_logar(client, "u2", "1234")
    client.post("/api/ponto")

    resp = client.get("/api/registros")
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.json["success"] is True
    assert len(resp.json["registros"]) == 1


def test_api_registrar_ponto(client):
    _criar_usuario_e_logar(client)
    resp = client.post("/api/ponto")
    assert resp.status_code == 201
    assert resp.is_json
    assert resp.json["success"] is True

    resp_list = client.get("/api/registros")
    assert resp_list.status_code == 200
    assert len(resp_list.json["registros"]) >= 1


def test_api_deletar_registro_proprio(client):
    _criar_usuario_e_logar(client)
    client.post("/api/ponto")

    resp_list = client.get("/api/registros")
    registro_id = resp_list.json["registros"][0]["id"]

    resp_del = client.delete(f"/api/registros/{registro_id}")
    assert resp_del.status_code == 200
    assert resp_del.is_json
    assert resp_del.json["success"] is True


def test_api_impede_deletar_registro_de_outro_usuario(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    client.post("/api/ponto")
    resp_list = client.get("/api/registros")
    registro_id = resp_list.json["registros"][0]["id"]

    client.get("/logout")
    _criar_usuario_e_logar(client, "u2", "1234")
    resp_del = client.delete(f"/api/registros/{registro_id}")
    assert resp_del.status_code == 404
    assert resp_del.is_json
    assert resp_del.json["success"] is False


def test_api_deletar_conta_logada(client):
    _criar_usuario_e_logar(client)
    resp = client.delete("/api/account", json={"confirmacao": "EXCLUIR"})
    assert resp.status_code == 200
    assert resp.is_json
    assert resp.json["success"] is True

    # Deve estar deslogado
    resp2 = client.get("/api/profile")
    assert resp2.status_code == 401


def test_dashboard_sem_registros_mostra_mensagem_graficos(client):
    _criar_usuario_e_logar(client)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Ainda não há dados suficientes para gerar o gráfico.".encode("utf-8") in response.data


def test_dashboard_graficos_apenas_do_usuario_logado(client):
    _criar_usuario_e_logar(client, "u1", "1234")

    # Insere registro finalizado para u1
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, "2026-01-01", "08:00", "12:00", "13:00", "17:00"),
    )
    conn.commit()
    conn.close()

    client.get("/logout")
    _criar_usuario_e_logar(client, "u2", "1234")

    # Insere registro finalizado para u2
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (2, "2026-02-02", "08:00", "12:00", "13:00", "18:00"),
    )
    conn.commit()
    conn.close()

    response = client.get("/dashboard")
    assert response.status_code == 200
    # Deve conter apenas a data do usuário logado (u2)
    assert b"2026-02-02" in response.data
    assert b"2026-01-01" not in response.data


def test_export_excel_sem_login_falha(client):
    resp = client.get("/export/excel", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_export_excel_retorna_arquivo_valido_e_so_do_usuario(client):
    _criar_usuario_e_logar(client, "u1", "1234")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, "2026-03-10", "08:00", "12:00", "13:00", "17:00"),
    )
    conn.commit()
    conn.close()

    client.get("/logout")
    _criar_usuario_e_logar(client, "u2", "1234")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (2, "2026-04-11", "08:00", "12:00", "13:00", "18:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/export/excel")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment")
    assert "registros_ponto.xlsx" in resp.headers["Content-Disposition"]

    wb = openpyxl.load_workbook(BytesIO(resp.data))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0][0].startswith("Período:")
    assert rows[2] == (
        "Data",
        "Entrada",
        "Saída Almoço",
        "Volta Almoço",
        "Saída Final",
        "Total Trabalhado",
        "Saldo do Dia",
    )

    # Deve conter apenas registro do u2
    valores = "\n".join(str(c) for r in rows[3:] for c in r if c is not None)
    assert "2026-04-11" in valores
    assert "2026-03-10" not in valores


def test_dashboard_filtro_periodo_retorna_apenas_registros_do_intervalo(client):
    _criar_usuario_e_logar(client, "u1", "1234")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, "2026-01-01", "08:00", "12:00", "13:00", "17:00"),
            (1, "2026-02-01", "08:00", "12:00", "13:00", "17:00"),
            (1, "2026-03-01", "08:00", "12:00", "13:00", "17:00"),
        ],
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard?data_inicio=2026-02-01&data_fim=2026-02-28")
    assert resp.status_code == 200
    assert b"2026-02-01" in resp.data
    assert b"2026-01-01" not in resp.data
    assert b"2026-03-01" not in resp.data


def test_export_excel_respeita_filtro_periodo(client):
    _criar_usuario_e_logar(client, "u1", "1234")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, "2026-01-01", "08:00", "12:00", "13:00", "17:00"),
            (1, "2026-02-15", "08:00", "12:00", "13:00", "17:00"),
        ],
    )
    conn.commit()
    conn.close()

    resp = client.get("/export/excel?data_inicio=2026-02-01&data_fim=2026-02-28")
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(BytesIO(resp.data))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0][0] == "Período: 01/02/2026 até 28/02/2026"

    valores = "\n".join(str(c) for r in rows[3:] for c in r if c is not None)
    assert "2026-02-15" in valores
    assert "2026-01-01" not in valores


def test_dashboard_valida_periodo_invalido(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    resp = client.get("/dashboard?data_inicio=2026-03-10&data_fim=2026-03-01", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/dashboard")


def test_export_pdf_sem_login_falha(client):
    resp = client.get("/export/pdf", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_export_pdf_retorna_pdf_valido_e_so_do_usuario(client):
    _criar_usuario_e_logar(client, "u1", "1234")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, "2026-03-10", "08:00", "12:00", "13:00", "17:00"),
    )
    conn.commit()
    conn.close()

    client.get("/logout")
    _criar_usuario_e_logar(client, "u2", "1234")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (2, "2026-04-11", "08:00", "12:00", "13:00", "18:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/export/pdf")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment")
    assert "registros_ponto.pdf" in resp.headers["Content-Disposition"]
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")

    # Como o PDF é gerado sem compressão, o texto deve estar presente.
    assert b"2026-04-11" in resp.data
    assert b"2026-03-10" not in resp.data


def test_export_pdf_respeita_filtro_periodo(client):
    _criar_usuario_e_logar(client, "u1", "1234")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, "2026-01-01", "08:00", "12:00", "13:00", "17:00"),
            (1, "2026-02-15", "08:00", "12:00", "13:00", "17:00"),
        ],
    )
    conn.commit()
    conn.close()

    resp = client.get("/export/pdf?data_inicio=2026-02-01&data_fim=2026-02-28")
    assert resp.status_code == 200
    assert resp.data.startswith(b"%PDF")
    assert b"01/02/2026" in resp.data
    assert b"28/02/2026" in resp.data
    assert b"2026-02-15" in resp.data
    assert b"2026-01-01" not in resp.data


def test_alterar_senha_exige_senha_atual_correta(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    resp = client.post(
        "/perfil/alterar-senha",
        data={"senha_atual": "errada", "nova_senha": "nova", "confirmar_nova_senha": "nova"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Senha atual incorreta.".encode("utf-8") in resp.data


def test_alterar_senha_sucesso_e_login_com_nova_senha(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    resp = client.post(
        "/perfil/alterar-senha",
        data={"senha_atual": "1234", "nova_senha": "nova123", "confirmar_nova_senha": "nova123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Senha alterada com sucesso.".encode("utf-8") in resp.data

    client.get("/logout")
    resp_login = client.post("/", data={"username": "u1", "password": "nova123"}, follow_redirects=False)
    assert resp_login.status_code == 302
    assert "/dashboard" in resp_login.headers["Location"]


def test_dashboard_mostra_botao_este_mes_e_banco_de_horas(client):
    _criar_usuario_e_logar(client, "u1", "1234")

    # Define esperado: 8h (default já é 8h, mas mantém explícito)
    client.post("/perfil", data={"horas_diarias_esperadas": "8"}, follow_redirects=True)

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    # +1h
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, "2026-04-10", "08:00", "12:00", "13:00", "18:00"),
    )
    # -1h
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, "2026-04-11", "08:00", "12:00", "13:00", "16:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Este m\xc3\xaas" in resp.data
    assert "Banco de horas do período:".encode("utf-8") in resp.data
    assert b"+0h 00m" in resp.data
    assert "Banco de horas do mês atual:".encode("utf-8") in resp.data


def test_dashboard_banco_mes_atual_considera_apenas_mes_corrente_e_finalizados(client):
    _criar_usuario_e_logar(client, "u1", "1234")

    from datetime import date

    hoje = date.today()
    mes_inicio = hoje.replace(day=1)
    dia_mes = mes_inicio.replace(day=min(2, 28))
    # dia fora do mês (mês anterior)
    if mes_inicio.month == 1:
        fora_mes = mes_inicio.replace(year=mes_inicio.year - 1, month=12, day=28)
    else:
        fora_mes = mes_inicio.replace(month=mes_inicio.month - 1, day=28)

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    # Dentro do mês: +1h
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, dia_mes.isoformat(), "08:00", "12:00", "13:00", "18:00"),
    )
    # Dentro do mês: em aberto (não conta)
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha)
        VALUES (?, ?, ?)
        """,
        (1, mes_inicio.isoformat(), "08:00"),
    )
    # Fora do mês: +2h (não conta)
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, fora_mes.isoformat(), "08:00", "12:00", "13:00", "19:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Banco de horas do mês atual: +1h 00m".encode("utf-8") in resp.data


def test_404_amigavel_mostra_botao_voltar(client):
    resp = client.get("/nao-existe")
    assert resp.status_code == 404
    assert b"404" in resp.data

    _criar_usuario_e_logar(client, "u1", "1234")
    resp2 = client.get("/nao-existe-2")
    assert resp2.status_code == 404
    assert b"/dashboard" in resp2.data


def test_status_dia_nao_iniciada(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Não iniciada".encode("utf-8") in resp.data


def test_status_dia_em_andamento(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    # cria entrada hoje em aberto via rota existente
    client.get("/bater")
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Em andamento".encode("utf-8") in resp.data


def test_status_dia_jornada_completa(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    client.post("/perfil", data={"horas_diarias_esperadas": "8"}, follow_redirects=True)

    hoje = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, hoje, "08:00", "12:00", "13:00", "17:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Jornada completa".encode("utf-8") in resp.data


def test_status_dia_jornada_incompleta(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    client.post("/perfil", data={"horas_diarias_esperadas": "8"}, follow_redirects=True)

    hoje = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, hoje, "08:00", "12:00", "13:00", "16:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Jornada incompleta".encode("utf-8") in resp.data


def test_tabela_saldo_recebe_classe_por_sinal(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    client.post("/perfil", data={"horas_diarias_esperadas": "8"}, follow_redirects=True)

    hoje = datetime.now().strftime("%Y-%m-%d")
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    anteontem = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    # +1h
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, anteontem, "08:00", "12:00", "13:00", "18:00"),
    )
    # -1h
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, ontem, "08:00", "12:00", "13:00", "16:00"),
    )
    # 0h
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, hoje, "08:00", "12:00", "13:00", "17:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"class=\"text-success\">+1h 00m" in resp.data
    assert b"class=\"text-danger\">-1h 00m" in resp.data
    assert b"class=\"text-secondary\">+0h 00m" in resp.data


def test_botao_ponto_sem_registro_hoje_mostra_registrar_entrada(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Registrar entrada".encode("utf-8") in resp.data


def test_botao_ponto_com_entrada_sem_saida_almoco_mostra_saida_almoco(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    hoje = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO registros (user_id, data, entrada_manha) VALUES (?, ?, ?)",
        (1, hoje, "08:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Registrar saída almoço".encode("utf-8") in resp.data


def test_botao_ponto_com_saida_almoco_sem_volta_mostra_volta_almoco(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    hoje = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco)
        VALUES (?, ?, ?, ?)
        """,
        (1, hoje, "08:00", "12:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Registrar volta almoço".encode("utf-8") in resp.data


def test_botao_ponto_com_volta_almoco_sem_saida_final_mostra_saida_final(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    hoje = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco)
        VALUES (?, ?, ?, ?, ?)
        """,
        (1, hoje, "08:00", "12:00", "13:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Registrar saída final".encode("utf-8") in resp.data


def test_botao_ponto_com_saida_final_mostra_registrar_novo_ponto(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    hoje = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("web/database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO registros (user_id, data, entrada_manha, saida_almoco, volta_almoco, saida_final)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, hoje, "08:00", "12:00", "13:00", "17:00"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Registrar novo ponto".encode("utf-8") in resp.data


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


def test_flash_exclusao_conta_nao_persiste_para_outro_usuario(client):
    _criar_usuario_e_logar(client, "u1", "1234")
    response = client.post("/perfil/excluir-conta", data={"confirmacao": "EXCLUIR"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Conta excluída com sucesso.".encode("utf-8") in response.data

    # Criar e logar outro usuário não deve ver o flash antigo no dashboard
    _criar_usuario_e_logar(client, "u2", "1234")
    response_dashboard = client.get("/dashboard")
    assert response_dashboard.status_code == 200
    assert "Conta excluída com sucesso.".encode("utf-8") not in response_dashboard.data

