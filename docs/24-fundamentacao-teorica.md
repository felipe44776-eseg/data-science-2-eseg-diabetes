# Fundamentação teórica e bibliografia

> Este documento não repete resultados. Ele responde **por que cada método foi
> escolhido** e **de onde ele vem**. Os números estão em `docs/01` a `docs/23`.

Cada seção tem a mesma estrutura: o problema, o método, a referência canônica, e
**onde ele aparece neste projeto**. A bibliografia completa está no §14.

---

## 1. O problema de fundo: o que é um dado de saúde autorrelatado

O BRFSS é um inquérito telefônico de amostragem complexa. Três propriedades dele
determinam quase tudo o que este projeto faz:

**(a) A amostra não é aleatória simples.** É estratificada por região e densidade
telefônica, com seleção desigual dentro do domicílio. Ignorar isso produz
estimativas pontuais enviesadas e intervalos de confiança estreitos demais
(CDC, 2015; Kish, 1965).

**(b) O desfecho é diagnóstico, não doença.** A pergunta é *"algum profissional de
saúde já lhe disse que você tem diabetes?"*. Quem tem a doença e nunca foi testado
responde "não" — e entra na base como caso negativo. Nos EUA, cerca de **27,6% dos
diabéticos não sabem** (Menke et al., 2015; Selvin et al., 2014). É o que torna o
problema formalmente **Positive-Unlabeled**, não classificação binária (§8).

**(c) O rótulo depende do acesso ao sistema de saúde.** Como diagnosticar exige
consultar alguém, a probabilidade de ser rotulado positivo é função de renda,
plano de saúde e escolaridade — que também são fatores de risco. Isso é
**viés de seleção com estrutura causal**, e o instrumento formal para raciocinar
sobre ele é o DAG (Hernán, Hernández-Díaz & Robins, 2004).

O arquivo entregue no trabalho agrava (c): é um derivado do BRFSS publicado no
Kaggle (Teboul, 2021), cuja limpeza removeu preferencialmente quem nunca fez
exame — medido em `docs/05`.

---

## 2. Reconstrução e proveniência

**Problema.** Os dados chegaram como PDF de 4.374 páginas. A ordem de leitura de
um PDF **não é garantida pela especificação** — o texto é uma lista de operadores
de desenho, não uma tabela.

**Método.** Reconstrução por coordenada de *bounding box*: agrupar palavras por
faixa de `y`, ordenar por `x` dentro da faixa. Verificação por igualdade célula a
célula contra a fonte original (`docs/05`).

**Princípio.** Proveniência versionada em vez de dado versionado — manifesto com
hash SHA-256, dado fora do git (Wilson et al., 2017; Wilkinson et al., 2016, sobre
FAIR). O registro do que a base é e de onde veio segue o formato de *datasheet*
(Gebru et al., 2021).

→ `docs/01`, `docs/04`, `data/external/FONTES.md`, ADR 0001.

---

## 3. Inferência em amostragem complexa

| conceito | referência | onde usamos |
|---|---|---|
| Pesos de pós-estratificação (`_LLCPWT`) | CDC (2015) | toda prevalência, em par com a não ponderada |
| Efeito de desenho (DEFF) e *n* efetivo | Kish (1965) | `docs/11` §A |
| Linearização de Taylor para variância | Binder (1983) | `docs/11` §A — DEFF real **2,94** |
| Raking / *iterative proportional fitting* | Deming & Stephan (1940) | `docs/11` §B — pesos publicáveis |
| Estimadores de calibração | Deville & Särndal (1992) | idem |

**Por que importa.** A aproximação de Kish é uma cota conservadora do DEFF; ela
supõe variabilidade de pesos sem estrutura. Com `_STSTR` e `_PSU` declarados, a
linearização de Taylor dá o valor correto. Medimos 2,94 contra os 4,04 de Kish —
ou seja, nossos intervalos de confiança anteriores eram **largos demais**, não
estreitos demais. Foi uma das nove previsões refutadas (`docs/23`).

