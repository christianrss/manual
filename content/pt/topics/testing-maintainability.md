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

## Particione o domínio antes de implementar

Uma suíte confiável nasce do contrato, não de exemplos aleatórios do caminho feliz. Separe entradas em classes de equivalência (válidas, inválidas, limites e malformadas) e identifique as transições entre elas. Na união de intervalos, diferencie entrada vazia, intervalo único, intervalos disjuntos, sobreposição, extremos fechados que se tocam, extremos invertidos, duplicatas e intervalos aninhados. Cada caso exercita uma hipótese. Teste comportamento independente da implementação: afirmar que um mock foi chamado não demonstra que os intervalos foram unidos corretamente.

## Propriedades verificáveis da união de intervalos

Para uma saída `out`, demonstre ao menos quatro propriedades: (1) início ≤ fim de cada intervalo; (2) ordenação por início; (3) intervalos consecutivos estritamente separados sob semântica de extremos fechados; (4) união dos pontos cobertos igual à da entrada. As propriedades (1)-(3) podem passar mesmo se (4) falhar ao perder um intervalo. Num domínio inteiro pequeno, compare a pertinência de cada ponto com um oráculo simples e independente.

```python
def coberto(intervalos, ponto):
    return any(inicio <= ponto <= fim for inicio,fim in intervalos)

for entrada in ([], [(1,3)], [(1,3),(3,5)], [(1,10),(2,4)], [(8,9),(1,2)]):
    saida = mesclar_intervalos(entrada)
    assert all(a <= b for a,b in saida)
    assert all(saida[i][1] < saida[i+1][0] for i in range(len(saida)-1))
    assert all(coberto(entrada,p) == coberto(saida,p) for p in range(-1,12))
```

## Contratos de integração e compatibilidade

Um contrato de API envolve mais que o formato JSON: códigos HTTP, paginação estável, timeouts, autenticação e idempotência podem fazer parte do comportamento observável. Testes de contrato orientados por consumidores identificam alterações incompatíveis, mas um esquema válido não prova que uma reserva jamais seja cobrada duas vezes. Invariantes persistidos exigem testes de integração com banco real e concorrência; resiliência exige injeção de falhas. Use relógios controláveis para testes de expiração e compare semântica, evitando testes dependentes de tempo real [2].

## Do pull request ao rollback

Uma mudança bem descrita apresenta motivação, interfaces afetadas, compatibilidade, ordem de migração, sinais de observabilidade e gatilho de reversão. Em migrações de esquema, adote expansão/migração/contração quando versões antigas e novas coexistirem: crie campo compatível, faça preenchimento ou leitura dupla quando necessário, mude leitores e só depois remova campos obsoletos. Um rollback pode ser inseguro se as novas gravações não forem compreendidas pela versão antiga. Planeje e ensaie recuperação *antes* da implantação.

## Limites dos testes automatizados

Testes unitários verificam exemplos e propriedades especificados, mas um conjunto finito de testes não prova correção universal. Alta cobertura de linhas pode coexistir com asserts fracos, condições de corrida ignoradas ou falhas operacionais. Revisão de segurança, testes de carga, análise estática e observabilidade acrescentam evidências diferentes. Analogamente, criar abstrações não constitui virtude automática: interfaces devem expressar contratos realmente variáveis, e não apenas reproduzir classes concretas [1].

## Exercícios e verificação
1. Para intervalos fechados, explique por que `(1,2)` e `(2,3)` devem se mesclar; para intervalos semiabertos a política pode diferir.
2. Acrescente testes para intervalos invertidos, vazios, contidos e já ordenados.
3. Descreva o risco de um consumidor antigo receber campo obrigatório novo durante um deploy parcial.

A habilidade relevante é preservar contratos por meio de alterações pequenas e verificáveis.
