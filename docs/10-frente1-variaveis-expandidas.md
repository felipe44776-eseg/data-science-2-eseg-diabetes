> Reproduzir: `.\tasks.ps1 expandido` · saída `data/processed/gold/_frente1_expandido.json`

# Frente 1 — recuperar as variáveis descartadas

## Por que esta frente veio primeiro

`docs/08` §2.3 estabeleceu que o teto do modelo **não é o algoritmo**: a escada
inteira (prevalência → regra clínica → logística → spline → boosting → calibração)
rendeu +0,036 de PR-AUC. Um teste exploratório com todas as colunas numéricas do
BRFSS rendeu **+0,049** — mais que a escada inteira, sem tocar no modelo.

Logo, o investimento com maior retorno não é método, é **informação**. Esta frente
mede quanto, de onde vem, e — a pergunta que mudou o resultado — **para quem**.

---

## Passo 1 — curadoria, não força bruta

O teste exploratório usou 133 colunas cegas. Isso mede um teto, mas não produz
análise: mistura preditor com marcador de detecção, repete a mesma informação em
três codificações (`_BMI5`, `_BMI5CAT`, `_RFBMI5`) e impede leitura por bloco.

`src/diabetes/features/expandido.py` declara **69 variáveis nomeadas, agrupadas por
domínio**, mantendo a separação que o projeto já usa (risco · detecção · sensível):

| bloco | n | o que entra de novo |
|---|---|---|
| demografia | 11 | emprego, estado civil, moradia, filhos, veterano, internet, idioma |
| **raça/etnia** | 2 | `_RACEGR3`, `_HISPANC` — **ausentes das 22 originais** |
| antropometria | 3 | peso em kg e altura, separados do IMC |
| **comorbidades** | 11 | rim, artrite, DPOC, asma, câncer, **depressão** |
| limitação funcional | 7 | visão, cognição, vestir-se, autonomia, equipamento |
| atividade física | 6 | categoria em 4 níveis, VO₂ máx, treino de força |
| dieta | 8 | porções/dia contínuas, suco, feijão, verdura, laranja |
| álcool | 5 | doses/dia, doses/semana, binge |
| tabaco | 3 | status em 4 níveis |
| saúde percebida | 3 | (já existiam) |
| acesso e detecção | 9 | check-up, médico de referência, vacinas, exame de colesterol |

**50 variáveis novas.** Três tipos de recuperação:

1. **Resolução** — `_AGE80` (idade contínua) no lugar de 13 faixas; `DROCDY3_`
   (doses/dia) no lugar de um binário; peso e altura fora do IMC.
2. **Domínios inteiros** — comorbidade, limitação funcional, aptidão, emprego.
3. **Raça/etnia** — a omissão mais séria.

### Duas decisões de higiene

**Vazamento.** `VAZAMENTO` bloqueia por regex tudo que decorre do próprio
diagnóstico: idade do diagnóstico, insulina, exame de HbA1c, exame de pé, fundo de
olho. Incluir qualquer uma produz AUC quase perfeito e valor zero. O módulo
levanta `AssertionError` se alguma entrar.

**Não-resposta vira `NaN`, não número.** Código 9 significa "recusou", não "nove
vezes mais que sim". O gradient boosting trata ausente nativamente. `INCOME2` fica
com **17,9% de missing** (77.714 linhas) — as 74.462 pessoas que responderam 77
("não sabe") ou 99 ("recusou"), mais 3.252 ausentes de origem. Elas continuam na
amostra em vez de serem descartadas, que é o ponto desta frente.

> **Correção (auditoria).** Este parágrafo dizia **31,2%** e atribuía o missing às
> 34.251 pessoas excluídas pelo pré-processamento original. Estava errado nas duas
> pontas. A máscara de não-resposta aplicava `{7, 9, 77, 99}` a toda variável, e em
> três delas o código 7 é **categoria válida**: `INCOME2` 7 = US$ 50-75 mil (57.166
> pessoas), `EMPLOY1` 7 = aposentado (129.290) e `_AGEG5YR` 7/9 = 50-54 e 60-64 anos
> (87.806). O código realmente inválido é outro em cada uma — e a regra certa já
> existia em `external/brfss2015.py` (`descartar=(77, 99)`), contradita pelo trilho
> expandido. Corrigido em `features/expandido.py`, com `NAO_RESPOSTA_PROPRIA` lido
> de `REGRAS` para que os dois trilhos não possam divergir de novo. O efeito
> preditivo é pequeno (o ganho desta frente vai de +6,62% para **+6,37%** de
> PR-AUC), mas o efeito descritivo e causal não é — ver `docs/21` e `docs/11`.

