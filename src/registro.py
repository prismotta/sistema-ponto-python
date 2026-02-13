import csv
from datetime import datetime
from src.utils import ARQUIVO

def bater_entrada():
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")

    with open(ARQUIVO, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([data, hora, "", ""])

    print(f"✅ Entrada registrada às {hora}")

def bater_saida():
    agora = datetime.now()
    hora_saida = agora.strftime("%H:%M:%S")

    with open(ARQUIVO, mode="r") as file:
        reader = list(csv.reader(file))

    horas = None

    for i in range(len(reader)-1, 0, -1):
        if reader[i][2] == "":
            horas = calcular_horas(reader[i][1], hora_saida)

            reader[i][2] = hora_saida
            reader[i][3] = str(horas)
            break

    if horas is None:
        print("⚠️ Nenhuma entrada encontrada para registrar saída.")
        return

    with open(ARQUIVO, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(reader)

    print(f"✅ Saída registrada às {hora_saida}")
    print(f"🕒 Total trabalhado: {horas}")

def calcular_horas(entrada_str, saida_str):
    entrada = datetime.strptime(entrada_str, "%H:%M:%S")
    saida = datetime.strptime(saida_str, "%H:%M:%S")
    return saida - entrada
