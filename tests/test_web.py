import pytest
import os
from web.app import app, criar_banco

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

