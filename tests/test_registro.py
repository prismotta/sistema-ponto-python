from src.registro import calcular_horas

def test_calculo_horas_basico():
    entrada = "09:00:00"
    saida = "10:30:00"
    resultado = calcular_horas(entrada, saida)
    
    assert str(resultado) == "1:30:00"

def test_calculo_horas_zero():
    entrada = "09:00:00"
    saida = "09:00:00"
    resultado = calcular_horas(entrada, saida)
    
    assert str(resultado) == "0:00:00"

import os
from src.registro import bater_entrada, bater_saida
from src.utils import inicializar_arquivo


def test_bater_entrada_cria_arquivo(tmp_path):
    arquivo = tmp_path / "ponto.csv"

    inicializar_arquivo(arquivo)
    bater_entrada(arquivo)

    assert os.path.exists(arquivo)


def test_bater_saida_sem_entrada(tmp_path):
    arquivo = tmp_path / "ponto.csv"

    inicializar_arquivo(arquivo)

    resultado = bater_saida(arquivo)

    assert resultado == (False, None)

import csv

def test_fluxo_completo_entrada_saida(tmp_path):
    arquivo = tmp_path / "ponto.csv"

    # Inicializa arquivo
    inicializar_arquivo(arquivo)

    # Bate entrada
    bater_entrada(arquivo)

    # Bate saída
    sucesso, horas = bater_saida(arquivo)

    assert sucesso is True
    assert horas is not None

    # Verifica se o CSV foi atualizado
    with open(arquivo, mode="r") as file:
        linhas = list(csv.reader(file))

    # Deve ter header + 1 registro
    assert len(linhas) == 2

    # A coluna de saída deve estar preenchida
    assert linhas[1][2] != ""
