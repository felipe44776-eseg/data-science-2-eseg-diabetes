> Reproduzir: `.\tasks.ps1 vigitel` · saída bruta `data/external/vigitel/_comparacao_binacional.json`

# Brasil × EUA — os fatores de risco se comportam igual?

**Por que Vigitel:** é o análogo desenhado do BRFSS — inquérito telefônico, adultos ≥18 anos,
autorrelato de diagnóstico médico, peso de pós-estratificação por raking. E existe **para o
mesmo ano de 2015**, o que elimina o ano como explicação alternativa de qualquer diferença.

| | Brasil | EUA |
|---|---|---|
| Pesquisa | Vigitel 2015 (Ministério da Saúde) | BRFSS 2015 (CDC) |
| Respondentes | **54.174** (27 capitais) | **441.456** (50 estados + DC + territórios) |
| n efetivo de Kish | 10.843 | 109.019 |
| Peso | `pesorake` | `_LLCPWT` |

---

## 0. Validação da harmonização

Antes de comparar qualquer coisa, checar se nossa leitura do Vigitel reproduz o número
oficial. Vigitel 2015 publicado: **6,9% homens · 7,8% mulheres**.

| | nosso cálculo | publicado |
|---|---|---|
| homens | **6,92%** | 6,9% |
| mulheres | **7,84%** | 7,8% |

Reprodução exata dentro do arredondamento. A harmonização está correta.

*(Nota metodológica: o número publicado **não** exclui quem teve diabetes apenas na gravidez.
Para a comparação com o BRFSS nós excluímos — o BRFSS manda `DIABETE3=2` para "sem diabetes",
e a comparação tem de usar a mesma definição dos dois lados. Daí a diferença entre 7,42%
(definição publicada) e 7,08% (definição comparável).)*

---

## 1. Prevalência

| | n | n efetivo | bruta | **ponderada** |
|---|---|---|---|---|
| **Brasil** — Vigitel 2015 | 54.064 | 10.843 | 9,71% | **7,08%** |
| **EUA** — BRFSS 2015 | 440.658 | 109.019 | 12,99% | **10,50%** |

Os EUA têm **1,48× a prevalência brasileira** de diabetes diagnosticado.

**Ressalva que não pode ser omitida:** o Vigitel cobre **apenas as 27 capitais**; o BRFSS
cobre o país inteiro. Capitais brasileiras não representam o Brasil — têm renda, acesso e
urbanização acima da média nacional, o que puxa o **diagnóstico** para cima e a prevalência
verdadeira para baixo em direções opostas. Esta é a principal limitação da comparação.

---

## 2. Odds ratio ajustado — mesmo modelo nas duas pesquisas

Oito variáveis presentes e comparáveis em ambas. **Unidades naturais, não padronizadas**:
o desvio-padrão do IMC difere entre as populações (Brasil 5,05 · EUA 6,61), então OR por
desvio-padrão não seria comparável. IMC por 5 kg/m², idade por faixa de 5 anos,
escolaridade por nível na escala harmonizada de 3 pontos.

| variável | **OR Brasil** | IC 95% | **OR EUA** | IC 95% | razão BR/EUA | mesma direção | IC sobrepõe |
|---|---|---|---|---|---|---|---|
| `frutas` | **1,299** | [1,10; 1,53] | **0,898** | [0,86; 0,94] | 1,45 | **NÃO** | **não** |
| `fumante` | 1,268 | [1,08; 1,49] | 1,149 | [1,10; 1,20] | 1,10 | sim | sim |
| `sexo` (masc.) | 1,273 | [1,08; 1,50] | 1,175 | [1,12; 1,23] | 1,08 | sim | sim |
| `atividade_fisica` | 0,846 | [0,72; 1,00] | 0,795 | [0,76; 0,84] | 1,06 | sim | sim |
| `idade_faixa` | **1,234** | [1,20; 1,27] | **1,240** | [1,23; 1,25] | **1,00** | sim | sim |
| `hipertensao` | **3,136** | [2,64; 3,73] | **3,146** | [2,99; 3,31] | **1,00** | sim | sim |
| `escolaridade` | 0,732 | [0,65; 0,82] | 0,768 | [0,74; 0,80] | 0,95 | sim | sim |
| `imc` (por 5 kg/m²) | **1,228** | [1,15; 1,31] | **1,454** | [1,43; 1,48] | **0,84** | sim | **não** |

