"""Reconstrucao das 22 colunas a partir do BRFSS 2015 original do CDC.

Objetivo: medir o vies introduzido pelo pre-processamento que gerou o arquivo
entregue pelo professor. O original tem 441.456 respondentes; recebemos 253.680.

A reconstrucao e declarativa (`REGRAS`) e **instrumentada**: cada regra registra
quantos registros derruba e quem sao. A saida nao e so o dataset -- e a
**cascata de exclusoes**, que e o objeto de analise.

Verificacao de integridade: se as regras reproduzirem exatamente 253.680 linhas
e a distribuicao do alvo bater com o arquivo entregue, a derivacao esta confirmada
e o espelho de download esta integro. E uma prova forte: uma corrupcao qualquer
faria a contagem divergir.

Uso:
    python -m diabetes.external.brfss2015 --xpt data/external/brfss2015/LLCP2015.XPT
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# --- variaveis de desenho amostral: descartadas pelo pre-processamento original ---
DESENHO = ["_LLCPWT", "_STSTR", "_PSU", "_STATE"]


@dataclass(frozen=True)
class Regra:
    """Derivacao de uma coluna do projeto a partir de uma variavel BRFSS."""

    destino: str                    # nome canonico no projeto
    origem: str                     # nome da variavel no BRFSS 2015
    descartar: tuple = ()           # codigos que eliminam o respondente
    recodificar: dict = field(default_factory=dict)  # de -> para
    dividir_por: float | None = None
    arredondar: bool = False
    nota: str = ""


REGRAS: list[Regra] = [
    Regra("diabetes", "DIABETE3", descartar=(7, 9),
          recodificar={1: 2, 2: 0, 3: 0, 4: 1},
          nota="1 sim -> 2 · 4 pre-diabetes -> 1 · 2 gestacional e 3 nao -> 0"),
    Regra("hipertensao", "_RFHYPE5", descartar=(9,), recodificar={1: 0, 2: 1}),
    Regra("colesterol_alto", "TOLDHI2", descartar=(7, 9), recodificar={2: 0}),
    Regra("exame_colesterol", "_CHOLCHK", descartar=(9,), recodificar={2: 0, 3: 0},
          nota="1 exame nos ultimos 5 anos · 2 (>5 anos) e 3 (nunca) -> 0"),
    Regra("imc", "_BMI5", dividir_por=100, arredondar=True,
          nota="_BMI5 vem com 2 casas implicitas"),
    Regra("fumante", "SMOKE100", descartar=(7, 9), recodificar={2: 0}),
    Regra("avc", "CVDSTRK3", descartar=(7, 9), recodificar={2: 0}),
    Regra("doenca_cardiaca", "_MICHD", recodificar={2: 0},
          nota="variavel ja calculada pelo CDC; nao tem codigo de recusa"),
    Regra("atividade_fisica", "_TOTINDA", descartar=(9,), recodificar={2: 0}),
    Regra("frutas", "_FRTLT1", descartar=(9,), recodificar={2: 0}),
    Regra("vegetais", "_VEGLT1", descartar=(9,), recodificar={2: 0}),
    Regra("alcool_excessivo", "_RFDRHV5", descartar=(9,), recodificar={1: 0, 2: 1}),
    Regra("acesso_saude", "HLTHPLN1", descartar=(7, 9), recodificar={2: 0}),
    Regra("sem_consulta_por_custo", "MEDCOST", descartar=(7, 9), recodificar={2: 0}),
    Regra("saude_geral", "GENHLTH", descartar=(7, 9)),
    Regra("saude_mental_dias", "MENTHLTH", descartar=(77, 99), recodificar={88: 0},
          nota="88 = nenhum dia -> 0"),
    Regra("saude_fisica_dias", "PHYSHLTH", descartar=(77, 99), recodificar={88: 0}),
    Regra("dificuldade_caminhar", "DIFFWALK", descartar=(7, 9), recodificar={2: 0}),
    Regra("sexo", "SEX", recodificar={2: 0}, nota="1 masculino · 2 feminino -> 0"),
    Regra("idade_faixa", "_AGEG5YR", descartar=(14,), nota="14 = nao sabe/recusou"),
    Regra("escolaridade", "EDUCA", descartar=(9,)),
    Regra("renda_faixa", "INCOME2", descartar=(77, 99),
          nota="77 nao sabe · 99 recusou — ESTA e a exclusao mais consequente"),
]

COLUNAS_BRFSS = [r.origem for r in REGRAS]


def carregar_xpt(xpt: Path, colunas: list[str] | None = None,
                 chunksize: int = 50_000) -> pd.DataFrame:
    """Le o XPT em blocos, mantendo apenas as colunas pedidas (o arquivo tem ~330)."""
    cols = colunas or (COLUNAS_BRFSS + DESENHO)
    partes = []
    with pd.read_sas(xpt, format="xport", chunksize=chunksize) as leitor:
        for bloco in leitor:
            presentes = [c for c in cols if c in bloco.columns]
            partes.append(bloco[presentes].copy())
    df = pd.concat(partes, ignore_index=True)
    ausentes = set(cols) - set(df.columns)
    if ausentes:
        raise KeyError(f"variaveis ausentes no XPT: {sorted(ausentes)}")
    return df


def reconstruir(bruto: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Aplica as regras registrando a cascata de exclusoes.

    Devolve (dataset_reconstruido, registros_excluidos_com_motivo, cascata).
    """
    vivo = pd.Series(True, index=bruto.index)
    motivo = pd.Series("", index=bruto.index, dtype=object)
    cascata: list[dict] = []
    n_ini = len(bruto)

    # etapa 0 — nulo em qualquer variavel usada
    nulo = bruto[COLUNAS_BRFSS].isna().any(axis=1)
    motivo[nulo & vivo] = "nulo"
    vivo &= ~nulo
    cascata.append({
        "etapa": 0, "regra": "—", "variavel": "(qualquer)", "criterio": "valor ausente",
        "excluidos": int(nulo.sum()), "restantes": int(vivo.sum()),
    })

    # etapas 1..N — codigos de nao-resposta, na ordem declarada
    for i, r in enumerate(REGRAS, start=1):
        if not r.descartar:
            cascata.append({
                "etapa": i, "regra": r.destino, "variavel": r.origem,
                "criterio": "—", "excluidos": 0, "restantes": int(vivo.sum()),
            })
            continue
        ruim = bruto[r.origem].isin(r.descartar) & vivo
        motivo[ruim] = f"{r.origem} in {list(r.descartar)}"
        vivo &= ~ruim
        cascata.append({
            "etapa": i, "regra": r.destino, "variavel": r.origem,
            "criterio": f"descarta {list(r.descartar)}",
            "excluidos": int(ruim.sum()), "restantes": int(vivo.sum()),
        })

    excluidos = bruto.loc[~vivo].copy()
    excluidos["motivo_exclusao"] = motivo.loc[~vivo]

    # aplica recodificacao apenas aos sobreviventes
    dados = bruto.loc[vivo].copy()
    out = pd.DataFrame(index=dados.index)
    for r in REGRAS:
        s = dados[r.origem]
        if r.dividir_por:
            s = s / r.dividir_por
        if r.arredondar:
            s = s.round()
        if r.recodificar:
            s = s.replace(r.recodificar)
        out[r.destino] = s.astype("uint8" if r.destino != "imc" else "uint8")
    for c in DESENHO:
        if c in dados.columns:
            out[c] = dados[c].values

    cascata.append({
        "etapa": "final", "regra": "—", "variavel": "—", "criterio": "—",
        "excluidos": int(n_ini - len(out)), "restantes": int(len(out)),
    })
    return out, excluidos, cascata


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xpt", type=Path, required=True)
    ap.add_argument("--saida", type=Path, default=Path("data/external/brfss2015/brfss2015_reconstruido.parquet"))
    ap.add_argument("--excluidos", type=Path, default=Path("data/external/brfss2015/brfss2015_excluidos.parquet"))
    ap.add_argument("--cascata", type=Path, default=Path("data/external/brfss2015/_cascata_exclusoes.json"))
    args = ap.parse_args()

    print("lendo XPT (1,17 GB, ~330 colunas -> mantendo 26)…")
    bruto = carregar_xpt(args.xpt)
    print(f"  respondentes no original: {len(bruto):,}")

    out, excluidos, cascata = reconstruir(bruto)
    print(f"  reconstruidos: {len(out):,} · excluidos: {len(excluidos):,}")

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.saida, index=False, compression="zstd")
    excluidos.to_parquet(args.excluidos, index=False, compression="zstd")
    args.cascata.write_text(
        json.dumps({"n_original": int(len(bruto)), "cascata": cascata},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(pd.DataFrame(cascata).to_string(index=False))


if __name__ == "__main__":
    main()
