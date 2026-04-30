import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.app import conectar, criar_banco, sql


def colunas_usuarios(cursor) -> set[str]:
    cursor.execute(sql("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='usuarios'
    """) if sql("?") == "%s" else "PRAGMA table_info(usuarios)")
    rows = cursor.fetchall()
    if rows and len(rows[0]) > 1:
        return {row[1] for row in rows}
    return {row[0] for row in rows}


def promover_admin(username: str | None, email: str | None) -> int:
    if not username and not email:
        print("Informe --username ou --email.", file=sys.stderr)
        return 2

    criar_banco()
    conn = conectar()
    cursor = conn.cursor()
    colunas = colunas_usuarios(cursor)

    if email:
        if "email" not in colunas:
            conn.close()
            print("A tabela usuarios nao possui coluna email.", file=sys.stderr)
            return 2
        filtro = "email=?"
        valor = email
    else:
        filtro = "username=?"
        valor = username

    cursor.execute(sql(f"UPDATE usuarios SET role='admin' WHERE {filtro}"), (valor,))
    alterados = cursor.rowcount
    conn.commit()

    cursor.execute(sql(f"SELECT id, username, role FROM usuarios WHERE {filtro}"), (valor,))
    usuario = cursor.fetchone()
    conn.close()

    if alterados != 1 or not usuario:
        print("Nenhum usuario encontrado para promocao.", file=sys.stderr)
        return 1

    print(f"Usuario promovido: id={usuario[0]} username={usuario[1]} role={usuario[2]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Promove um usuario existente para admin.")
    parser.add_argument("--username")
    parser.add_argument("--email")
    args = parser.parse_args()
    return promover_admin(args.username, args.email)


if __name__ == "__main__":
    raise SystemExit(main())
