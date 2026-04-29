![CI](https://github.com/prismotta/sistema-ponto-python/actions/workflows/ci.yml/badge.svg)

# Sistema de Ponto - Projeto QA

Aplicação em produção:  
https://sistema-ponto-python.onrender.com/

Sistema completo de controle de ponto desenvolvido em Python com foco em qualidade, testabilidade e boas práticas de arquitetura.

O projeto evoluiu de uma versão CLI para interface gráfica e, posteriormente, para uma aplicação web com autenticação, banco de dados e testes automatizados com alta cobertura.

---

## Funcionalidades

### Autenticação
- Cadastro de usuário
- Login com hash seguro de senha (Werkzeug)
- Controle de sessão
- Logout
- Rotas protegidas

### Registro de Ponto
- Entrada
- Saída para almoço
- Volta do almoço
- Saída final
- Cálculo automático de horas trabalhadas

### Histórico
- Histórico por usuário
- Total trabalhado por dia

### Testes Automatizados
- Testes unitários
- Testes de integração
- Testes de fluxo HTTP
- Testes de regras de negócio
- Cobertura de código: 94%

---

## Arquitetura do Projeto

```
sistema-ponto/
│
├── src/                # Módulo legado (CLI/CSV)
│   ├── registro.py
│   └── utils.py
│
├── web/                # Aplicação Flask (banco de dados)
│   ├── app.py
│   ├── templates/
│   └── database.db
│
├── tests/              # Testes automatizados
│   ├── test_registro.py
│   └── test_web.py
│
├── gui.py              # Interface gráfica (Tkinter)
├── main.py             # Versão CLI
├── requirements.txt
└── README.md
```

---

## Decisões Técnicas

### Separação de camadas
- `src/` contém apenas o fluxo legado CLI/GUI baseado em CSV (mantido para referência e testes).
- `web/` contém a aplicação web Flask e usa **apenas banco de dados** (SQLite/PostgreSQL) como fonte de dados.
- Código desacoplado para facilitar testes.

### Inversão de dependência
Funções recebem caminho de arquivo como parâmetro, eliminando dependência de variáveis globais e aumentando testabilidade.

### Testabilidade
Uso de:
- pytest
- tmp_path
- Flask test_client
- pytest-cov

---

## Executando os Testes

Instalar dependências:

```bash
pip install -r requirements.txt
```

Rodar testes:

```bash
python -m pytest
```

Rodar com cobertura:

```bash
python -m pytest --cov=web --cov=src
```

Gerar relatório HTML:

```bash
python -m pytest --cov=web --cov=src --cov-report=html
```

Abrir relatório:

```
htmlcov/index.html
```

Cobertura atual: 94%

---

## Executando a Aplicação Web Localmente

```bash
python web/app.py
```

Acesse:

```
http://127.0.0.1:5000
```

---

## Tecnologias Utilizadas

- Python 3.11+
- Flask
- SQLite
- Pytest
- Pytest-cov
- HTML / Bootstrap
- Tkinter (GUI)

---

## Deploy

Aplicação hospedada em ambiente público utilizando Render.

URL:  
https://sistema-ponto-python.onrender.com/

---

## Evolução do Projeto

1. Versão CLI com CSV  
2. Refatoração para código desacoplado  
3. Interface gráfica  
4. Aplicação web com autenticação  
5. Testes automatizados  
6. Cobertura de código acima de 90%  
7. Deploy em ambiente público  

---

## Objetivo do Projeto

Demonstrar:

- Capacidade de estruturar projeto real  
- Aplicar boas práticas de arquitetura  
- Criar testes automatizados  
- Medir cobertura  
- Garantir qualidade de software  
- Implementar CI com GitHub Actions  
- Realizar deploy contínuo  

---

## Autoria

Projeto desenvolvido como parte da preparação para atuação como QA / QA Automation.

