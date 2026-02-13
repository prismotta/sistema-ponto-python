# Sistema de Bater Ponto em Python

Projeto simples de registro de ponto desenvolvido em Python.
Ideal para fins educacionais e portfólio.

---

## Funcionalidades

- Registro de entrada
- Registro de saída
- Cálculo automático de horas trabalhadas
- Armazenamento em arquivo CSV
- Estrutura organizada em módulos (boa prática de projeto)

---

## Tecnologias Utilizadas

- Python 3
- Biblioteca padrão `csv`
- Estrutura modular

---

## Estrutura do Projeto

```
sistema-ponto/
│
├── src/
│   ├── __init__.py
│   ├── registro.py
│   └── utils.py
│
├── data/
│   └── ponto.csv
│
├── tests/
│
├── main.py
├── requirements.txt
└── README.md
```

---

## Como Executar

1. Clone o repositório:

```bash
git clone https://github.com/seu-usuario/sistema-ponto.git
```

2. Acesse a pasta do projeto:

```bash
cd sistema-ponto
```

3. Execute o sistema:

```bash
python main.py
```

---

##  Como Funciona

- O sistema cria automaticamente o arquivo `ponto.csv`
- Ao registrar entrada, salva data e horário
- Ao registrar saída, calcula automaticamente o total trabalhado
- Os dados ficam armazenados na pasta `data/`

---

##  Próximas Melhorias (Roadmap)

- Testes automatizados com Pytest
- Interface gráfica com Tkinter
- Versão Web com Flask
- Relatórios mensais automáticos
- Controle de múltiplos usuários

---

##  Objetivo do Projeto

Este projeto foi desenvolvido como prática de organização de código,
estruturação de sistema e futura implementação de testes automatizados,
seguindo boas práticas para portfólio na área de QA.

---

## Testes

Para rodar os testes:

python -m pytest

---

Projeto para fins educacionais.
