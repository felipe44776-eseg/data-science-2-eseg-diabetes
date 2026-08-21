# Dicionário de dados

Gerado de `src/diabetes/schema.py` — a fonte de verdade. Não editar à mão.

| pt-BR (origem) | canônico (projeto) | BRFSS 2015 | tipo | domínio | descrição |
|---|---|---|---|---|---|
| `Diabetes` | `diabetes` | `Diabetes_012` | ordinal | 0, 1, 2 | 0 sem diabetes (ou gestacional) · 1 pre-diabetes · 2 diabetes |
| `Hipertensão` | `hipertensao` | `HighBP` | binaria | 0, 1 | pressao alta diagnosticada |
| `Colesterol_Alto` | `colesterol_alto` | `HighChol` | binaria | 0, 1 | colesterol alto diagnosticado |
| `Exame_de_Colesterol` | `exame_colesterol` | `CholCheck` | binaria | 0, 1 | exame de colesterol nos ultimos 5 anos — PROXY DE ACESSO, nao de risco |
| `IMC` | `imc` | `BMI` | continua | 12–98 | indice de massa corporal, derivado de peso/altura AUTORRELATADOS |
| `Fumante` | `fumante` | `Smoker` | binaria | 0, 1 | >=100 cigarros na vida (medida de exposicao acumulada, nao de status atual) |
| `AVC` | `avc` | `Stroke` | binaria | 0, 1 | AVC ja informado por profissional |
| `Doença_ou_Ataque_Cardiaco` | `doenca_cardiaca` | `HeartDiseaseorAttack` | binaria | 0, 1 | DAC ou IAM |
| `Atividade_Fisica` | `atividade_fisica` | `PhysActivity` | binaria | 0, 1 | atividade fisica nos ultimos 30 dias, excluindo trabalho |
| `Frutas` | `frutas` | `Fruits` | binaria | 0, 1 | frutas >=1x/dia |
| `Vegetais` | `vegetais` | `Veggies` | binaria | 0, 1 | vegetais >=1x/dia |
| `Consumo_Excessivo_de_Alcool` | `alcool_excessivo` | `HvyAlcoholConsump` | binaria | 0, 1 | H >14 doses/sem, M >7 doses/sem |
| `Acesso_a_Serviços_de_Saude` | `acesso_saude` | `AnyHealthcare` | binaria | 0, 1 | possui cobertura de saude |
| `Sem_Consulta_Medica_por_Custo` | `sem_consulta_por_custo` | `NoDocbcCost` | binaria | 0, 1 | deixou de consultar por custo nos ultimos 12 meses |
| `Saude_Geral` | `saude_geral` | `GenHlth` | ordinal | 1, 2, 3, 4, 5 | autoavaliacao 1 excelente .. 5 ruim |
| `Saude_Mental` | `saude_mental_dias` | `MentHlth` | contagem | 0–30 | dias ruins de saude mental nos ultimos 30 (zero-inflado) |
| `Saude_Fisica` | `saude_fisica_dias` | `PhysHlth` | contagem | 0–30 | dias ruins de saude fisica nos ultimos 30 (zero-inflado) |
| `Dificuldade_para_Caminhar` | `dificuldade_caminhar` | `DiffWalk` | binaria | 0, 1 | dificuldade seria para caminhar/subir escadas |
| `Sexo` | `sexo` | `Sex` | binaria | 0, 1 | 0 feminino · 1 masculino |
| `Idade` | `idade_faixa` | `Age` | ordinal | 1–13 | faixa etaria BRFSS em 13 niveis (1 = 18-24 ... 13 = 80+) |
| `Escolaridade` | `escolaridade` | `Education` | ordinal | 1, 2, 3, 4, 5, 6 | 1 nenhuma .. 6 superior completo |
| `Renda` | `renda_faixa` | `Income` | ordinal | 1, 2, 3, 4, 5, 6, 7, 8 | faixa de renda anual USD, 1 (<10k) .. 8 (>=75k); 77/99 = nao sabe/recusou |

## Colunas derivadas (camada silver)

| coluna | origem |
|---|---|
| `idade_anos` | ponto médio da faixa etária BRFSS |
| `renda_usd` | ponto médio da faixa de renda (USD/ano) |
| `imc_faixa_oms` | classificação OMS: baixo peso → obesidade III |
| `comorbidades` | soma de hipertensão + colesterol alto + AVC + doença cardíaca (0–4) |
| `dias_ruins_total` | saúde mental + saúde física, limitado a 60 |
| `habitos_saudaveis` | atividade física + frutas + vegetais + não-fumante + sem álcool excessivo (0–5) |
| `flag_duplicata_exata` | linha idêntica a outra em todas as 22 colunas |
| `flag_alvo_conflitante` | mesmas 21 features com alvo divergente |
| `flag_imc_extremo` | IMC > 60 (implausibilidade fisiológica, marcado não removido) |

## Blocos de variáveis (uso em modelagem)

| bloco | colunas | por quê |
|---|---|---|
| `PROXIES_DE_ACESSO` | exame_colesterol, acesso_saude, sem_consulta_por_custo | marcadores de detecção, não de risco |
| `POSSIVEIS_CONSEQUENCIAS` | saude_geral, dificuldade_caminhar, saude_fisica_dias | possível mediador/colisor do desfecho |
| `ATRIBUTOS_SENSIVEIS` | sexo, renda_faixa, escolaridade, idade_faixa | auditoria de viés (fairlearn) |