O raking existe aqui por um motivo prático: o arquivo do Kaggle **descartou as
colunas de peso**. Reconstruímos pesos que corrigem 95,6% do viés, publicáveis
para qualquer pessoa que use o mesmo CSV.

---

## 4. Associação e tamanho de efeito

Com *n* = 253.680, **p-valor não informa nada**: diferenças irrelevantes atingem
significância. O projeto reporta tamanho de efeito com intervalo, não teste.

| medida | referência | uso |
|---|---|---|
| V de Cramér | Cramér (1946) | associação categórica, `docs/06` |
| δ de Cliff | Cliff (1993) | comparação ordinal robusta, `docs/06` |
| Teste de tendência | Cochran (1954); Armitage (1955) | monotonicidade em variáveis ordinais |
| Odds ratio ajustado com IC | — | `docs/07`, modelos M1/M2/M3 |

---

## 5. Vazamento e partição

**Problema.** A base tem 23.899 duplicatas exatas de vetor de features. Um
`train_test_split` aleatório coloca cópias da mesma linha nos dois lados —
contaminando 13,65% do teste.

**Método.** Partição por **hash blake2b do vetor de features**, de modo que linhas
idênticas caiam sempre na mesma partição (`StratifiedGroupKFold` com o hash como
chave de grupo).

**Nota de honestidade.** Medimos a inflação: **0,1% a 1,2%** — pequena. A regra
permanece porque é gratuita e defensável, não porque o efeito seja grande. A
taxonomia geral de vazamento está em Kaufman et al. (2012).

→ ADR 0002, `docs/08` §2.1.

---

## 6. Desbalanceamento, métricas e calibração

**Acurácia não é reportada em nenhum lugar deste projeto** (ADR 0005). Responder
sempre "não tem diabetes" acerta 84,2%. Com prevalência de 13,9%, a curva
precision-recall é mais informativa que a ROC (Saito & Rehmsmeier, 2015).

| métrica | referência | por que |
|---|---|---|
| PR-AUC | Saito & Rehmsmeier (2015) | primária, sensível à classe rara |
| Recall @ especificidade fixa | — | traduz a métrica em capacidade operacional |
| Escore de Brier | Brier (1950) | erro quadrático de probabilidade |
| ECE | Guo et al. (2017) | erro de calibração esperado, por faixa |

**Sobre reamostragem.** SMOTE (Chawla et al., 2002) **não é o método adotado**.
A razão é medida, não estilística: reponderar distorce as probabilidades previstas
e piorou o ECE em **67×** sem mudar a ordenação. É exatamente o resultado que
van den Goorbergh et al. (2022) documentam para modelos de risco clínico. Usamos
aprendizado sensível ao custo (Elkan, 2001) mais ajuste de limiar, e SMOTE entra
apenas como ablação para sustentar a escolha com número.

**Calibração como requisito, não refinamento.** Regressão isotônica (Zadrozny &
Elkan, 2002; Niculescu-Mizil & Caruana, 2005). Van Calster et al. (2019) chamam a
calibração de "calcanhar de Aquiles da análise preditiva" — e este projeto
encontrou o mesmo padrão em quatro transposições independentes (`docs/23`).

→ ADR 0004, ADR 0005, `docs/08`.

---

## 7. Modelos: por que árvores e por que *glass-box*

**Gradient boosting** (Friedman, 2001; Ke et al., 2017) como referência de
desempenho. Grinsztajn, Oyallon & Varoquaux (2022) mostram por que redes
profundas não superam árvores em tabular típico — a base é heterogênea,
categórica e de tamanho moderado.

**Explainable Boosting Machine** como modelo publicável. É um GAM aditivo com
interações de pares (Hastie & Tibshirani, 1990; Lou et al., 2013; Nori et al.,
2019). Duas consequências práticas:

1. **Exportável como tabela de consulta.** Foi o que permitiu a calculadora rodar
   em JavaScript com paridade de 1,1×10⁻¹⁶ contra o Python (`docs/17`).
2. **Interpretável por construção**, não por explicação *post hoc* — o argumento
   de Rudin (2019) para decisões de alto risco. SHAP (Lundberg & Lee, 2017) é
   usado como diagnóstico, nunca como justificativa clínica.

