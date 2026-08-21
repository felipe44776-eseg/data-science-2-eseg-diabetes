"""Observabilidade do pipeline: o que rodou, o que esta velho, o que falta.

Problema real: o projeto tem etapas caras (ler 1,17 GB de XPT, treinar a escada
de modelos) e artefatos espalhados. Sem isto, "ja rodei o EDA?" e "esse grafico
e da versao atual dos dados?" viram adivinhacao.

O DAG e declarado **uma vez** em `ETAPAS`. A partir dele, `status()` calcula:

  ausente    — a saida nao existe
  obsoleto   — alguma entrada e mais nova que a saida  (⚠ o caso perigoso)
  ok         — saida existe e e mais nova que tudo que a gerou

Uso:
    python -m diabetes.pipeline.estado            # tabela de status
    python -m diabetes.pipeline.estado --json     # para script
    python -m diabetes.pipeline.estado --execucoes  # historico do log
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
LOG_EXECUCAO = RAIZ / "reports" / "execucao.jsonl"

# hash completo so ate este tamanho; acima disso, amostragem (inicio+meio+fim)
LIMITE_HASH_COMPLETO = 50 * 1024 * 1024


@dataclass(frozen=True)
class Etapa:
    chave: str
    titulo: str
    comando: str
    entradas: tuple[str, ...]
    saidas: tuple[str, ...]
    opcional: bool = False          # nao bloqueia o pipeline se faltar
    nota: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


ETAPAS: list[Etapa] = [
    Etapa(
        "ingest", "Ingestao — PDF para CSV bronze",
        ".\\tasks.ps1 ingest",
        ("data/raw/Diabetes-2026.csv.pdf",),
        ("data/raw/diabetes_2026_raw.csv", "data/raw/_manifest_ingestao.json"),
        nota="4.374 paginas -> 253.680 linhas, por coordenada de bounding box",
    ),
    Etapa(
        "clean", "Limpeza — CSV para Parquet silver",
        ".\\tasks.ps1 clean",
        ("data/raw/diabetes_2026_raw.csv", "src/diabetes/schema.py"),
        ("data/processed/diabetes_silver.parquet", "data/processed/_relatorio_limpeza.json"),
        nota="7 regras rastreadas; nenhuma linha some em silencio",
    ),
    Etapa(
        "folds", "Particionamento a prova de vazamento",
        "python -m diabetes.features.split",
        ("data/processed/diabetes_silver.parquet", "src/diabetes/features/split.py"),
        ("data/processed/gold/folds.parquet",),
        nota="split aleatorio ingenuo vazaria 13,65% do teste",
    ),
    Etapa(
        "external", "BRFSS 2015 original — reconstrucao e vies",
        ".\\tasks.ps1 external",
        ("data/external/brfss2015/LLCP2015.XPT", "src/diabetes/external/brfss2015.py"),
        ("data/external/brfss2015/brfss2015_reconstruido.parquet",
         "data/external/brfss2015/_cascata_exclusoes.json",
         "data/external/brfss2015/_analise_vies.json"),
        nota="XPT de 1,17 GB fora do git — ver data/external/FONTES.md",
    ),
    Etapa(
        "eda", "EDA bivariada em base dupla",
        ".\\tasks.ps1 eda",
        ("data/processed/diabetes_silver.parquet", "data/external/brfss2015/LLCP2015.XPT",
         "src/diabetes/eda/associacao.py", "src/diabetes/eda/comparativo.py"),
        ("data/processed/gold/_eda_comparativa.json",),
    ),
    Etapa(
        "explicativo", "Modelo explicativo — M1/M2/M3",
        ".\\tasks.ps1 explicativo",
        ("data/processed/diabetes_silver.parquet", "data/external/brfss2015/LLCP2015.XPT",
         "src/diabetes/models/explicativo.py"),
        ("data/processed/gold/_modelo_explicativo.json",),
    ),
    Etapa(
        "figuras", "Figuras do relatorio",
        ".\\tasks.ps1 figuras",
        ("data/processed/gold/_eda_comparativa.json",
         "data/processed/gold/_modelo_explicativo.json",
         "data/external/brfss2015/_cascata_exclusoes.json",
         "src/diabetes/viz/figuras.py"),
        ("reports/figures/01-cascata-exclusoes.svg",
         "reports/figures/02-decomposicao-vies.svg",
         "reports/figures/03-forest-m1.svg",
         "reports/figures/04-gradientes.svg",
         "reports/figures/05-imc.svg",
         "reports/figures/06-pre-vs-diabetes.svg"),
    ),
    Etapa(
        "modelos", "Escada de modelos preditivos",
        ".\\tasks.ps1 modelos",
        ("data/processed/diabetes_silver.parquet", "data/processed/gold/folds.parquet",
         "src/diabetes/models/escada.py"),
        ("data/processed/gold/_escada_modelos.json",),
    ),
    Etapa(
        "vigitel", "Vigitel — comparacao binacional",
        ".\\tasks.ps1 vigitel",
        ("src/diabetes/external/vigitel.py",),
        ("data/external/vigitel/_comparacao_binacional.json",),
        opcional=True,
        nota="microdados do MS; ver data/external/FONTES.md",
    ),
    # --- expansoes (docs/10 a docs/14) ------------------------------------
    Etapa(
        "expandido", "Frente 1 — variaveis expandidas (69 curadas)",
        ".\\tasks.ps1 expandido",
        ("data/external/brfss2015/LLCP2015.XPT", "src/diabetes/features/expandido.py",
         "src/diabetes/models/expandido.py"),
        ("data/processed/gold/brfss_expandido.parquet",
         "data/processed/gold/_features_expandidas.json",
         "data/processed/gold/_frente1_expandido.json"),
        nota="+6,6% PR-AUC; o ganho e inteiramente das minorias",
    ),
    Etapa(
        "pesos", "Frente 5 — inferencia complexa e pesos publicaveis",
        ".\\tasks.ps1 pesos",
        ("data/processed/gold/brfss_expandido.parquet",
         "data/processed/diabetes_silver.parquet", "src/diabetes/external/pesos.py"),
        ("data/processed/gold/_frente5_pesos.json",
         "data/processed/gold/pesos_arquivo_entregue.parquet"),
        nota="raking remove 95,6% do vies com a margem de acesso",
    ),
    Etapa(
        "pu", "Frente 2 — Positive-Unlabeled",
        ".\\tasks.ps1 pu",
        ("data/processed/gold/brfss_expandido.parquet", "src/diabetes/models/pu.py"),
        ("data/processed/gold/_frente2_pu.json",),
        nota="BBE estima c=0,7283 contra 0,7240 do NHANES",
    ),
    Etapa(
        "glassbox", "Frente 3 — EBM e predicao conforme",
        ".\\tasks.ps1 glassbox",
        ("data/processed/gold/brfss_expandido.parquet",
         "src/diabetes/models/glassbox.py"),
        ("data/processed/gold/_frente3_glassbox.json",),
        nota="EBM com 12 vars = 94,4% do boosting com 60",
    ),
    Etapa(
        "medicaid", "Frente 4 — expansao do Medicaid (DiD)",
        ".\\tasks.ps1 medicaid",
        ("src/diabetes/external/medicaid.py",),
        ("data/external/medicaid/_frente4_medicaid.json",
         "data/external/medicaid/painel_brfss_estados.parquet"),
        opcional=True,
        nota="painel via data.cdc.gov; nao depende do XPT local",
    ),
    Etapa(
        "trilhac", "Trilha C — escore, decisao e equidade",
        ".\\tasks.ps1 trilhac",
        ("data/processed/gold/brfss_expandido.parquet",
         "src/diabetes/eval/escore.py", "src/diabetes/eval/decisao.py",
         "src/diabetes/eval/equidade.py"),
        ("data/processed/gold/_trilhaC_escore.json",
         "data/processed/gold/_trilhaC_decisao.json",
         "data/processed/gold/_trilhaC_equidade.json"),
        nota="escore de 5 perguntas bate o FINDRISC em +37,7 milesimos",
    ),
]


# --------------------------------------------------------------------------

def _hash_arquivo(p: Path) -> str:
    """SHA-256 completo em arquivo pequeno; amostrado em arquivo grande.

    Amostragem (inicio, meio, fim + tamanho) detecta troca de arquivo e
    truncamento sem ler 1,17 GB a cada `status`.
    """
    tam = p.stat().st_size
    h = hashlib.sha256()
    with p.open("rb") as fh:
        if tam <= LIMITE_HASH_COMPLETO:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
            return "sha256:" + h.hexdigest()[:16]
        bloco = 1 << 20
        for pos in (0, tam // 2, max(tam - bloco, 0)):
            fh.seek(pos)
            h.update(fh.read(bloco))
    h.update(str(tam).encode())
    return "amostra:" + h.hexdigest()[:16]


def _humano(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"


def _idade(ts: float) -> str:
    d = datetime.now() - datetime.fromtimestamp(ts)
    if d < timedelta(minutes=1):
        return "agora"
    if d < timedelta(hours=1):
        return f"{int(d.total_seconds() // 60)} min"
    if d < timedelta(days=1):
        return f"{int(d.total_seconds() // 3600)} h"
    return f"{d.days} d"


def inspecionar(caminho: str, raiz: Path = RAIZ) -> dict:
    p = raiz / caminho
    if not p.exists():
        return {"caminho": caminho, "existe": False}
    st = p.stat()
    return {
        "caminho": caminho,
        "existe": True,
        "bytes": st.st_size,
        "tamanho": _humano(st.st_size),
        "mtime": st.st_mtime,
        "modificado": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
        "idade": _idade(st.st_mtime),
        "hash": _hash_arquivo(p),
    }


def status(raiz: Path = RAIZ) -> list[dict]:
    """Estado de cada etapa: ausente, obsoleto ou ok."""
    linhas = []
    for e in ETAPAS:
        ent = [inspecionar(c, raiz) for c in e.entradas]
        sai = [inspecionar(c, raiz) for c in e.saidas]

        faltando_entrada = [i["caminho"] for i in ent if not i["existe"]]
        faltando_saida = [s["caminho"] for s in sai if not s["existe"]]

        if faltando_saida:
            estado = "ausente"
            motivo = f"{len(faltando_saida)} de {len(sai)} saidas nao existem"
        else:
            t_ent = max((i["mtime"] for i in ent if i["existe"]), default=0.0)
            t_sai = min(s["mtime"] for s in sai)
            desatualizadas = [i["caminho"] for i in ent
                              if i["existe"] and i["mtime"] > t_sai]
            if desatualizadas:
                estado = "obsoleto"
                motivo = f"entrada mais nova: {', '.join(desatualizadas[:2])}"
            else:
                estado = "ok"
                motivo = f"gerado {sai[0]['idade']} atras"
            del t_ent

        linhas.append({
            "chave": e.chave, "titulo": e.titulo, "comando": e.comando,
            "estado": estado, "motivo": motivo, "opcional": e.opcional,
            "nota": e.nota,
            "entradas_faltando": faltando_entrada,
            "entradas": ent, "saidas": sai,
        })
    return linhas


def proxima_etapa(linhas: list[dict]) -> dict | None:
    """Primeira etapa acionavel: precisa rodar e tem todas as entradas."""
    for ln in linhas:
        if ln["estado"] in ("ausente", "obsoleto") and not ln["entradas_faltando"]:
            return ln
    return None


# --- registro de execucao -------------------------------------------------

def registrar(etapa: str, evento: str, **extra) -> None:
    """Anexa uma linha ao log de execucao. Nunca levanta excecao."""
    try:
        LOG_EXECUCAO.parent.mkdir(parents=True, exist_ok=True)
        with LOG_EXECUCAO.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now().isoformat(timespec="seconds"),
                "etapa": etapa, "evento": evento, "pid": os.getpid(), **extra,
            }, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def execucoes(limite: int = 25) -> list[dict]:
    if not LOG_EXECUCAO.exists():
        return []
    linhas = LOG_EXECUCAO.read_text(encoding="utf-8").strip().splitlines()
    saida = []
    for ln in linhas[-limite:]:
        try:
            saida.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return saida


# --- apresentacao ---------------------------------------------------------

MARCA = {"ok": "[ok]     ", "obsoleto": "[OBSOLETO]", "ausente": "[ausente]"}


def imprimir(linhas: list[dict]) -> None:
    print("\nESTADO DO PIPELINE\n" + "=" * 78)
    for ln in linhas:
        opc = " (opcional)" if ln["opcional"] else ""
        print(f"{MARCA[ln['estado']]:11} {ln['chave']:12} {ln['titulo']}{opc}")
        print(f"{'':11} {'':12} {ln['motivo']}")
        if ln["entradas_faltando"]:
            print(f"{'':11} {'':12} BLOQUEADA — falta: {', '.join(ln['entradas_faltando'])}")
        for s in ln["saidas"]:
            if s["existe"]:
                print(f"{'':11} {'':12}   · {s['caminho']}  {s['tamanho']}  "
                      f"{s['modificado']}  {s['hash']}")

    print("=" * 78)
    conta = {e: sum(1 for ln in linhas if ln["estado"] == e)
             for e in ("ok", "obsoleto", "ausente")}
    print(f"ok: {conta['ok']}   obsoleto: {conta['obsoleto']}   ausente: {conta['ausente']}")

    obsoletas = [ln["chave"] for ln in linhas if ln["estado"] == "obsoleto"]
    if obsoletas:
        print(f"\nATENCAO — etapa(s) com entrada mais nova que a saida: {', '.join(obsoletas)}")
        print("Os artefatos existem mas nao refletem os dados atuais.")

    prox = proxima_etapa(linhas)
    if prox:
        print(f"\nPROXIMA: {prox['chave']} — {prox['titulo']}")
        print(f"         {prox['comando']}")
    else:
        pend = [ln for ln in linhas if ln["estado"] != "ok"]
        if pend:
            print("\nNenhuma etapa acionavel — todas as pendentes estao bloqueadas por "
                  "entrada ausente:")
            for ln in pend:
                print(f"  {ln['chave']}: falta {', '.join(ln['entradas_faltando'])}")
        else:
            print("\nPipeline completo e coerente.")


def imprimir_execucoes(regs: list[dict]) -> None:
    if not regs:
        print("Sem execucoes registradas em reports/execucao.jsonl")
        return
    print("\nULTIMAS EXECUCOES\n" + "=" * 78)
    for r in regs:
        dur = f"  {r['segundos']}s" if "segundos" in r else ""
        det = f"  {r.get('detalhe', '')}" if r.get("detalhe") else ""
        print(f"{r['ts']}  {r['etapa']:12} {r['evento']:10}{dur}{det}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="saida em JSON")
    ap.add_argument("--execucoes", action="store_true", help="historico do log")
    ap.add_argument("--limite", type=int, default=25)
    args = ap.parse_args()

    if args.execucoes:
        regs = execucoes(args.limite)
        print(json.dumps(regs, ensure_ascii=False, indent=2)) if args.json else imprimir_execucoes(regs)
        return

    linhas = status()
    if args.json:
        print(json.dumps(linhas, ensure_ascii=False, indent=2, default=str))
    else:
        imprimir(linhas)


if __name__ == "__main__":
    main()
