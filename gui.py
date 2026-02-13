import tkinter as tk
from tkinter import messagebox
from src.registro import bater_entrada, bater_saida
from src.utils import inicializar_arquivo

def registrar_entrada():
    sucesso = bater_entrada()
    if sucesso:
        messagebox.showinfo("Sucesso", "Entrada registrada com sucesso!")


def registrar_saida():
    sucesso, horas = bater_saida()

    if sucesso:
        messagebox.showinfo("Sucesso", f"Saída registrada!\nTotal: {horas}")
    else:
        messagebox.showwarning("Aviso", "Nenhuma entrada encontrada para registrar saída.")


def criar_interface():
    inicializar_arquivo()

    janela = tk.Tk()
    janela.title("Sistema de Ponto")
    janela.geometry("300x200")
    janela.resizable(False, False)

    titulo = tk.Label(janela, text="Sistema de Bater Ponto", font=("Arial", 14))
    titulo.pack(pady=15)

    btn_entrada = tk.Button(janela, text="Bater Entrada", width=20, command=registrar_entrada)
    btn_entrada.pack(pady=5)

    btn_saida = tk.Button(janela, text="Bater Saída", width=20, command=registrar_saida)
    btn_saida.pack(pady=5)

    btn_sair = tk.Button(janela, text="Sair", width=20, command=janela.quit)
    btn_sair.pack(pady=15)

    janela.mainloop()

if __name__ == "__main__":
    criar_interface()