**Restrições de monotonicidade** entram onde a direção é conhecida a priori
(pressão alta não pode reduzir risco). Deliberadamente **não** aplicadas à idade —
a relação empírica não é estritamente monótona no topo.

→ `docs/08`, `docs/13`.

---

## 8. Positive-Unlabeled learning

**O enquadramento.** Se todo positivo rotulado é de fato positivo, mas parte dos
"negativos" são positivos não rotulados, o problema é PU, não binário
(Bekker & Davis, 2020).

| método | referência | resultado |
|---|---|---|
| SCAR / estimador de `c` | Elkan & Noto (2008) | frequência de rotulagem |
| Best Bin Estimation | Garg et al. (2021) | **c = 0,7283** |
| SAR (rotulagem dependente de covariável) | Bekker & Davis (2020) | perfil dos ocultos |

**A validação externa é o ponto.** O BBE, usando só o BRFSS, estimou c = 0,7283.
O NHANES, que mede HbA1c em laboratório e portanto **vê** os não diagnosticados,
implica c = 0,7240 (Menke et al., 2015). Dois métodos que não se falam concordam
na terceira casa decimal. Prevalência real corrigida: **14,29%**.

**Armadilha registrada.** A primeira formulação SAR explodiu porque `c(x)`
chegava a 0,05 e o ranking passou a medir "não foi testado" em vez de "alto risco
e não testado". Corrigido com limites `c ∈ [0,50; 0,95]` e remoção de vazamento
(as variáveis de exame eram simultaneamente feature e fonte do rótulo).

→ `docs/12`.

---

## 9. Predição conforme

Garante cobertura marginal sem supor nada sobre a distribuição (Vovk, Gammerman &
Shafer, 2005; Angelopoulos & Bates, 2023). Usamos a variante **Mondrian**
(condicional à classe), porque cobertura marginal com 13,9% de prevalência pode
ser satisfeita ignorando a classe rara.

→ `docs/13`.

---

## 10. Da predição à decisão

Um modelo bom não é automaticamente um programa de rastreamento bom. A ponte é a
**análise de curva de decisão** (Vickers & Elkin, 2006): benefício líquido em
função do limiar, comparado contra "rastrear todos" e "rastrear ninguém".

Complementos: número necessário a rastrear (NNS) e custo por caso encontrado, com
três cenários de preço de HbA1c. Resultado: testar 10% da população encontra
**40,3% dos casos** a R$ 75 por caso.

O escore de papel de cinco perguntas foi construído contra o **FINDRISC**
(Lindström & Tuomilehto, 2003), o padrão internacional desde 2003 — e o supera em
37,7 milésimos de ROC-AUC na mesma amostra. O relato de modelo preditivo segue a
estrutura do **TRIPOD** (Collins et al., 2015); o dimensionamento amostral segue
Riley et al. (2020).

→ `docs/16`.

---

## 11. Equidade

**Os três critérios usuais são mutuamente incompatíveis** quando a prevalência
difere entre grupos — resultado de impossibilidade demonstrado independentemente
por Kleinberg, Mullainathan & Raghavan (2017) e Chouldechova (2017). Não há
escolha "neutra": há escolha declarada.

Este projeto tem um agravante específico: **o rótulo é enviesado**. Obermeyer et
al. (2019) mostram o caso canônico — um algoritmo que usa custo como proxy de
necessidade reproduz a desigualdade de acesso que gerou o custo. Aqui, usar
"diagnóstico" como proxy de "doença" tem exatamente a mesma estrutura.

Por isso a auditoria de equidade é feita **duas vezes**: sobre o rótulo observado
e sobre o rótulo corrigido por PU. E por isso o achado de `docs/10` — que o ganho
de variáveis novas vai inteiramente para minorias (+10,6 a +13,4 p.p. de recall
contra −0,45 p.p. para brancos) — é reportado como resultado central, não como
nota de rodapé.

→ `docs/10`, `docs/16` §4.

---

