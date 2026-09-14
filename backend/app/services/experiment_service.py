"""Localiza resultados e gráficos de treinos e benchmarks para a interface."""
from pathlib import Path
from core.config import settings


def listar_experimentos():
    from urllib.parse import quote
    experimentos = []
    origens = [(Path(settings.TRAINING_PROJECT), "/static/experiments"),
               (Path(settings.BENCHMARKS_DIR), "/static/benchmarks")]
    for raiz, url in origens:
        if not raiz.is_dir():
            continue
        for resultado in sorted(raiz.rglob("results.csv")):
            pasta = resultado.parent
            relativo = pasta.relative_to(raiz).as_posix()
            experimentos.append(dict(
                nome=relativo, tem_resultados=True,
                tem_pesos=(pasta / "weights" / "best.pt").is_file(),
                grafico_url=f"{url}/{quote(relativo, safe='/')}/results.png" if (pasta / "results.png").is_file() else None,
            ))
    return {"experimentos": experimentos}
