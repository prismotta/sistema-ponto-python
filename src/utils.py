import os
import csv

ARQUIVO = "data/ponto.csv"

def inicializar_arquivo():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(ARQUIVO):
        with open(ARQUIVO, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Data", "Entrada", "Saida", "Horas Trabalhadas"])