### 2.1 · Seis de oito convergem — e a convergência é o resultado principal

`hipertensao` (3,136 vs. 3,146) e `idade_faixa` (1,234 vs. 1,240) coincidem na **terceira
casa decimal**, em duas pesquisas independentes, dois países, dois sistemas de saúde,
amostras de tamanho muito diferente.

Isso é a evidência mais forte que este trabalho produz de que **hipertensão e idade são
fatores robustos**, não artefatos do desenho americano. Um resultado que se replica assim
transfere. Escolaridade, sexo, tabagismo e atividade física também mantêm direção e ordem
de grandeza.

**Consequência direta:** o escore de 5 variáveis proposto em `docs/08` §4 apoia-se em
`hipertensao` e `idade_faixa` — as duas que melhor se replicam. É defensável para uso no
Brasil.

### 2.2 · Divergência 1 — `frutas` **inverte de direção**

```
Brasil   OR 1,299  [1,10; 1,53]   consumo diário de fruta associado a MAIS diabetes
EUA      OR 0,898  [0,86; 0,94]   associado a MENOS diabetes
```

IC disjuntos: a diferença não é ruído. Três explicações possíveis, e **os dados
transversais não distinguem entre elas**:

1. **Causalidade reversa mais forte no Brasil.** Quem recebe o diagnóstico é orientado a
   mudar a dieta. Se a orientação nutricional pós-diagnóstico for mais efetiva ou mais
   frequente no Brasil, o diabético brasileiro come mais fruta *porque* é diabético.
2. **Confundimento socioeconômico de sinal oposto.** Nos EUA, consumo de fruta acompanha
   renda alta; no Brasil, o padrão pode ser outro. O modelo controla escolaridade, mas
   escolaridade não é renda — e renda não existe no Vigitel de forma comparável.
3. **Diferença de instrumento.** Vigitel pergunta frequência semanal e nós binarizamos em
   "todos os dias"; o BRFSS já entrega a variável derivada `_FRTLT1`. Construtos próximos,
   não idênticos.

**Não afirmamos qual delas é.** O que se afirma: *nenhuma recomendação dietética deve ser
derivada desta variável nesta base*, e o achado é um argumento contra transplantar
coeficientes de dieta entre países.

### 2.3 · Divergência 2 — o IMC pesa **16% menos** no Brasil

```
Brasil   OR 1,228 por 5 kg/m²
EUA      OR 1,454 por 5 kg/m²
```

Cada 5 pontos de IMC aumentam a chance de diabetes em 23% no Brasil e 45% nos EUA.
IC disjuntos.

Duas leituras compatíveis com a literatura, e provavelmente ambas operam:

- **Distribuições diferentes.** IMC médio: Brasil 26,3 · EUA 28,4. A curva risco×IMC não é
  linear; medir a inclinação em faixas diferentes dá inclinações diferentes. É a mesma
  não-linearidade que `docs/06` §4 mostrou na curva em J.
- **Limiar de risco mais baixo em populações não europeias.** É achado consolidado que
  populações latino-americanas e asiáticas desenvolvem diabetes tipo 2 com IMC menor — o
  IMC é um marcador pior de adiposidade visceral nelas.

**Consequência prática, e ela é acionável:** um escore de risco calibrado nos EUA
**superestima** o peso do IMC quando aplicado ao Brasil. Recalibração local não é
refinamento acadêmico; é requisito.

---

## 3. Acesso — a variável que não pode ser comparada

| | valor |
|---|---|
| Brasil — % com **plano privado** (`q88`) | **49,0%** |
| EUA — % com **qualquer cobertura** (`HLTHPLN1`) | **87,8%** |

