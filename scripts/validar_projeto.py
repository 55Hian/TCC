"""Executa verificações locais, testes Python e testes da interface sem iniciar hardware."""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def executar(comando):
    print("Executando: " + " ".join(map(str, comando)), flush=True)
    subprocess.run(comando, cwd=RAIZ, check=True)


def main():
    executar([sys.executable, "-B", "scripts/verificar_codigo.py", "--limite-decisoes", "15"])
    for caminho in sorted((RAIZ / "frontend/js").glob("*.js")):
        executar(["node", "--check", str(caminho)])
    executar([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not hardware"])
    testes = sorted((RAIZ / "frontend/tests").glob("*.test.cjs"))
    executar(["node", "--test", *map(str, testes)])


if __name__ == "__main__":
    main()
