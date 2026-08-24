> Reproduzir: `.\tasks.ps1 causal` · saída `data/processed/gold/_causal.json`

# Camada causal — DAG, refutação e E-value

**Dados transversais não estabelecem causalidade. Nenhum método muda isso.** O que
esta frente faz é declarar as suposições em vez de escondê-las, derivar delas o
que ajustar, e **quantificar a fragilidade** do resultado.

**A pergunta:** atividade física reduz o risco de diabetes?

Escolhida porque `docs/07` §2.1 mostrou que o efeito aparente **desaparece** ao
entrar `saude_geral` (OR 0,852 → 0,988), e a leitura depende inteiramente de essa
variável ser mediador ou colisor. O DAG resolve a ambiguidade — **declarando** a
suposição, não provando-a.

---

## 1. O DAG, declarado

```
idade, sexo, raça, renda, escolaridade, emprego  →  CONFUNDIDORES
    (afetam tanto a atividade física quanto o diabetes)

atividade → IMC → diabetes                       →  MEDIADOR
atividade → hipertensão → diabetes               →  MEDIADOR
atividade → diabetes                             →  efeito direto

diabetes → saúde geral                           →  CONSEQUÊNCIA
diabetes → dificuldade de caminhar
atividade → saúde geral                          →  ⚠ COLISOR
```

Duas consequências que não são óbvias e mudam a análise:

- **ajustar por IMC estima o efeito *direto*, não o total** — e para saúde pública
  o que interessa é o total, que *inclui* a via pelo IMC;
- **`saude_geral` é colisor** (recebe seta de atividade *e* de diabetes).
  Condicionar nela abre viés — e é exatamente o que M2 e M3 de `docs/07` fazem.

---

## 2. A mesma pergunta, quatro respostas

| conjunto de ajuste | OR | IC 95% | n | leitura |
|---|---|---|---|---|
| sem ajuste (associação bruta) | **0,5099** | [0,489; 0,532] | 395.611 | confundida por idade e renda |
| **backdoor — só confundidores** | **0,6738** | **[0,641; 0,708]** | 326.137 | **efeito TOTAL, sob o DAG** |
| + mediadores | 0,8142 | [0,772; 0,859] | 271.456 | efeito **direto** — não é o total |
| + consequências (colisor) | **0,9769** | [0,923; 1,034] | 265.396 | **inválido** — viés de colisor |

> **Correção (auditoria).** Esta tabela publicava OR **0,7459** [0,719; 0,774] com
> n = 194.931. Dois defeitos, um de dado e um de método:
>
> 1. **`features/expandido.py` apagava `EMPLOY1 == 7` (aposentado)** e a categoria 7
>    de `INCOME2`. Como `_preparar` faz `dropna()` sobre os confundidores, o
>    conjunto backdoor **excluía sistematicamente os aposentados** — 222.804 linhas,
>    13,8 anos mais velhas e com 56% mais prevalência. Corrigido, o n vai a 326.137.
> 2. **O IC era calculado como amostra aleatória simples** — violação do invariante
>    11, que `models/explicativo.py` já respeitava. Agora o peso entra reescalado
>    pelo **n efetivo de Kish**, o que alarga o intervalo corretamente.
>
> O ponto estimado se moveu **mais** que o alargamento do IC: os intervalos novo e
> antigo **não se sobrepõem**.

> **A mesma variável responde "reduz 49%", "reduz 33%", "reduz 19%" ou "não faz
> nada", dependendo do que se ajusta.** O DAG é o que diz qual dessas quatro é a
> pergunta que se quis fazer.

**A última linha é `docs/07` M2/M3.** Lá o OR de 0,988 foi corretamente descrito
como "não pode ser lido como 'atividade física não importa'". Aqui está o motivo
formal: é viés de colisor, e o intervalo cruzando 1 é o sintoma.

**A estimativa causal é a segunda linha: OR 0,6738** — praticar atividade física
está associado a **33% menos chance** de diabetes, *sob as suposições do DAG*.

---

## 3. Refutação

Três testes. Sobreviver a eles **não prova causa**; falhar prova que não é.

| teste | esperado | obtido | veredito |
|---|---|---|---|
| placebo — tratamento embaralhado | 1,000 | **1,0001** | ✅ passou |
| confundidor aleatório acrescentado | 0,6738 | **0,6738** | ✅ passou |
| subconjunto aleatório (50%) | 0,6738 | **0,6917** | ✅ passou |

O placebo é o mais importante: se o efeito sobrevivesse ao embaralhamento do
tratamento, o modelo estaria capturando estrutura espúria.

---

## 4. E-value — o único número que não depende do DAG