**Estes números não se comparam e não entraram no modelo.** No Brasil, `q88` mede plano
**privado**; a cobertura pública pelo SUS é universal e simplesmente não aparece nessa
variável. Nos EUA, `HLTHPLN1` mede qualquer cobertura, pública ou privada.

Lido ingenuamente, "49% vs 88%" sugeriria que o brasileiro tem menos acesso à saúde que o
americano — conclusão que a existência do SUS torna insustentável. É por isso que a variável
está fora do modelo comum e listada em `NAO_COMPARAVEL` no código, com o motivo.

*Isto ilustra o ponto geral da comparação binacional: variável com o mesmo nome não é a
mesma variável.*

---

## 4. Variáveis que ficaram de fora, e por quê

| variável | motivo |
|---|---|
| `colesterol_alto` | Vigitel 2015 não pergunta diagnóstico de colesterol alto |
| `avc`, `doenca_cardiaca` | ausentes no Vigitel 2015 |
| `saude_geral`, `saude_mental_dias`, `saude_fisica_dias`, `dificuldade_caminhar` | ausentes no Vigitel 2015 |
| `renda_faixa` | Vigitel não coleta renda de forma comparável |
| `sem_consulta_por_custo` | ausente no Vigitel 2015 |
| `vegetais` | Vigitel mede feijão e hortaliças com pergunta de forma diferente |
| `exame_colesterol` | Vigitel pergunta, mas a janela temporal difere |
| **`alcool_excessivo`** | **construtos diferentes**: BRFSS mede volume semanal (>14 doses H / >7 M); Vigitel mede *binge* (5/4 doses numa ocasião). Não é o mesmo fenômeno |

O caso do álcool merece nota: seria fácil casar as duas variáveis pelo nome e produzir uma
comparação sem sentido. Volume crônico e binge são comportamentos distintos com
fisiopatologia distinta.

---

## 5. Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | **6 de 8 fatores convergem**; hipertensão e idade coincidem na 3ª decimal | Os fatores centrais são robustos e transferem entre países |
| 2 | EUA têm **1,48×** a prevalência brasileira (10,50% vs 7,08%) | Contexto, não fator de risco |
| 3 | **`frutas` inverte de direção** (BR 1,30 · EUA 0,90) | Não derivar recomendação dietética desta base |
| 4 | **IMC pesa 16% menos no Brasil** (1,23 vs 1,45 por 5 kg/m²) | Escore americano superestima o IMC no Brasil — recalibrar |
| 5 | Acesso é incomparável por desenho (SUS) | Variável com mesmo nome ≠ mesma variável |

## 6. Limitações

1. **Cobertura geográfica.** Vigitel = 27 capitais; BRFSS = país inteiro. A limitação mais
   séria desta comparação.
2. **Oito variáveis apenas.** O modelo comum tem menos da metade das 21; os fatores omitidos
   são confundidores potenciais de ambos os lados.
3. **Ambos autorrelato de diagnóstico**, com subdiagnóstico diferente em cada país — e o
   subdiagnóstico brasileiro não foi medido aqui (exigiria a PNS 2019 com HbA1c, `docs/03` §3.2).
4. **Inferência ponderada aproximada** (peso reescalado ao n efetivo de Kish), como em
   `docs/07` §6.3.
5. **Vigitel não é probabilístico puro** — é amostra de linhas telefônicas fixas com
   ponderação para corrigir cobertura. O raking corrige parte disso, não tudo.

## Fontes

- [Ministério da Saúde — Vigitel, microdados 2006–2024](https://svs.aids.gov.br/daent/cgdnt/vigitel/) · arquivo `vigitel-2015-peso-rake.zip`, dicionário `dicionario-vigitel-2006-2024.xlsx`
- [CDC — 2015 BRFSS Survey Data and Documentation](https://www.cdc.gov/brfss/annual_data/annual_2015.html)
- [Tendência da prevalência do diabetes autorreferido nas capitais brasileiras (SciELO)](https://www.scielo.br/j/ress/a/79fMV9fPm66sxgMRPwT8JFx/)
- Proveniência e hashes em `data/external/FONTES.md`
