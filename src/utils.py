import os
import csv


def inicializar_arquivo(arquivo):
    pasta = os.path.dirname(arquivo)

    if pasta:
        os.makedirs(pasta, exist_ok=True)

    if not os.path.exists(arquivo):
        with open(arquivo, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Data", "Entrada", "Saida", "Horas Trabalhadas"])