**n = 432.968** (vs. 253.680 do arquivo entregue).

---

## Passo 2 — quanto ganha

Protocolo idêntico ao de `docs/08`: holdout de 20% por grupo (chave = hash das 21
originais, escolha conservadora), gradient boosting com calibração isotônica.

| conjunto | vars | ROC-AUC | **PR-AUC** | recall @ esp. 90% | Brier |
|---|---|---|---|---|---|
| 21 originais | 21 | 0,8430 | 0,4439 | 0,5051 | 0,0911 |
| **60 curadas (risco)** | 60 | **0,8539** | **0,4733** | **0,5333** | 0,0885 |
| 69 curadas (+ detecção) | 69 | 0,8631 | 0,4874 | 0,5495 | 0,0869 |

**+6,62% de PR-AUC** e **+10,9 milésimos de ROC-AUC** só com variáveis de risco.
Em termos operacionais: o recall a 90% de especificidade sobe de **50,5% para 53,3%**.

### Nota honesta sobre o número

O teste exploratório prometeu +11%; a curadoria entrega **+6,6%**. A diferença tem
três causas, todas legítimas: a curadoria descarta redundância e marcadores de
detecção, o protocolo agora inclui calibração, e o holdout é por grupo. **Menos
ganho, muito mais interpretabilidade** — e o número exploratório continua válido
como teto do que força bruta alcançaria.

O bloco de detecção acrescenta mais **+2,98%** — e, como em `docs/08` §2.2, isso
confirma que ele prediz *diagnóstico*, não doença. Fica fora do modelo de referência.

---

## Passo 3 — de onde vem o ganho (ablação por bloco)

Remove um bloco de cada vez, mede a perda. É o único jeito de distinguir "mais
variáveis" de "variáveis que importam".

| bloco removido | n | PR-AUC | perda | **perda %** |
|---|---|---|---|---|
| **comorbidades** | 11 | 0,4296 | 0,0437 | **−9,23%** |
| **antropometria** | 3 | 0,4446 | 0,0287 | **−6,06%** |
| saúde percebida | 3 | 0,4556 | 0,0177 | −3,74% |
| álcool | 5 | 0,4651 | 0,0082 | −1,73% |
| dieta | 8 | 0,4674 | 0,0059 | −1,25% |
| demografia | 11 | 0,4683 | 0,0050 | −1,06% |
| limitação funcional | 7 | 0,4688 | 0,0045 | −0,95% |
| **raça/etnia** | 2 | 0,4695 | 0,0038 | **−0,80%** |
| atividade física | 6 | 0,4719 | 0,0014 | −0,30% |
| outros | 1 | 0,4727 | 0,0006 | −0,13% |
| **tabaco** | 3 | 0,4731 | 0,0002 | **−0,04%** |

### Insights da ablação

**1. Comorbidade domina.** Onze variáveis valem **9,2%** — mais que todos os outros
blocos novos somados. Rim, artrite, DPOC, câncer e depressão carregam informação
que nenhuma das 21 originais tinha. Faz sentido clínico: diabetes é doença de
multimorbidade, e o conjunto original só continha as comorbidades *cardiovasculares*.

**2. Tabagismo é praticamente irrelevante** (−0,04%). Isso é surpreendente para uma
variável que consta de todo escore de risco cardiovascular — e coerente com o que
`docs/07` já mostrava: OR ajustado de 1,08, o menor de M1. **Tabagismo é fator de
risco cardiovascular, não de diabetes tipo 2.** O escore da Trilha C não deve incluí-lo.

**3. Atividade física quase não contribui preditivamente** (−0,30%), mesmo com VO₂
máx e treino de força. Reforça `docs/07` §2.1: o efeito existe mas é mediado por
saúde percebida — e o que sobra, após condicionar em tudo, é pequeno.

**4. Raça vale pouco na média (−0,80%)** — e este número, isolado, levaria à
conclusão errada. Ver o passo seguinte.

---

## Passo 4 — para quem melhora (e o achado que reorienta a frente)

Auditoria só possível agora, porque raça/etnia entrou na base. Limiar **global** fixo
em especificidade de 90% — que é como um programa de rastreamento seria operado.

