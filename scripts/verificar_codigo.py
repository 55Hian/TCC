"""Verifica sintaxe, espaços finais e complexidade estrutural sem dependências extras."""
import argparse
import ast
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def medir_funcao(funcao):
    """Conta decisões sintáticas; não substitui uma medida formal de complexidade."""
    decisoes = 1
    for no in ast.walk(funcao):
        if isinstance(no, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
            decisoes += 1
        elif isinstance(no, ast.BoolOp):
            decisoes += len(no.values) - 1
        elif isinstance(no, ast.comprehension):
            decisoes += 1 + len(no.ifs)
    return {"decisoes": decisoes, "linhas": funcao.end_lineno - funcao.lineno + 1}


def inventariar():
    inventario = {}
    for pasta in ("backend/app", "scripts"):
        for caminho in sorted((RAIZ / pasta).rglob("*.py")):
            if "__pycache__" in caminho.parts:
                continue
            texto = caminho.read_text(encoding="utf-8-sig")
            arvore = ast.parse(texto, filename=str(caminho))
            funcoes = {}
            for no in arvore.body:
                if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcoes[no.name] = medir_funcao(no)
                elif isinstance(no, ast.ClassDef):
                    for metodo in no.body:
                        if isinstance(metodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            funcoes[f"{no.name}.{metodo.name}"] = medir_funcao(metodo)
            inventario[caminho.relative_to(RAIZ).as_posix()] = funcoes
    return inventario


def verificar_espacos():
    problemas = []
    for pasta in ("backend/app", "scripts", "frontend/js"):
        for caminho in (RAIZ / pasta).rglob("*"):
            if caminho.suffix not in (".py", ".js", ".cjs"):
                continue
            for numero, linha in enumerate(caminho.read_text(encoding="utf-8-sig").splitlines(), 1):
                if linha.rstrip() != linha or "\t" in linha[:len(linha) - len(linha.lstrip())]:
                    problemas.append(f"{caminho.relative_to(RAIZ)}:{numero}")
    return problemas


def verificar_limite(inventario, limite):
    """Limita decisões por função de produção; testes são medidos, mas não bloqueados."""
    problemas = []
    for caminho, funcoes in inventario.items():
        if "/tests/" in caminho or caminho.endswith("verificar_codigo.py"):
            continue
        for nome, medidas in funcoes.items():
            if medidas["decisoes"] > limite:
                problemas.append(f"{caminho}:{nome} ({medidas['decisoes']} > {limite})")
    return problemas


def main():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--registrar", type=Path, help="Salva o inventário em JSON.")
    argumentos.add_argument("--comparar", type=Path, help="Compara máximos por módulo com a referência.")
    argumentos.add_argument("--limite-decisoes", type=int, help="Falha se uma função de produção exceder o limite.")
    opcoes = argumentos.parse_args()
    atual = inventariar()
    problemas = verificar_espacos()
    if opcoes.limite_decisoes is not None:
        problemas.extend(verificar_limite(atual, opcoes.limite_decisoes))
    if problemas:
        raise SystemExit("Verificação reprovada: " + ", ".join(problemas))
    if opcoes.registrar:
        opcoes.registrar.write_text(json.dumps(atual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if opcoes.comparar:
        anterior = json.loads(opcoes.comparar.read_text(encoding="utf-8-sig"))
        for caminho, funcoes in anterior.items():
            if not funcoes or "/tests/" in caminho or caminho not in atual:
                continue
            antes = max(item["decisoes"] for item in funcoes.values())
            depois = max((item["decisoes"] for item in atual[caminho].values()), default=0)
            print(f"{caminho}: máximo de decisões {antes} -> {depois}")
    print(f"Sintaxe Python e espaços: OK ({len(atual)} arquivos Python).")


if __name__ == "__main__":
    main()