## 12. Camada causal

**Nenhum método torna dado transversal causal.** O que se pode fazer é declarar as
suposições, derivar delas o que ajustar, e quantificar a fragilidade.

| ferramenta | referência | papel |
|---|---|---|
| DAG e critério de *backdoor* | Pearl (1995, 2009) | define **qual** é a pergunta |
| Viés de colisor e de seleção | Hernán, Hernández-Díaz & Robins (2004) | por que ajustar por `saude_geral` invalida |
| Mediação vs. efeito total | Hernán & Robins (2020) | ajustar por IMC dá o efeito **direto** |
| Testes de refutação | Sharma & Kiciman (2020) | placebo, confundidor aleatório, subamostra |
| **E-value** | VanderWeele & Ding (2017) | o único número que **não** depende do DAG |

O E-value é o que sustenta o veredito honesto de `docs/21`: o efeito da atividade
física **sobrevive a todas as refutações** (E-value 2,02) e **não sobrevive a um
confundidor plausível** — capacidade funcional prévia. A refutação testa a
especificação; o E-value testa o que está fora dela.

**Experimento natural.** A expansão do Medicaid em 2014 serve de choque exógeno de
acesso. Diferenças-em-diferenças no desenho de Card & Krueger (1994), com erros
padrão agrupados por estado (Bertrand, Duflo & Mullainathan, 2004) e exclusão de
estados de adoção escalonada pelo problema documentado por Goodman-Bacon (2021).
A literatura de referência para o efeito esperado é Sommers et al. (2016) e
Kaufman et al. (2015).

**O resultado foi honesto sobre si mesmo:** a cobertura sobe 3,11 p.p., mas a
diferença mínima detectável do desenho é 0,90 p.p. contra um efeito esperado de
0,16 p.p. **O desenho não tem poder** — e dizê-lo vale mais do que reportar um
nulo como se fosse evidência de ausência.

→ `docs/14`, `docs/21`.

---

## 13. Não supervisionada e deslocamento de distribuição

**Por que MCA e não PCA.** As variáveis são categóricas; PCA sobre indicadores
0/1 otimiza a métrica errada. A análise de correspondência múltipla decompõe a
inércia do qui-quadrado (Benzécri, 1973; Greenacre & Blasius, 2006).

| método | referência | achado |
|---|---|---|
| MCA + k-means | Benzécri (1973) | 5 fenótipos, gradiente de 17× |
| FP-Growth | Han, Pei & Yin (2000) | síndrome metabólica reconstruída, lift 3,83 |
| Isolation Forest | Liu, Ting & Zhou (2008) | **refutou** nossa hipótese (lift 0,81) |

**Deslocamento de distribuição.** A decomposição em *covariate shift* / *label
shift* / *concept drift* (Quiñonero-Candela et al., 2009; Moreno-Torres et al.,
2012) é o que dá diagnóstico acionável: os dois primeiros se corrigem por
reponderação e recalibração (Lipton, Wang & Smola, 2018); o terceiro exige
retreinar. Medimos os três entre 2015 e 2023 — e o terceiro é **praticamente
ausente**, que é a razão de a recalibração bastar.

→ `docs/20`, `docs/22`.

---

## 14. Bibliografia

### Amostragem complexa e inferência

- BINDER, D. A. On the variances of asymptotically normal estimators from complex surveys. *International Statistical Review*, v. 51, n. 3, p. 279–292, 1983.
- CENTERS FOR DISEASE CONTROL AND PREVENTION. *Behavioral Risk Factor Surveillance System: 2015 Codebook Report* e *Complex Sampling Weights and Preparing Module Data for Analysis*. Atlanta: CDC, 2015.
- DEMING, W. E.; STEPHAN, F. F. On a least squares adjustment of a sampled frequency table when the expected marginal totals are known. *Annals of Mathematical Statistics*, v. 11, n. 4, p. 427–444, 1940.
- DEVILLE, J.-C.; SÄRNDAL, C.-E. Calibration estimators in survey sampling. *Journal of the American Statistical Association*, v. 87, n. 418, p. 376–382, 1992.
- KISH, L. *Survey Sampling*. New York: Wiley, 1965.