| grupo | n | prevalência | recall 21 vars | **recall 60 vars** | **ganho** |
|---|---|---|---|---|---|
| branco não-hispânico | 66.098 | 12,25% | 0,4934 | 0,4889 | **−0,45 pp** |
| **negro não-hispânico** | 6.736 | **21,30%** | 0,5770 | **0,6829** | **+10,6 pp** |
| outro não-hispânico | 3.827 | 13,27% | 0,4409 | **0,5571** | **+11,6 pp** |
| multirracial | 1.511 | 14,82% | 0,5446 | **0,6786** | **+13,4 pp** |
| hispânico | 7.021 | 14,88% | 0,5273 | **0,6354** | **+10,8 pp** |

> **O ganho médio de 6,6% esconde uma redistribuição enorme.** Os brancos perdem
> meio ponto; todos os demais grupos ganham **10 a 13 pontos percentuais** de recall.
>
> O modelo de 21 variáveis era sistematicamente pior para minorias — e ninguém
> podia saber, porque a variável que revela isso tinha sido removida da base.

Calibração por grupo fica boa em todos (desvio < 1,2 pp).

### Passo 4b — o ganho vem de raça, ou das comorbidades?

Pergunta ética central, e mensurável: rodei o modelo de **58 variáveis, sem raça**.

| grupo | ganho **sem** raça | ganho **com** raça |
|---|---|---|
| branco não-hispânico | +2,1 pp | −0,45 pp |
| negro não-hispânico | +2,2 pp | **+10,6 pp** |
| outro não-hispânico | +0,8 pp | **+11,6 pp** |
| multirracial | +4,0 pp | **+13,4 pp** |
| hispânico | +3,6 pp | **+10,8 pp** |

**Resposta: vem de raça.** Sem ela o ganho é pequeno e **uniforme** — melhora todo
mundo um pouco e **preserva a lacuna original**. Com ela, o modelo redistribui.

**Mecanismo:** a prevalência em negros não-hispânicos é **21,3%** contra 12,25% em
brancos. Sob limiar global, um modelo que ignora raça subestima o risco basal das
minorias e as sub-seleciona para rastreamento. Incluir raça corrige o intercepto.

### O dilema, declarado

Isto reproduz o debate de **race-based medicine**, e o projeto toma posição explícita:

- **Raça aqui não é variável biológica.** É *proxy* de determinantes sociais não
  medidos — acesso, discriminação estrutural, ambiente alimentar, estresse crônico,
  qualidade do cuidado. Tratá-la como causa biológica seria erro grave.
- **Como proxy, funciona e o efeito é grande** — +10 a 13 pp de recall para quem
  tem a maior prevalência e o pior diagnóstico.
- **A solução correta não é escolher entre incluir e excluir**, é **medir os
  determinantes diretamente** (renda do bairro, insegurança alimentar, distância
  ao serviço, experiência de discriminação). Com eles no modelo, raça deveria
  perder poder preditivo — e isso é um teste falseável.
- **Enquanto não houver essa medida, excluir raça não é neutro:** é escolher manter
  a lacuna de 10 pontos percentuais e chamar isso de imparcialidade.

**Decisão do projeto:** o modelo de referência **inclui** raça, com esta justificativa
registrada, e o relatório final reporta as duas versões lado a lado.

---

## Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | **+6,6% PR-AUC** com 60 variáveis curadas; recall 50,5% → 53,3% | Confirma que o teto era informação |
| 2 | **Comorbidade vale 9,2%** — mais que todos os outros blocos novos juntos | Multimorbidade é o bloco que faltava |
| 3 | **Tabagismo vale 0,04%** | Fora do escore da Trilha C — é fator cardiovascular, não de diabetes |
| 4 | Atividade física preditivamente irrelevante (−0,30%) | Coerente com a mediação de `docs/07` §2.1 |
| 5 | **O ganho é inteiramente das minorias** (+10 a 13 pp vs. −0,45 pp) | Ganho médio esconde redistribuição |
| 6 | **O efeito de equidade vem de raça, não das comorbidades** | Decisão ética explícita, com as duas versões reportadas |
| 7 | `INCOME2` volta com **17,9%** de missing em vez de 34.251 linhas descartadas | Base para a Frente 5 (MNAR e pesos) |

## Limitações

1. **Raça como proxy** — ver o dilema acima. O teste falseável é adicionar
   determinantes sociais e verificar se raça perde poder.
2. **Missing tratado nativamente pelo boosting**, não imputado. Para o modelo é
   adequado; para inferência, não — é o que a Frente 5 trata.
3. **Ablação por bloco não é decomposição de variância**: os blocos são
   correlacionados, e as perdas não somam ao ganho total.
4. **Limiar global.** Limiar por grupo mudaria o quadro de equidade e abre outra
   discussão (paridade de recall vs. paridade de precisão) — Trilha C.