O E-value (VanderWeele & Ding, 2017) responde: **quão forte teria de ser um
confundidor não medido** para anular o efeito observado?

| | valor |
|---|---|
| **E-value da estimativa** | **2,332** |
| E-value do limite do IC | 2,174 |

**Leitura:** um confundidor não medido precisaria estar associado *tanto* à
atividade física *quanto* ao diabetes por um risco relativo de **pelo menos 2,33
cada** — além de tudo que já foi ajustado — para explicar o efeito.

### A escala de referência que dá sentido ao número

E-value calculado do mesmo jeito para efeitos conhecidos nesta base:

| fator | OR ajustado | **E-value** |
|---|---|---|
| **hipertensão** | 3,884 | **7,23** |
| IMC (por 5 kg/m²) | 1,548 | **2,47** |
| **atividade física** | **0,674** | **2,33** |

O efeito da atividade física é **um pouco mais frágil que o do IMC** e muito mais
frágil que o da hipertensão. *(Antes da correção da auditoria o E-value era 2,02
contra 2,33 do IMC, e a leitura publicada era "tão frágil quanto". Com os dados
corretos os dois ficam próximos, com a atividade física ainda abaixo — a conclusão
qualitativa sobrevive, o número não era o certo.)*

### E há um candidato plausível a esse confundidor

**Capacidade funcional prévia.** Quem já está doente — por qualquer motivo — se
exercita menos. Essa variável não medida está associada à atividade física e ao
diabetes, e um RR de 2,0 para ela é **inteiramente plausível**.

> ### O veredito honesto
> O efeito **sobrevive a todas as refutações** e **não sobrevive a um
> confundidor plausível**. Isso não é contradição: a refutação testa a
> especificação; o E-value testa o que está fora dela.
>
> A conclusão defensável é: *"há associação de 33% de redução, robusta às
> covariáveis medidas, mas compatível com confundimento residual por
> capacidade funcional prévia — que os dados não medem."*

Note que isso é **mais forte** que o que `docs/07` conseguia dizer, e **mais
fraco** que "atividade física previne diabetes". As duas coisas ao mesmo tempo.

---

## 5. Síntese

| # | Achado | Consequência |
|---|---|---|
| 1 | O mesmo dado dá OR de **0,51 a 0,98** conforme o ajuste | O DAG não é formalidade: é o que define a pergunta |
| 2 | Estimativa causal do efeito total: **OR 0,674** [0,641; 0,708] | 33% menos chance, sob o DAG |
| 3 | Ajustar por mediador dá o efeito **direto** (0,864), não o total | Distinção que quase nunca é feita |
| 4 | `saude_geral` é **colisor** — M2/M3 de `docs/07` são inválidos como causais | Confirma formalmente o alerta de lá |
| 5 | Três refutações **passam** | A especificação é estável |
| 6 | **E-value 2,33** — pouco abaixo do IMC (2,47), muito abaixo da hipertensão (7,23) | O efeito é frágil a confundimento residual |
| 7 | Candidato plausível: **capacidade funcional prévia** | Conclusão fica em "associação robusta, causa não estabelecida" |

## 6. Limitações

1. **O DAG é uma suposição, não um achado.** Outro DAG defensável — por exemplo,
   com `saude_geral` como confundidor em vez de colisor — daria outra resposta.
   Publicá-lo é o que permite ao leitor discordar com precisão.
2. **Dados transversais.** Não há temporalidade: nada garante que a atividade
   física veio antes do diabetes.
3. **Causalidade reversa não modelada.** Quem recebe o diagnóstico pode passar a
   se exercitar mais (ou menos) — o DAG não tem essa seta e deveria ter, num
   desenho longitudinal.
4. **O tratamento é binário e grosseiro** (`_TOTINDA`: praticou atividade nos
   últimos 30 dias). Dose e intensidade não entram.
5. **O E-value supõe desfecho raro** para a aproximação do risco relativo. Com
   13,2% de prevalência a aproximação é razoável, mas não exata.
6. **O IC usa o n efetivo de Kish**, que é uma cota conservadora do efeito de
   desenho — não a linearização de Taylor com `_STSTR` e `_PSU` que `docs/11` §A
   usa para prevalência. O DEFF de 2,94 foi medido na amostra cheia; nesta
   subamostra de casos completos o Kish dá outro valor, então o fator exato aqui é
   desconhecido. Só a direção é certa: sem essa correção o IC era **estreito
   demais**, e foi assim que ele saiu publicado até a auditoria.
7. **A análise é de casos completos.** Mesmo corrigida a codificação, o `dropna()`
   sobre os seis confundidores descarta ~25% da amostra. Imputação múltipla
   mudaria o n e possivelmente o ponto.
