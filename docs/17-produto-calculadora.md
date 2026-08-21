> Abrir: `reports/produto/index.html` — duplo clique, funciona offline
> Reproduzir: `.\tasks.ps1 produto`

# O produto — calculadora de risco que roda no navegador

## O que é

Um **arquivo HTML de 59 KB** que estima o risco de diabetes a partir de 12
perguntas, roda inteiramente no navegador, **sem servidor e sem internet**, e
mostra *por que* chegou àquele número.

Feito para ser aberto no notebook durante a apresentação e usado pela plateia.

---

## Por que isso é possível — e por que não é um "modelo simplificado"

O EBM é **aditivo**:

```
logit P(y) = intercepto + Σ f_j(x_j) + Σ f_jk(x_j, x_k)
```

e cada `f` é uma **tabela de consulta sobre faixas**. Não há álgebra de matriz,
não há árvore para percorrer: são somas de valores tabelados.

Consequência: a predição cabe em ~25 linhas de JavaScript e devolve o **mesmo
número** que o Python — não uma aproximação, não um modelo menor.

```javascript
function prever(linha){
  let total = M.ebm.intercepto;
  for (const t of M.ebm.termos){
    let plano = 0;
    t.variaveis.forEach((v, k) => {
      let i = indice(linha[v], t.cortes[k]);          // 0 = ausente
      plano = plano * t.forma[k] + Math.min(i, t.forma[k] - 1);
    });
    total += t.scores[plano];
  }
  return 1 / (1 + Math.exp(-total));
}
```

### A garantia, verificada

| | |
|---|---|
| casos verificados | **500** |
| erro máximo Python ↔ JavaScript | **1,110 × 10⁻¹⁶** |
| tolerância exigida | 10⁻¹² |
| casos com valor ausente | 290 — todos válidos |

`tests/paridade_js.mjs` roda o **mesmo JavaScript da página** contra 500
predições do `sklearn`. **Faz parte da suíte de testes** (`test_produto.py`) e do
build (`.\tasks.ps1 produto`). Se divergir, o build falha.

> Isso importa mais do que parece: um erro de JavaScript não quebra a página —
> ela abre bonita e **não calcula nada**. Foi exatamente o que aconteceu na
> primeira versão (§ abaixo). Erro silencioso em apresentação ao vivo é o pior tipo.

---

## O que a calculadora mostra

| painel | conteúdo |
|---|---|
| **Risco estimado** | probabilidade, faixa qualitativa, e o **percentil** na população adulta americana |
| **Comparação** | você vs. EUA diagnosticado (10,7%) vs. EUA real com subdiagnóstico (14,3%) vs. Brasil capitais (7,1%) |
| **O que pesa** | contribuição de cada resposta ao logit, em barras divergentes |
| **E se mudasse** | contrafactuais só sobre o que é **acionável** — IMC, saúde percebida, pressão — e o efeito de 10 anos |
| **Escore de papel** | os 5 pontos de `docs/16`, com a faixa do usuário destacada na tabela |

As três referências vêm de bases diferentes (`docs/05`, `docs/09`, `docs/12`) —
é o diferencial de comparação múltipla aparecendo no produto, não só no relatório.

### Três decisões de projeto

**1. "Nunca fiz o exame" é resposta válida.** O EBM tem **faixa própria para
ausente**. Isso não é conveniência de interface: é o argumento de `docs/16` §2
implementado. Colesterol, renda e raça/etnia aceitam "prefiro não dizer" e o
modelo continua funcionando — com o score que ele aprendeu para quem não responde.

**2. Contribuição por variável, não por termo.** As interações são divididas
entre as variáveis que as compõem. Mostrar um termo `GENHLTH & _AGE80` para o
usuário seria exibir algo que não corresponde a nenhuma pergunta que ele respondeu.

