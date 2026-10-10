---
id: property-based-algorithm-testing
title: "Testes algorítmicos por propriedades: oráculos, shrinking e metamorfismo"
description: "Gere casos adversariais com Hypothesis e compare busca binária e subarrays com oráculos independentes."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [binary-search, algorithm-interview-workshop, testing-strategies]
sources:
  - {title: "Hypothesis — Introduction", url: "https://hypothesis.readthedocs.io/en/latest/tutorial/introduction.html", kind: "official library documentation"}
  - {title: "Hypothesis — Replaying failed tests", url: "https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html", kind: "official library documentation"}
---
Alguns exemplos escolhidos manualmente não estabelecem correção de algoritmos em todas as entradas permitidas. **Testes baseados em propriedades** definem relações gerais—como resultado otimizado igual ao de um oráculo independente—e geram muitos casos, inclusive combinações não previstas pelo autor. Hypothesis para Python também tenta **reduzir** uma falha a um contraexemplo menor, frequentemente mais útil que entrada aleatória enorme [1][2]. É ferramenta para descobrir defeitos, não prova de ausência de entradas problemáticas.

## Comece pelo contrato, não pelo gerador

Para lower bound, considere lista de inteiros em ordem não decrescente e alvo inteiro. Devolva primeiro índice cujo valor ≥ alvo, ou comprimento se não existir. Gerador de arrays desordenados viola contrato; ordenar uma lista arbitrária produz entrada válida. O oráculo independente não deve copiar a mesma ramificação da busca binária: varredura linear é mais fácil de auditar.

No problema de menor subarray, valores negativos são permitidos. O alvo é positivo e a saída é o menor comprimento de janela contígua não vazia cuja soma é ≥ alvo, ou −1 quando não existe. Um oráculo quadrático ou cúbico de enumeração é aceitável em listas curtas, mas inviável para milhões de números.

## Oráculo gerado para lower bound

Hypothesis separa uma **estratégia** de geração de entradas válidas de uma **propriedade** que deve valer. Compare busca otimizada com varredura direta. Verifique também que todos os elementos antes da posição encontrada são menores que o alvo e que os elementos restantes são maiores ou iguais.

~~~python
from hypothesis import given, settings, strategies as st

def limite_inferior(valores, alvo):
    esquerda, direita = 0, len(valores)
    while esquerda < direita:
        meio = esquerda + (direita - esquerda) // 2
        if valores[meio] < alvo:
            esquerda = meio + 1
        else:
            direita = meio
    return esquerda

@settings(max_examples=60, deadline=None)
@given(st.lists(st.integers(-20, 20), max_size=20),
       st.integers(-25, 25))
def conferir_limite(brutos, alvo):
    valores = sorted(brutos)
    esperado = next((i for i, v in enumerate(valores) if v >= alvo),
                    len(valores))
    resultado = limite_inferior(valores, alvo)
    assert resultado == esperado
    assert all(v < alvo for v in valores[:resultado])
    assert all(v >= alvo for v in valores[resultado:])

conferir_limite()
~~~

Entradas ordenadas com duplicatas são comuns; erro de igualdade que salta valores iguais será detectado. O oráculo O(n) é adequado porque os tamanhos são limitados no teste. A busca otimizada continua O(log(n+1)) comparações sob acesso aleatório.

![Entradas geradas são comparadas a oráculo independente e falhas são reduzidas.](/diagrams/property-based-testing-loop.svg)

## Propriedades metamórficas quando falta oráculo completo

Um **oráculo** conhece a resposta esperada. Quando ele é caro ou indisponível, uma **propriedade metamórfica** relaciona resultados de entradas transformadas. Somar a mesma constante a cada valor da lista ordenada e ao alvo preserva o índice do limite inferior. É útil, mas **incompleto**: função incorreta que sempre devolve zero também satisfaz essa propriedade.

~~~python
@settings(max_examples=50, deadline=None)
@given(st.lists(st.integers(-10, 10), max_size=20),
       st.integers(-12, 12), st.integers(-100, 100))
def conferir_translacao(brutos, alvo, deslocamento):
    valores = sorted(brutos)
    assert limite_inferior(valores, alvo) == limite_inferior(
        [x + deslocamento for x in valores], alvo + deslocamento)

conferir_translacao()
~~~

Identifique implementações falsas que propriedades fracas aprovam. Combine oráculo independente, invariantes de fronteira, transformações e regressões conhecidas em vez de pressupor que centenas de entradas geradas bastam para um teste forte.

## Subarray com negativos e oráculo por enumeração