### Estatística e tamanho de efeito

- ARMITAGE, P. Tests for linear trends in proportions and frequencies. *Biometrics*, v. 11, n. 3, p. 375–386, 1955.
- CLIFF, N. Dominance statistics: ordinal analyses to answer ordinal questions. *Psychological Bulletin*, v. 114, n. 3, p. 494–509, 1993.
- COCHRAN, W. G. Some methods for strengthening the common χ² tests. *Biometrics*, v. 10, n. 4, p. 417–451, 1954.
- CRAMÉR, H. *Mathematical Methods of Statistics*. Princeton: Princeton University Press, 1946.

### Avaliação, calibração e desbalanceamento

- BRIER, G. W. Verification of forecasts expressed in terms of probability. *Monthly Weather Review*, v. 78, n. 1, p. 1–3, 1950.
- CHAWLA, N. V. et al. SMOTE: Synthetic Minority Over-sampling Technique. *Journal of Artificial Intelligence Research*, v. 16, p. 321–357, 2002.
- ELKAN, C. The foundations of cost-sensitive learning. In: *IJCAI*, 2001.
- GUO, C. et al. On calibration of modern neural networks. In: *ICML*, 2017.
- KAUFMAN, S. et al. Leakage in data mining: formulation, detection, and avoidance. *ACM TKDD*, v. 6, n. 4, 2012.
- NICULESCU-MIZIL, A.; CARUANA, R. Predicting good probabilities with supervised learning. In: *ICML*, 2005.
- SAITO, T.; REHMSMEIER, M. The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. *PLoS ONE*, v. 10, n. 3, e0118432, 2015.
- VAN CALSTER, B. et al. Calibration: the Achilles heel of predictive analytics. *BMC Medicine*, v. 17, art. 230, 2019.
- VAN DEN GOORBERGH, R. et al. The harm of class imbalance corrections for risk prediction models. *JAMIA*, v. 29, n. 9, p. 1525–1534, 2022.
- ZADROZNY, B.; ELKAN, C. Transforming classifier scores into accurate multiclass probability estimates. In: *KDD*, 2002.

### Modelos e interpretabilidade

- FRIEDMAN, J. H. Greedy function approximation: a gradient boosting machine. *Annals of Statistics*, v. 29, n. 5, p. 1189–1232, 2001.
- GRINSZTAJN, L.; OYALLON, E.; VAROQUAUX, G. Why do tree-based models still outperform deep learning on typical tabular data? In: *NeurIPS*, 2022.
- HASTIE, T.; TIBSHIRANI, R. *Generalized Additive Models*. London: Chapman & Hall, 1990.
- KE, G. et al. LightGBM: a highly efficient gradient boosting decision tree. In: *NeurIPS*, 2017.
- LOU, Y. et al. Accurate intelligible models with pairwise interactions. In: *KDD*, 2013.
- LUNDBERG, S. M.; LEE, S.-I. A unified approach to interpreting model predictions. In: *NeurIPS*, 2017.
- NORI, H. et al. InterpretML: a unified framework for machine learning interpretability. *arXiv*:1909.09223, 2019.
- RUDIN, C. Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead. *Nature Machine Intelligence*, v. 1, p. 206–215, 2019.

### Positive-Unlabeled e predição conforme

- ANGELOPOULOS, A. N.; BATES, S. Conformal prediction: a gentle introduction. *Foundations and Trends in Machine Learning*, v. 16, n. 4, 2023.
- BEKKER, J.; DAVIS, J. Learning from positive and unlabeled data: a survey. *Machine Learning*, v. 109, p. 719–760, 2020.
- ELKAN, C.; NOTO, K. Learning classifiers from only positive and unlabeled data. In: *KDD*, 2008.
- GARG, S. et al. Mixture proportion estimation and PU learning: a modern approach. In: *NeurIPS*, 2021.
- VOVK, V.; GAMMERMAN, A.; SHAFER, G. *Algorithmic Learning in a Random World*. New York: Springer, 2005.

