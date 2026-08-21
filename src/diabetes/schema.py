"""Contrato de dados unico do projeto.

Fonte de verdade para nomes, tipos, dominios validos e semantica das 22 colunas.
Todas as camadas (ingestao, limpeza, feature, modelo, relatorio) importam daqui.
Se o dado violar isto, o pipeline para -- nao remenda.

Referencia: BRFSS 2015 (CDC) + `docs/enunciado/Mapa-dos-dados.txt`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TARGET = "diabetes"  # nome canonico pos-normalizacao (snake_case)

#: nomes em pt-BR (como vieram no PDF) -> nome canonico BRFSS, para cruzar com a fonte oficial
PTBR_TO_BRFSS = {
    "Diabetes": "Diabetes_012",
    "Hipertensão": "HighBP",
    "Colesterol_Alto": "HighChol",
    "Exame_de_Colesterol": "CholCheck",
    "IMC": "BMI",
    "Fumante": "Smoker",
    "AVC": "Stroke",
    "Doença_ou_Ataque_Cardiaco": "HeartDiseaseorAttack",
    "Atividade_Fisica": "PhysActivity",
    "Frutas": "Fruits",
    "Vegetais": "Veggies",
    "Consumo_Excessivo_de_Alcool": "HvyAlcoholConsump",
    "Acesso_a_Serviços_de_Saude": "AnyHealthcare",
    "Sem_Consulta_Medica_por_Custo": "NoDocbcCost",
    "Saude_Geral": "GenHlth",
    "Saude_Mental": "MentHlth",
    "Saude_Fisica": "PhysHlth",
    "Dificuldade_para_Caminhar": "DiffWalk",
    "Sexo": "Sex",
    "Idade": "Age",
    "Escolaridade": "Education",
    "Renda": "Income",
}

#: nomes ASCII-safe usados internamente (evita acento em nome de coluna)
PTBR_TO_SNAKE = {
    "Diabetes": "diabetes",
    "Hipertensão": "hipertensao",
    "Colesterol_Alto": "colesterol_alto",
    "Exame_de_Colesterol": "exame_colesterol",
    "IMC": "imc",
    "Fumante": "fumante",
    "AVC": "avc",
    "Doença_ou_Ataque_Cardiaco": "doenca_cardiaca",
    "Atividade_Fisica": "atividade_fisica",
    "Frutas": "frutas",
    "Vegetais": "vegetais",
    "Consumo_Excessivo_de_Alcool": "alcool_excessivo",
    "Acesso_a_Serviços_de_Saude": "acesso_saude",
    "Sem_Consulta_Medica_por_Custo": "sem_consulta_por_custo",
    "Saude_Geral": "saude_geral",
    "Saude_Mental": "saude_mental_dias",
    "Saude_Fisica": "saude_fisica_dias",
    "Dificuldade_para_Caminhar": "dificuldade_caminhar",
    "Sexo": "sexo",
    "Idade": "idade_faixa",
    "Escolaridade": "escolaridade",
    "Renda": "renda_faixa",
}


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: str                       # binaria | ordinal | contagem | continua
    dominio: tuple | None           # valores admissiveis (None = intervalo)
    minimo: float | None = None
    maximo: float | None = None
    codigos_invalidos: tuple = ()    # 77 = "nao sabe", 99 = "recusou" (BRFSS)
    descricao: str = ""
    rotulos: dict = field(default_factory=dict)


BINARIA = (0, 1)

ESQUEMA: dict[str, Coluna] = {
    "diabetes": Coluna(
        "diabetes", "ordinal", (0, 1, 2),
        descricao="0 sem diabetes (ou gestacional) · 1 pre-diabetes · 2 diabetes",
        rotulos={0: "sem_diabetes", 1: "pre_diabetes", 2: "diabetes"},
    ),
    "hipertensao": Coluna("hipertensao", "binaria", BINARIA, descricao="pressao alta diagnosticada"),
    "colesterol_alto": Coluna("colesterol_alto", "binaria", BINARIA, descricao="colesterol alto diagnosticado"),
    "exame_colesterol": Coluna("exame_colesterol", "binaria", BINARIA,
                               descricao="exame de colesterol nos ultimos 5 anos — PROXY DE ACESSO, nao de risco"),
    "imc": Coluna("imc", "continua", None, minimo=12, maximo=98,
                  descricao="indice de massa corporal, derivado de peso/altura AUTORRELATADOS"),
    "fumante": Coluna("fumante", "binaria", BINARIA, descricao=">=100 cigarros na vida (medida de exposicao acumulada, nao de status atual)"),
    "avc": Coluna("avc", "binaria", BINARIA, descricao="AVC ja informado por profissional"),
    "doenca_cardiaca": Coluna("doenca_cardiaca", "binaria", BINARIA, descricao="DAC ou IAM"),
    "atividade_fisica": Coluna("atividade_fisica", "binaria", BINARIA, descricao="atividade fisica nos ultimos 30 dias, excluindo trabalho"),
    "frutas": Coluna("frutas", "binaria", BINARIA, descricao="frutas >=1x/dia"),
    "vegetais": Coluna("vegetais", "binaria", BINARIA, descricao="vegetais >=1x/dia"),
    "alcool_excessivo": Coluna("alcool_excessivo", "binaria", BINARIA,
                               descricao="H >14 doses/sem, M >7 doses/sem"),
    "acesso_saude": Coluna("acesso_saude", "binaria", BINARIA, descricao="possui cobertura de saude"),
    "sem_consulta_por_custo": Coluna("sem_consulta_por_custo", "binaria", BINARIA,
                                     descricao="deixou de consultar por custo nos ultimos 12 meses"),
    "saude_geral": Coluna("saude_geral", "ordinal", (1, 2, 3, 4, 5),
                          descricao="autoavaliacao 1 excelente .. 5 ruim",
                          rotulos={1: "excelente", 2: "muito_boa", 3: "boa", 4: "regular", 5: "ruim"}),
    "saude_mental_dias": Coluna("saude_mental_dias", "contagem", None, minimo=0, maximo=30,
                                descricao="dias ruins de saude mental nos ultimos 30 (zero-inflado)"),
    "saude_fisica_dias": Coluna("saude_fisica_dias", "contagem", None, minimo=0, maximo=30,
                                descricao="dias ruins de saude fisica nos ultimos 30 (zero-inflado)"),
    "dificuldade_caminhar": Coluna("dificuldade_caminhar", "binaria", BINARIA, descricao="dificuldade seria para caminhar/subir escadas"),
    "sexo": Coluna("sexo", "binaria", BINARIA, descricao="0 feminino · 1 masculino",
                   rotulos={0: "feminino", 1: "masculino"}),
    "idade_faixa": Coluna("idade_faixa", "ordinal", tuple(range(1, 14)),
                          descricao="faixa etaria BRFSS em 13 niveis (1 = 18-24 ... 13 = 80+)"),
    "escolaridade": Coluna("escolaridade", "ordinal", tuple(range(1, 7)),
                           descricao="1 nenhuma .. 6 superior completo"),
    "renda_faixa": Coluna("renda_faixa", "ordinal", tuple(range(1, 9)),
                          codigos_invalidos=(77, 99),
                          descricao="faixa de renda anual USD, 1 (<10k) .. 8 (>=75k); 77/99 = nao sabe/recusou"),
}

#: pontos medios das faixas etarias BRFSS, para converter ordinal -> anos (comparacao externa)
IDADE_PONTO_MEDIO = {
    1: 21, 2: 27, 3: 32, 4: 37, 5: 42, 6: 47, 7: 52,
    8: 57, 9: 62, 10: 67, 11: 72, 12: 77, 13: 85,
}

#: pontos medios das faixas de renda (USD/ano), para conversao a escala monetaria
RENDA_PONTO_MEDIO = {
    1: 5_000, 2: 12_500, 3: 17_500, 4: 22_500,
    5: 30_000, 6: 42_500, 7: 62_500, 8: 90_000,
}

COLUNAS = list(ESQUEMA)
BINARIAS = [c for c, m in ESQUEMA.items() if m.tipo == "binaria"]
ORDINAIS = [c for c, m in ESQUEMA.items() if m.tipo == "ordinal" and c != TARGET]
CONTAGENS = [c for c, m in ESQUEMA.items() if m.tipo == "contagem"]
CONTINUAS = [c for c, m in ESQUEMA.items() if m.tipo == "continua"]

#: variaveis que NAO sao fator de risco, mas marcadores de acesso/uso do sistema de saude.
#: Usar como preditor infla a performance e produz um modelo que aprende "quem foi diagnosticado",
#: nao "quem tem a doenca". Devem entrar em bloco separado e ser reportadas a parte.
PROXIES_DE_ACESSO = ["exame_colesterol", "acesso_saude", "sem_consulta_por_custo"]

#: variaveis potencialmente pos-tratamento / consequencia (colisor ou mediador do desfecho).
#: Entram no modelo preditivo, mas nao em modelo causal ingenuo.
POSSIVEIS_CONSEQUENCIAS = ["saude_geral", "dificuldade_caminhar", "saude_fisica_dias"]

#: atributos sensiveis para auditoria de vies
ATRIBUTOS_SENSIVEIS = ["sexo", "renda_faixa", "escolaridade", "idade_faixa"]
