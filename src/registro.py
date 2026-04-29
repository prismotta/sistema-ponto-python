import csv
from datetime import datetime


"""
MÓDULO LEGADO (CSV)

Este módulo é usado apenas pela versão CLI/GUI (main.py/gui.py) e pelos testes
unitários em tests/test_registro.py.

A aplicação web (web/app.py) usa exclusivamente banco de dados (SQLite/PostgreSQL)
e não importa este módulo.
"""


def bater_entrada(arquivo):
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")

    with open(arquivo, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([data, hora, "", ""])

    return True


def bater_saida(arquivo):
    agora = datetime.now()
    hora_saida = agora.strftime("%H:%M:%S")

    with open(arquivo, mode="r") as file:
        reader = list(csv.reader(file))

    horas = None

    for i in range(len(reader)-1, 0, -1):
        if reader[i][2] == "":
            horas = calcular_horas(reader[i][1], hora_saida)

            reader[i][2] = hora_saida
            reader[i][3] = str(horas)
            break

    if horas is None:
        return False, None

    with open(arquivo, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(reader)

    return True, horas


def calcular_horas(entrada_str, saida_str):
    entrada = datetime.strptime(entrada_str, "%H:%M:%S")
    saida = datetime.strptime(saida_str, "%H:%M:%S")
    return saida - entrada
