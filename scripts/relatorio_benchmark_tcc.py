"""Gera tabelas e curvas somente depois dos quatro benchmarks completos."""
import argparse
import csv
import json
from pathlib import Path

def formatar_numero(valor, casas_decimais=2):
    return f'{valor:.{casas_decimais}f}'.replace('.', ',')

def montar_tabela(cabecalhos, linhas):
    """Formata uma tabela Markdown preservando a ordem das colunas."""
    resultado = [
        "| " + " | ".join(cabecalhos) + " |",
        "| " + " | ".join(["---"] * len(cabecalhos)) + " |",
    ]
    for linha in linhas:
        resultado.append("| " + " | ".join(map(str, linha)) + " |")
    return "\n".join(resultado)


def salvar_curvas(out, histories, metric):
    """Gera a figura em modo não interativo, sem abrir janelas."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figura,eixo=plt.subplots(figsize=(9,5))
    for nome,historico in histories.items():
        eixo.plot([int(r['epoch']) for r in historico],[100*float(r[metric]) for r in historico],label=nome)
    eixo.axvline(20,color='gray',linestyle='--',linewidth=1)
    eixo.set(xlabel='Época',ylabel='mAP50–95 de validação (%)',title='Evolução dos quatro modelos — mesmo protocolo')
    eixo.legend()
    eixo.grid(alpha=.25)
    figura.tight_layout()
    figura.savefig(out/'curvas_map.png',dpi=220)
    plt.close(figura)

def montar_linhas(resultados, historicos, metrica):
    """Converte métricas para percentuais e compara os melhores valores por período."""
    linhas_principais = []
    linhas_epocas = []
    linhas_classes = []
    for resultado in resultados:
        nome = resultado["model"]
        percentuais = [
            formatar_numero(100 * resultado[chave])
            for chave in ("precision", "recall", "map50", "map50_95")
        ]
        linhas_principais.append([
            nome, str(resultado["epochs"]), str(resultado["best_csv_epoch"]),
            *percentuais, formatar_numero(resultado["training_seconds"] / 60),
        ])
        historico = historicos[nome]
        melhor_20 = max(float(linha[metrica]) for linha in historico[:20])
        melhor_50 = max(float(linha[metrica]) for linha in historico)
        linhas_epocas.append([
            nome, formatar_numero(100 * melhor_20), formatar_numero(100 * melhor_50),
            formatar_numero(100 * (melhor_50 - melhor_20)),
        ])
        for classe, valores in resultado["classes"].items():
            linhas_classes.append([nome, classe, *[formatar_numero(valor * 100) for valor in valores]])
    return linhas_principais, linhas_epocas, linhas_classes


def montar_relatorio(linhas_principais, linhas_epocas, linhas_classes):
    """Insere as tabelas no texto do protocolo preservado em um modelo Markdown."""
    caminho = Path(__file__).with_name("templates") / "relatorio_tcc.md"
    relatorio = caminho.read_text(encoding="utf-8")
    relatorio = relatorio.replace('{{TABELA_1}}', montar_tabela(['Modelo', 'Épocas', 'Melhor época (CSV)', 'Precisão (%)', 'Recall (%)', 'mAP50 (%)', 'mAP50–95 (%)', 'Tempo de treino (min)'], linhas_principais))
    relatorio = relatorio.replace('{{TABELA_2}}', montar_tabela(['Modelo', 'Melhor até 20 (%)', 'Melhor até 50 (%)', 'Ganho (p.p.)'], linhas_epocas))
    relatorio = relatorio.replace('{{TABELA_3}}', montar_tabela(['Modelo', 'Classe', 'Precisão (%)', 'Recall (%)', 'mAP50 (%)', 'mAP50–95 (%)'], linhas_classes))
    return relatorio


def _ler_historico(caminho):
    """Fecha o CSV mesmo se sua leitura falhar."""
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def main():
    argumentos=argparse.ArgumentParser()
    argumentos.add_argument('directory', type=Path)
    opcoes=argumentos.parse_args()
    pasta_saida=opcoes.directory.resolve()
    nomes=['yolov8n','yolo12n','yolo26s','yolo26m']
    resultados=[json.loads((pasta_saida/(nome+'_summary.json')).read_text(encoding='utf-8')) for nome in nomes]
    historicos = {nome: _ler_historico(pasta_saida / nome / 'results.csv') for nome in nomes}
    if any(len(linhas)!=50 for linhas in historicos.values()):
        raise RuntimeError('Todos os treinos devem ter 50 epocas completas')
    metrica='metrics/mAP50-95(B)'
    linhas_principais, linhas_epocas, linhas_classes = montar_linhas(resultados, historicos, metrica)
    with (pasta_saida/'comparativo_por_classe.csv').open('w',newline='',encoding='utf-8-sig') as f:
        gravador_csv=csv.writer(f,delimiter=';')
        gravador_csv.writerow(['Modelo','Classe','Precisao (%)','Recall (%)','mAP50 (%)','mAP50-95 (%)'])
        gravador_csv.writerows(linhas_classes)
    relatorio = montar_relatorio(linhas_principais, linhas_epocas, linhas_classes)
    (pasta_saida/'RELATORIO_TCC.md').write_text(relatorio,encoding='utf-8')
    salvar_curvas(pasta_saida, historicos, metrica)
    print(pasta_saida/'RELATORIO_TCC.md')



# Compatibilidade de importação com os nomes anteriores.
def number(value, digits=2):
    """Aceita os parâmetros nomeados da interface anterior."""
    return formatar_numero(value, digits)
def table(headers, rows):
    """Aceita os parâmetros nomeados da interface anterior."""
    return montar_tabela(headers, rows)

if __name__=='__main__':
    main()