### Decisão clínica e relato

- COLLINS, G. S. et al. Transparent reporting of a multivariable prediction model for individual prognosis or diagnosis (TRIPOD). *BMJ*, v. 350, g7594, 2015.
- LINDSTRÖM, J.; TUOMILEHTO, J. The Diabetes Risk Score: a practical tool to predict type 2 diabetes risk. *Diabetes Care*, v. 26, n. 3, p. 725–731, 2003.
- RILEY, R. D. et al. Calculating the sample size required for developing a clinical prediction model. *BMJ*, v. 368, m441, 2020.
- VICKERS, A. J.; ELKIN, E. B. Decision curve analysis: a novel method for evaluating prediction models. *Medical Decision Making*, v. 26, n. 6, p. 565–574, 2006.

### Equidade algorítmica

- CHOULDECHOVA, A. Fair prediction with disparate impact: a study of bias in recidivism prediction instruments. *Big Data*, v. 5, n. 2, p. 153–163, 2017.
- HARDT, M.; PRICE, E.; SREBRO, N. Equality of opportunity in supervised learning. In: *NeurIPS*, 2016.
- KLEINBERG, J.; MULLAINATHAN, S.; RAGHAVAN, M. Inherent trade-offs in the fair determination of risk scores. In: *ITCS*, 2017.
- OBERMEYER, Z. et al. Dissecting racial bias in an algorithm used to manage the health of populations. *Science*, v. 366, n. 6464, p. 447–453, 2019.

### Inferência causal

- BERTRAND, M.; DUFLO, E.; MULLAINATHAN, S. How much should we trust differences-in-differences estimates? *Quarterly Journal of Economics*, v. 119, n. 1, p. 249–275, 2004.
- CARD, D.; KRUEGER, A. B. Minimum wages and employment: a case study of the fast-food industry in New Jersey and Pennsylvania. *American Economic Review*, v. 84, n. 4, p. 772–793, 1994.
- GOODMAN-BACON, A. Difference-in-differences with variation in treatment timing. *Journal of Econometrics*, v. 225, n. 2, p. 254–277, 2021.
- HERNÁN, M. A.; HERNÁNDEZ-DÍAZ, S.; ROBINS, J. M. A structural approach to selection bias. *Epidemiology*, v. 15, n. 5, p. 615–625, 2004.
- HERNÁN, M. A.; ROBINS, J. M. *Causal Inference: What If*. Boca Raton: Chapman & Hall/CRC, 2020.
- PEARL, J. Causal diagrams for empirical research. *Biometrika*, v. 82, n. 4, p. 669–688, 1995.
- PEARL, J. *Causality: Models, Reasoning, and Inference*. 2. ed. Cambridge: Cambridge University Press, 2009.
- SHARMA, A.; KICIMAN, E. DoWhy: an end-to-end library for causal inference. *arXiv*:2011.04216, 2020.
- VANDERWEELE, T. J.; DING, P. Sensitivity analysis in observational research: introducing the E-value. *Annals of Internal Medicine*, v. 167, n. 4, p. 268–274, 2017.

### Não supervisionada e deslocamento de distribuição

- BENZÉCRI, J.-P. *L'Analyse des Données*. Paris: Dunod, 1973.
- GREENACRE, M.; BLASIUS, J. (ed.). *Multiple Correspondence Analysis and Related Methods*. Boca Raton: Chapman & Hall/CRC, 2006.
- HAN, J.; PEI, J.; YIN, Y. Mining frequent patterns without candidate generation. In: *SIGMOD*, 2000.
- LIPTON, Z.; WANG, Y.-X.; SMOLA, A. Detecting and correcting for label shift with black box predictors. In: *ICML*, 2018.
- LIU, F. T.; TING, K. M.; ZHOU, Z.-H. Isolation Forest. In: *ICDM*, 2008.
- MORENO-TORRES, J. G. et al. A unifying view on dataset shift in classification. *Pattern Recognition*, v. 45, n. 1, p. 521–530, 2012.
- QUIÑONERO-CANDELA, J. et al. (ed.). *Dataset Shift in Machine Learning*. Cambridge: MIT Press, 2009.

