---
id: testing-maintainability
title: Testes, contratos e manutenção segura
description: Aprenda a realizar alterações verificáveis com invariantes, testes de fronteira, contratos de integração, regressões e análise de riscos operacionais.
category: engineering
difficulty: intermediate
updated: 2026-10-09
prerequisites:
- complexity-analysis
sources:
- title: Google Engineering Practices — Code Review
  url: https://google.github.io/eng-practices/review/
  kind: engineering guidance
- title: Martin Fowler — The Practical Test Pyramid
  url: https://martinfowler.com/articles/practical-test-pyramid.html
  kind: engineering article
---
Código testável começa por um contrato: entradas válidas, saída esperada, efeitos colaterais e comportamento em falhas. Sem esse contrato, um teste que apenas verifica que a função foi executada não prova correção. O objetivo não é maximizar uma porcentagem isolada de cobertura, mas detectar violações importantes antes do usuário [1][2].

## Contrato e particionamento de casos
Separe valores típicos, fronteiras, entradas inválidas e interações entre componentes. Para um algoritmo que mescla intervalos, decida previamente se `[a,b]` e `[b,c]` devem ser considerados adjacentes e mesclados. Declare se intervalos invertidos são rejeitados. Teste essas decisões deliberadamente em vez de deixar a implementação defini-las por acidente.

## Exemplo verificável: mesclar intervalos
A pré-condição é uma lista de pares `(inicio,fim)` com `inicio≤fim`. Após ordenar por início, um intervalo novo pode ser incorporado ao último bloco enquanto `inicio≤fim_atual`, conforme política de extremidades fechadas. O invariante é que o resultado parcial contém intervalos ordenados, disjuntos e equivalentes à união do prefixo já processado.

```python
def mesclar_intervalos(intervalos):
    if any(a > b for a, b in intervalos):
        raise ValueError('intervalo inválido')
    resultado = []
    for inicio, fim in sorted(intervalos):
        if resultado and inicio <= resultado[-1][1]:
            resultado[-1] = (resultado[-1][0], max(fim, resultado[-1][1]))
        else:
            resultado.append((inicio, fim))
    return resultado

assert mesclar_intervalos([(1,3),(2,4),(6,8)]) == [(1,4),(6,8)]
assert mesclar_intervalos([]) == []
```

Para `n` intervalos, a ordenação domina o custo: `O(n log n)` tempo, mais `O(n)` memória no pior caso para saída e estruturas temporárias. Cópias internas da linguagem podem mudar detalhes de espaço, mas não a ordem do resultado.

## Hierarquia de testes
Teste unitário é adequado a regras isoladas determinísticas. Testes de contrato verificam formatos, semântica e compatibilidade entre cliente e serviço. Integração com banco verdadeiro revela diferenças de isolamento e transação que mocks não reproduzem. Teste end-to-end valida poucos fluxos críticos, porém costuma ser mais lento e frágil. Use a menor fronteira que consiga capturar o erro pretendido [1].

Mudanças em serviços distribuídos exigem verificar compatibilidade retroativa, tratamento de timeout, retries, idempotência e comportamento durante deploy parcial. Um teste verde em ambiente local não prova a mesma latência ou disponibilidade na produção.

## Revisão e segurança operacional
Um pull request deve explicitar contrato modificado, impacto nos consumidores, evidências dos testes, plano de rollback e telemetria esperada. Em ambientes críticos, feature flags, canary e alertas tornam uma mudança reversível. Evite refatorar vários domínios junto com uma correção pequena, pois isso aumenta a superfície de revisão sem melhorar a evidência de correção.

## Exercícios e verificação
1. Para intervalos fechados, explique por que `(1,2)` e `(2,3)` devem se mesclar; para intervalos semiabertos a política pode diferir.
2. Acrescente testes para intervalos invertidos, vazios, contidos e já ordenados.
3. Descreva o risco de um consumidor antigo receber campo obrigatório novo durante um deploy parcial.

A habilidade relevante é preservar contratos por meio de alterações pequenas e verificáveis.