A solução otimizada usa somas prefixadas e deque monotônica; índices candidatos seguem em ordem e prefixos dominados saem. Um oráculo mais simples enumera todas as janelas contíguas, sem deque. Gerador deve incluir números negativos e prefixos iguais para encontrar os casos em que janela deslizante convencional falha.

~~~python
from collections import deque

def menor_subarray(valores, alvo):
    prefixos = [0]
    for v in valores:
        prefixos.append(prefixos[-1] + v)
    candidatos = deque()
    resposta = len(valores) + 1
    for direita, total in enumerate(prefixos):
        while candidatos and total - prefixos[candidatos[0]] >= alvo:
            resposta = min(resposta, direita - candidatos.popleft())
        while candidatos and prefixos[candidatos[-1]] >= total:
            candidatos.pop()
        candidatos.append(direita)
    return resposta if resposta <= len(valores) else -1

def oraculo_janelas(valores, alvo):
    melhor = len(valores) + 1
    for inicio in range(len(valores)):
        for fim in range(inicio + 1, len(valores) + 1):
            if sum(valores[inicio:fim]) >= alvo:
                melhor = min(melhor, fim - inicio)
    return melhor if melhor <= len(valores) else -1

@settings(max_examples=80, deadline=None)
@given(st.lists(st.integers(-5, 5), max_size=12),
       st.integers(1, 15))
def conferir_janelas(valores, alvo):
    assert menor_subarray(valores, alvo) == oraculo_janelas(valores, alvo)

conferir_janelas()
~~~

O oráculo é mais simples, não mais eficiente: slices e somas repetidas tornam o pior caso cúbico no tamanho máximo. Limite entradas geradas e jamais extrapole seu desempenho para produção; a solução com deque faz O(n) operações.

## Shrinking, regressões e reprodução

Hypothesis reduz entradas falhas quando possível [1]. Função que devolve valores ordenados únicos em vez de preservar multiplicidade falha com duplicatas, possivelmente no caso mínimo de dois elementos iguais. **Armazene esse contraexemplo** como teste explícito mesmo que próximas execuções não reproduzam o mesmo conjunto gerado.

A política de aleatoriedade do CI deve ser intencional. Hypothesis pode tornar execuções no CI determinísticas; para explorar novos casos ao longo do tempo, configure gerações variáveis e mantenha os exemplos mínimos em versionamento. Seed ou blob ajuda a investigar, mas fixture explícita tende a permanecer útil entre versões da biblioteca [2].

## Oráculos e erros comuns

| Falha | Verificação fraca | Evidência mais forte |
| --- | --- | --- |
| Condição de igualdade incorreta | Apenas valores distintos | Duplicatas e oráculo |
| Janela presume números positivos | Gerador só positivo | Negativos e zeros |
| Oráculo copia algoritmo | Mesma função comparada consigo | Brute force independente |
| Falha some na rodada seguinte | Só aleatoriedade | Regressão mínima versionada |
| Gerador viola pré-condições | Array desordenado para lower bound | Entradas dentro do contrato |
| Teste leva tempo excessivo | Brute force com listas enormes | Tamanho e orçamento limitados |

Propriedades geradas descobrem contraexemplos; não substituem **prova de invariantes**, análise de performance ou concorrência real. Por outro lado, prova do algoritmo não garante ausência de erro ao convertê-lo em código. As técnicas se complementam.

## Validação integrada ao CI

Esta edição adiciona `tests/test_property_based_sde_algorithms.py`, que carrega implementações publicadas em EN/PT e as compara com **oráculos escritos independentemente**. CI instala Hypothesis e executa testes dentro da suíte padrão. A oficina mantém distinção entre exemplos já resolvidos e **desafios propositadamente não resolvidos**: não publica respostas da avaliação independente.

Falhas geradas devem ser investigadas, minimizadas e preservadas como regressões antes de alterar o algoritmo. CI verde comprova apenas os casos e propriedades exercitados naquela execução, não todas as entradas possíveis.

## Exercícios e verificação

1. Troque comparação `<` por `<=` e encontre contraexemplo mínimo com duplicatas.
2. Proponha função errada que ainda satisfaz a propriedade de somar constante a todos os valores.
3. Adicione gerador de histogramas não negativos e compare área máxima a brute force.
4. Explique crescimento do tempo do oráculo ao aumentar comprimento máximo de 12 para 25.
5. Compare importância de fixture de regressão explícita e seed para reproduzir uma falha.

**Capítulos relacionados:** [Busca binária](/pt/topics/binary-search/), [oficina de subarrays](/pt/topics/algorithm-interview-workshop/), [testes](/pt/topics/testing-strategies/) e [verificação formal](/pt/topics/formal-model-checking/) fundamentam o método [1][2].