**3. Contrafactuais só sobre o acionável.** O painel simula IMC, saúde percebida
e pressão — nunca idade, sexo ou raça. E o rótulo diz "simulação sobre o modelo,
não promessa clínica": mostra o que o modelo prevê para outro perfil, **não o
efeito causal** de mudar de hábito. `docs/07` §2.1 mostrou por que a distinção importa.

---

## Duas falhas encontradas ao construir, e o que ficou no lugar

### 1 · O `%` que quebrava tudo em silêncio

A primeira versão acessava `R.prevalencia_eua_diagnosticada_%` — e `%` **não é
identificador válido em JavaScript**. A página abria, ficava com aparência
correta e não calculava nada.

**Correção:** notação de colchete. **E o que ficou:** `node --check` roda no
JavaScript a cada build (`pagina.verificar_js`), e o processo falha em vez de
publicar HTML quebrado.

### 2 · `Infinity` não é JSON

O export continha `-Infinity` (vindo dos cortes `±inf` do escore). Python
serializa como `Infinity`, que **`JSON.parse` do navegador rejeita** — erro só em
tempo de execução, com a página já aberta.

O curioso: a verificação de paridade em Python **passou**, porque nunca
serializava para texto. A verificação estava testando a coisa errada.

**Correção:** `_finitizar()` troca não-finitos, e `json.dumps(..., allow_nan=False)`
faz o build falhar se algo escapar. **E o que ficou:** a verificação de paridade
agora faz **ida e volta pelo texto JSON**, que é exatamente o que o navegador
recebe.

> As duas falhas têm a mesma forma: **algo que só quebra em tempo de execução, no
> navegador, sem sinal visível.** As duas correções são a mesma: mover a
> verificação para o build.

---

## Desempenho do modelo do produto

| | |
|---|---|
| ROC-AUC (holdout) | **0,8421** |
| PR-AUC | **0,4460** |
| treino / holdout | 346.314 / 86.654 |
| termos | 20 (12 variáveis + 8 interações) |
| tamanho do JSON | 42 KB |
| tamanho da página | **59 KB**, autocontida |

É o mesmo EBM de `docs/13` — **94,4% do PR-AUC** do boosting de 60 variáveis, com
interpretabilidade total.

---

## O que a página diz sobre si mesma

O rodapé traz as métricas, o erro de paridade e as limitações — **na própria
página**, não só na documentação:

- o alvo é **diagnóstico autorrelatado**, não a doença (~27,6% não sabem);
- modelo treinado nos EUA, e **o IMC pesa ~16% menos no Brasil** (`docs/09`), logo
  o risco para brasileiros é provavelmente superestimado;
- raça/etnia entra como **proxy de determinantes sociais**, nunca fator biológico.

E o aviso clínico está no topo, antes de qualquer número: **isto não é um
diagnóstico**. Um teste (`test_pagina_e_autocontida`) verifica que ele não some
numa refatoração.

---

## Como usar na apresentação

```
1. abrir reports/produto/index.html          (duplo clique, offline)
2. preencher com um perfil qualquer
3. mostrar "O que pesa"                      -> explicabilidade nativa
4. mudar o IMC e ver o número reagir          -> o modelo é vivo, não um slide
5. escolher "nunca fiz o exame" no colesterol -> o argumento de acesso, na prática
6. rolar até o escore de papel                -> o entregável para a UBS
```

**Passo 5 é o momento da apresentação.** É onde o produto demonstra, em um clique,
a tese que o projeto inteiro sustenta: um instrumento de saúde que exige exame
prévio exclui exatamente quem mais precisa dele.

## Limitações

1. **Não é dispositivo médico** e não foi validado clinicamente.
2. **Calibrado nos EUA de 2015.** Uso no Brasil exige recalibração (`docs/09` §2.3).
3. **Prediz diagnóstico, não doença.** A versão PU (`docs/12`) seria a correta
   para rastreamento, e não está no produto — fica como próximo passo.
4. **Sem persistência**: nada é salvo, nada é enviado. É recurso de privacidade,
   mas significa que recarregar a página perde as respostas.
