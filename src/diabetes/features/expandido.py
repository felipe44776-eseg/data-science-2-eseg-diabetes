"""Conjunto expandido de variaveis do BRFSS 2015.

Motivo da decisao
-----------------
`docs/08` §2.3 mostrou que o teto do modelo nao e o ruido de rotulo (que limita a
acuracia a 99,3%) nem o algoritmo (a escada inteira rendeu +0,036 de PR-AUC).
Um teste rapido com todas as colunas numericas rendeu **+0,049 de PR-AUC** — mais
que a escada inteira. O gargalo e **informacao**, e o pre-processamento que gerou
o arquivo entregue jogou fora tres tipos dela:

  1. **resolucao** — idade virou 13 faixas (havia `_AGE80` continuo), alcool virou
     binario (havia `DROCDY3_` doses/dia), peso e altura sumiram dentro do IMC;
  2. **dominios inteiros** — comorbidades (rim, artrite, DPOC, asma, cancer,
     depressao), limitacao funcional, aptidao fisica, situacao de emprego;
  3. **raca/etnia** — ausente das 22. Numa analise de desigualdade em saude nos
     EUA isso nao e lacuna, e defeito.

Por que curadoria e nao "todas as 133 colunas"
----------------------------------------------
Jogar 133 colunas no modelo mede o teto, mas nao produz analise: mistura preditor
com marcador de deteccao, duplica a mesma informacao em tres codificacoes
(`_BMI5`, `_BMI5CAT`, `_RFBMI5`) e impede qualquer leitura por bloco. Aqui as
variaveis sao **nomeadas, agrupadas por dominio e justificadas**, mantendo a
separacao que o projeto ja usa: risco vs. deteccao vs. atributo sensivel.

Cuidado com vazamento
---------------------
`VAZAMENTO` lista tudo que decorre do proprio diagnostico de diabetes — idade do
diagnostico, uso de insulina, exame de HbA1c, exame de pe, exame de fundo de olho.
Incluir qualquer uma produz um modelo com AUC quase perfeito e valor zero.

Uso:
    python -m diabetes.features.expandido --xpt data/external/brfss2015/LLCP2015.XPT
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from diabetes.external.brfss2015 import REGRAS

ALVO = "DIABETE3"

#: decorrentes do proprio diagnostico — nunca entram como preditor
VAZAMENTO = re.compile(
    r"^(DIABETE3|DIABAGE2|PDIABTST|PREDIAB1|INSULIN|FEETCHK2?|DOCTDIAB|"
    r"CHKHEMO3|EYEEXAM|DIABEYE|DIABEDU)$", re.I)

#: desenho amostral e metadados de coleta — nunca sao preditor
DESENHO = ["_LLCPWT", "_STSTR", "_PSU", "_RAWRAKE", "_WT2RAKE", "_STRWT",
           "SEQNO", "DISPCODE", "FMONTH", "QSTVER", "PAMISS1_", "_STATE"]


# --------------------------------------------------------------------------
# blocos
# --------------------------------------------------------------------------

DEMOGRAFIA = {
    "_AGE80": "idade em anos, truncada em 80 — RECUPERA a resolucao perdida na faixa de 13 niveis",
    "SEX": "sexo",
    "EDUCA": "escolaridade em 6 niveis",
    "INCOME2": "faixa de renda anual",
    "EMPLOY1": "situacao de emprego — NOVO",
    "MARITAL": "estado civil — NOVO",
    "RENTHOM1": "casa propria, alugada ou outro — proxy de riqueza, NOVO",
    "_CHLDCNT": "criancas no domicilio — NOVO",
    "VETERAN3": "veterano — acesso ao sistema VA, NOVO",
    "INTERNET": "usou internet nos ultimos 30 dias — proxy socioeconomico e de acesso, NOVO",
    "QSTLANG": "idioma da entrevista — proxy de imigracao recente, NOVO",
}

#: bloco separado: e o atributo sensivel mais critico e estava totalmente ausente
RACA = {
    "_RACEGR3": "raca/etnia em 5 grupos (categoria de analise padrao do CDC) — NOVO",
    "_HISPANC": "origem hispanica — NOVO",
}

ANTROPOMETRIA = {
    "_BMI5": "IMC x 100",
    "WTKG3": "peso em kg x 100 — RECUPERA o componente que o IMC agrega, NOVO",
    "HTM4": "altura em cm — NOVO",
}

COMORBIDADES = {
    "_RFHYPE5": "hipertensao diagnosticada",
    "TOLDHI2": "colesterol alto diagnosticado",
    "_MICHD": "infarto ou doenca arterial coronariana",
    "CVDSTRK3": "AVC",
    "CHCKIDNY": "doenca renal — NOVO, aparece no top-5 de importancia",
    "HAVARTH3": "artrite — NOVO",
    "CHCCOPD1": "DPOC — NOVO",
    "ASTHMA3": "asma — NOVO",
    "CHCOCNCR": "cancer (exceto pele) — NOVO",
    "CHCSCNCR": "cancer de pele — NOVO",
    "ADDEPEV2": "depressao diagnosticada — NOVO, comorbidade metabolica conhecida",
}

LIMITACAO_FUNCIONAL = {
    "DIFFWALK": "dificuldade para caminhar ou subir escadas",
    "BLIND": "cego ou dificuldade seria de visao — NOVO",
    "DECIDE": "dificuldade de concentracao ou decisao — NOVO",
    "DIFFDRES": "dificuldade para se vestir ou tomar banho — NOVO",
    "DIFFALON": "dificuldade para fazer tarefas sozinho — NOVO",
    "USEEQUIP": "usa equipamento especial por problema de saude — NOVO",
    "QLACTLM2": "limitacao de atividade por problema de saude — NOVO",
}

ATIVIDADE_FISICA = {
    "_TOTINDA": "praticou atividade fisica nos ultimos 30 dias",
    "_PACAT1": "categoria de atividade fisica em 4 niveis — RECUPERA resolucao, NOVO",
    "_PA150R2": "atingiu 150 min/semana de atividade aerobica — NOVO",
    "MAXVO2_": "VO2 maximo estimado — aptidao cardiorrespiratoria, NOVO",
    "_PASTRNG": "atingiu a recomendacao de fortalecimento muscular — NOVO",
    "STRFREQ_": "frequencia de exercicio de forca por semana — NOVO",
}

DIETA = {
    "_FRTLT1": "fruta >= 1x/dia",
    "_VEGLT1": "vegetais >= 1x/dia",
    "FRUTDA1_": "porcoes de fruta por dia — RECUPERA a contagem que o binario perdeu, NOVO",
    "VEGEDA1_": "porcoes de vegetais por dia — NOVO",
    "FTJUDA1_": "suco de fruta por dia — NOVO, aparece no top-10 de importancia",
    "BEANDAY_": "feijao por dia — NOVO",
    "GRENDAY_": "verdura verde-escura por dia — NOVO",
    "ORNGDAY_": "vegetal alaranjado por dia — NOVO",
}

ALCOOL = {
    "_RFDRHV5": "consumo excessivo cronico",
    "DROCDY3_": "doses por dia — RECUPERA a quantidade, NOVO",
    "_DRNKWEK": "doses por semana — NOVO",
    "_RFBING5": "episodio de binge — construto distinto do consumo cronico, NOVO",
    "DRNKANY5": "bebeu nos ultimos 30 dias — NOVO",
}

TABACO = {
    "SMOKE100": ">= 100 cigarros na vida",
    "_SMOKER3": "status de tabagismo em 4 niveis — RECUPERA resolucao, NOVO",
    "USENOW3": "tabaco sem fumaca — NOVO",
}

SAUDE_PERCEBIDA = {
    "GENHLTH": "autoavaliacao de saude, 1 a 5",
    "MENTHLTH": "dias ruins de saude mental nos ultimos 30",
    "PHYSHLTH": "dias ruins de saude fisica nos ultimos 30",
}

OUTROS = {
    "SEATBELT": "uso de cinto de seguranca — proxy de aversao a risco, NOVO",
}

#: MARCADORES DE DETECCAO, nao de risco. Mesmo papel de `schema.PROXIES_DE_ACESSO`:
#: predizem quem foi diagnosticado, nao quem tem a doenca. Bloco separado, sempre.
ACESSO_E_DETECCAO = {
    "HLTHPLN1": "possui cobertura de saude",
    "MEDCOST": "deixou de consultar por custo",
    "CHOLCHK": "quando fez o ultimo exame de colesterol",
    "BLOODCHO": "ja fez exame de colesterol alguma vez — NOVO",
    "CHECKUP1": "tempo desde o ultimo check-up de rotina — NOVO",
    "PERSDOC2": "possui medico de referencia — NOVO",
    "FLUSHOT6": "vacina da gripe nos ultimos 12 meses — NOVO",
    "PNEUVAC3": "ja tomou vacina pneumococica — NOVO, top-10 de importancia",
    "HIVTST6": "ja fez teste de HIV — NOVO",
}

BLOCOS: dict[str, dict[str, str]] = {
    "demografia": DEMOGRAFIA,
    "raca": RACA,
    "antropometria": ANTROPOMETRIA,
    "comorbidades": COMORBIDADES,
    "limitacao_funcional": LIMITACAO_FUNCIONAL,
    "atividade_fisica": ATIVIDADE_FISICA,
    "dieta": DIETA,
    "alcool": ALCOOL,
    "tabaco": TABACO,
    "saude_percebida": SAUDE_PERCEBIDA,
    "outros": OUTROS,
    "acesso_e_deteccao": ACESSO_E_DETECCAO,
}

#: bloco de risco: tudo menos os marcadores de deteccao
RISCO = [c for b, d in BLOCOS.items() if b != "acesso_e_deteccao" for c in d]
DETECCAO = list(ACESSO_E_DETECCAO)
TODAS = RISCO + DETECCAO

#: as 21 originais, para a comparacao "antes e depois"
ORIGINAIS = ["_RFHYPE5", "TOLDHI2", "_CHOLCHK", "_BMI5", "SMOKE100", "CVDSTRK3",
             "_MICHD", "_TOTINDA", "_FRTLT1", "_VEGLT1", "_RFDRHV5", "HLTHPLN1",
             "MEDCOST", "GENHLTH", "MENTHLTH", "PHYSHLTH", "DIFFWALK", "SEX",
             "_AGEG5YR", "EDUCA", "INCOME2"]

#: atributos sensiveis para auditoria de vies — agora com raca
SENSIVEIS = ["_RACEGR3", "_HISPANC", "SEX", "INCOME2", "EDUCA", "_AGE80"]

#: codigos de nao-resposta comuns no BRFSS. Viram NaN: o gradient boosting trata
#: ausente nativamente, e 7/9 como numero seria um valor 7x maior que "sim"=1.
NAO_RESPOSTA = {7, 9, 77, 99, 777, 999, 7777, 9999, 99900}

#: Variaveis em que 7 e/ou 9 sao CATEGORIA VALIDA, nao nao-resposta.
#:
#: A mascara generica acima apagava, sem registrar nada: `_AGEG5YR` 7 (50-54 anos)
#: e 9 (60-64) — 87.806 pessoas; `EMPLOY1` 7 (aposentado) — 129.290; `INCOME2` 7
#: (US$ 50-75 mil) — 57.166. Nas tres, o codigo realmente invalido e outro. Havia
#: uma guarda para isso e ela era codigo morto: `limite = 4 if nome in (...)`
#: seguido de `return v if limite is None else v` devolve o mesmo objeto nos dois
#: ramos, e `INCOME2` sequer estava na lista.
#:
#: Os dois primeiros saem de `REGRAS` em vez de serem redigitados: a regra certa
#: ja existia la (`descartar=(14,)`, `descartar=(77, 99)`) e o trilho expandido a
#: contradizia — violacao do invariante 1. `EMPLOY1` nao esta em `REGRAS` porque
#: nao e uma das 21 colunas originais, entao fica explicito aqui.
#:
#: Vale tambem para 2023: `external/temporal.py` renomeia `INCOME3` para
#: `INCOME2`, e la 9 = 100-150k — outra categoria valida que a mascara comia.
NAO_RESPOSTA_PROPRIA: dict[str, set[float]] = {
    r.origem: set(r.descartar) for r in REGRAS if r.origem in ("_AGEG5YR", "INCOME2")
} | {"EMPLOY1": {9}}


def _limpar_codigos(s: pd.Series, nome: str) -> pd.Series:
    """Manda codigo de nao-resposta para NaN, respeitando a escala de cada variavel."""
    v = s.astype("float32")
    if nome in ("MENTHLTH", "PHYSHLTH"):
        return v.replace({88: 0}).mask(v.isin([77, 99]))
    if nome in ("_AGE80", "_BMI5", "WTKG3", "HTM4", "MAXVO2_", "FRUTDA1_", "VEGEDA1_",
                "FTJUDA1_", "BEANDAY_", "GRENDAY_", "ORNGDAY_", "DROCDY3_",
                "_DRNKWEK", "STRFREQ_"):
        # continuas ja calculadas pelo CDC: nao-resposta vem como codigo alto
        return v.mask(v >= 99900)
    if nome in ("ALCDAY5", "CHILDREN", "STRENGTH"):
        return v.mask(v.isin([777, 888, 999]))
    if nome in NAO_RESPOSTA_PROPRIA:
        return v.mask(v.isin(NAO_RESPOSTA_PROPRIA[nome]))
    return v.mask(v.isin(NAO_RESPOSTA))


def construir(xpt: Path) -> tuple[pd.DataFrame, dict]:
    """Le o XPT e devolve a matriz expandida + alvo + desenho amostral."""
    necessarias = set(TODAS) | set(ORIGINAIS) | set(DESENHO) | {ALVO}
    partes = []
    with pd.read_sas(xpt, format="xport", chunksize=60_000) as leitor:
        for bloco in leitor:
            presentes = [c for c in bloco.columns if c in necessarias]
            partes.append(bloco[presentes].copy())
    bruto = pd.concat(partes, ignore_index=True)

    faltando = necessarias - set(bruto.columns)
    if faltando:
        raise KeyError(f"variaveis ausentes no XPT: {sorted(faltando)}")
    for c in bruto.columns:
        if VAZAMENTO.match(c) and c != ALVO:
            raise AssertionError(f"variavel de vazamento no conjunto: {c}")

    # alvo: 1 = sim · 3 = nao · 2 = gestacional (-> nao) · 4 = pre-diabetes (excluido)
    d = bruto[bruto[ALVO].isin([1, 2, 3])].copy()
    alvo = (d[ALVO] == 1).astype("int8")

    X = pd.DataFrame(index=d.index)
    for c in TODAS:
        X[c] = _limpar_codigos(d[c], c)

    # originais na mesma limpeza, para comparacao justa
    orig = pd.DataFrame(index=d.index)
    for c in ORIGINAIS:
        orig[c] = _limpar_codigos(d[c], c)

    desenho = d[DESENHO].copy()

    rel = {
        "n": int(len(d)),
        "prevalencia": round(float(alvo.mean()), 4),
        "n_variaveis_expandido": len(TODAS),
        "n_variaveis_original": len(ORIGINAIS),
        "novas": sorted(set(TODAS) - set(ORIGINAIS)),
        "por_bloco": {b: len(v) for b, v in BLOCOS.items()},
        "missing_medio_expandido": round(float(X.isna().mean().mean()), 4),
        "variaveis_com_missing_alto": {
            c: round(float(v), 3) for c, v in X.isna().mean().items() if v > 0.15},
    }
    return pd.concat([X, orig.add_suffix("__orig"), desenho,
                      alvo.rename("diabetes")], axis=1), rel


def main() -> None:
    """Constroi o conjunto expandido a partir do XPT e grava `gold/brfss_expandido.parquet`."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xpt", type=Path,
                    default=Path("data/external/brfss2015/LLCP2015.XPT"))
    ap.add_argument("--saida", type=Path,
                    default=Path("data/processed/gold/brfss_expandido.parquet"))
    ap.add_argument("--relatorio", type=Path,
                    default=Path("data/processed/gold/_features_expandidas.json"))
    args = ap.parse_args()

    df, rel = construir(args.xpt)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.saida, index=False, compression="zstd")
    args.relatorio.write_text(json.dumps(rel, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(json.dumps({k: v for k, v in rel.items() if k != "novas"},
                     ensure_ascii=False, indent=2))
    print(f"\n{len(rel['novas'])} variaveis novas em relacao as 21 do trabalho")
    print(f"saida: {args.saida}  ({df.shape[0]:,} x {df.shape[1]})")


if __name__ == "__main__":
    main()