### Epidemiologia do diabetes e políticas de acesso

- INTERNATIONAL DIABETES FEDERATION. *IDF Diabetes Atlas*. 10. ed. Bruxelas: IDF, 2021.
- KAUFMAN, H. W. et al. Surge in newly identified diabetes among Medicaid patients in 2014 within Medicaid expansion states under the Affordable Care Act. *Diabetes Care*, v. 38, n. 1, p. 98–99, 2015.
- MENKE, A. et al. Prevalence of and trends in diabetes among adults in the United States, 1988–2012. *JAMA*, v. 314, n. 10, p. 1021–1029, 2015.
- SELVIN, E. et al. Trends in prevalence and control of diabetes in the United States, 1988–1994 and 1999–2010. *Annals of Internal Medicine*, v. 160, n. 8, p. 517–525, 2014.
- SOMMERS, B. D. et al. Changes in utilization and health among low-income adults after Medicaid expansion or expanded private insurance. *JAMA Internal Medicine*, v. 176, n. 10, p. 1501–1509, 2016.

### Fontes de dados

- BRASIL. Ministério da Saúde. *Vigitel Brasil 2015* e *Vigitel Brasil 2023*: vigilância de fatores de risco e proteção para doenças crônicas por inquérito telefônico. Brasília: Ministério da Saúde.
- CENTERS FOR DISEASE CONTROL AND PREVENTION. *Behavioral Risk Factor Surveillance System (BRFSS) Annual Survey Data*, 2015 e 2023.
- CENTERS FOR DISEASE CONTROL AND PREVENTION / NCHS. *National Health and Nutrition Examination Survey (NHANES)*.
- TEBOUL, A. *Diabetes Health Indicators Dataset*. Kaggle, 2021. (Origem do CSV entregue no trabalho.)

### Prática de projeto e documentação

- CHAPMAN, P. et al. *CRISP-DM 1.0: Step-by-step data mining guide*. SPSS/NCR, 2000.
- GEBRU, T. et al. Datasheets for datasets. *Communications of the ACM*, v. 64, n. 12, p. 86–92, 2021.
- MITCHELL, M. et al. Model cards for model reporting. In: *FAT\**, 2019.
- WILKINSON, M. D. et al. The FAIR guiding principles for scientific data management and stewardship. *Scientific Data*, v. 3, art. 160018, 2016.
- WILSON, G. et al. Good enough practices in scientific computing. *PLoS Computational Biology*, v. 13, n. 6, e1005510, 2017.

### Ferramentas

- HARRIS, C. R. et al. Array programming with NumPy. *Nature*, v. 585, p. 357–362, 2020.
- McKINNEY, W. Data structures for statistical computing in Python. In: *SciPy*, 2010.
- PEDREGOSA, F. et al. Scikit-learn: machine learning in Python. *JMLR*, v. 12, p. 2825–2830, 2011.
- SEABOLD, S.; PERKTOLD, J. Statsmodels: econometric and statistical modeling with Python. In: *SciPy*, 2010.
- VIRTANEN, P. et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. *Nature Methods*, v. 17, p. 261–272, 2020.

---

## 15. O que a bibliografia não cobre

Duas escolhas centrais deste projeto **não** têm referência canônica porque
nasceram da medição, não da literatura:

1. **O padrão "a ordem transfere, o nível não"** (`docs/23`) é consistente com
   Van Calster et al. (2019), mas a replicação em quatro transposições
   independentes — arquivo→população, EUA→Brasil, 2015→2023,
   `class_weight`→calibrado — foi medida aqui.

2. **Remover os marcadores de acesso do escore** contraria a prática usual de
   maximizar AUC. A justificativa é de desenho, não de literatura: um instrumento
   de rastreamento que exige exame prévio exclui quem mais precisa dele. O custo
   foi medido (4,2 milésimos de ROC-AUC) e considerado aceitável.

Ambas são falseáveis, e `docs/23` §"o que ficou de fora" diz com que dado.
