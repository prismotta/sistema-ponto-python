from src.registro import bater_entrada, bater_saida
from src.utils import inicializar_arquivo

def menu():
    while True:
        print("\n--- SISTEMA DE PONTO ---")
        print("1 - Bater Entrada")
        print("2 - Bater Saída")
        print("3 - Sair")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            bater_entrada()
        elif opcao == "2":
            bater_saida()
        elif opcao == "3":
            print("Encerrando sistema...")
            break
        else:
            print("Opção inválida!")

if __name__ == "__main__":
    inicializar_arquivo()
    menu()