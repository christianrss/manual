---
id: independent-coding-assessment
title: "Avaliação independente: rotas com cupom e rodadas de tarefas"
description: "Resolva dois desafios originais de grafos sem solução antecipada, com contratos claros, fixtures, verificador e rubrica."
category: algorithms
difficulty: advanced
updated: 2026-10-09
prerequisites: [graph-traversal, shortest-paths]
sources:
  - {title: "Amazon SDE II Online Assessment Preparation", url: "https://amazon.jobs/content/en/how-we-hire/sde-ii-oa-prep", kind: "official employer guidance"}
  - {title: "Python unittest documentation", url: "https://docs.python.org/3/library/unittest.html", kind: "official language documentation"}
---
Entrevista de programação não é exercício de leitura: **reconhecer o algoritmo depois de ver uma solução não demonstra conseguir derivá-lo diante de requisito desconhecido**. Esta avaliação apresenta dois desafios originais independentes sem fornecer a implementação de referência. Você recebe especificação precisa, exemplos de entrada/saída, verificador e critérios de revisão. Deve produzir algoritmo, justificativa, complexidade e tratamento das fronteiras. Não são questões oficiais ou vazadas da Amazon. O guia público SDE II enfatiza código sintaticamente correto, escalável, manutenível e testado, não apenas pseudocódigo [1].

## Como executar a avaliação

Abra [unsolved_drills.py](https://github.com/christianrss/manual/blob/main/examples/python/unsolved_drills.py) no repositório. O arquivo declara duas funções que lançam `NotImplementedError`. Implemente respeitando os contratos. Execute o [verificador público](https://github.com/christianrss/manual/blob/main/examples/python/drill_grader.py) e crie depois seus próprios casos adversariais, ausentes do verificador.

Numa simulação, reserve 90 minutos para ambos os problemas, incluindo interpretação, código e testes. É **meta de prática**, não descrição obrigatória de distribuição de tempo em qualquer seleção. Registre decisões antes de procurar material externo. Ao finalizar, explique invariante, caso de falha e custo de tempo/memória para cada resposta.

## Desafio A: rota direcionada com um desconto

Receba um **grafo dirigido** de nós 0 até n−1 e arestas (u,v,w), onde w é inteiro não negativo. Saia do nó 0 e chegue a n−1. Você pode usar **um cupom no máximo uma vez**, reduzindo custo de uma única aresta percorrida de w para floor(w/2). Também pode não usar. Retorne o menor custo inteiro total, ou −1 se não há caminho dirigido.

O grafo pode ter arestas paralelas, self-loops, arestas de custo zero e ciclos. Caminhos podem repetir nós, embora ciclos de custo positivo não beneficiem a otimização com custos não negativos. Para n=1, a saída é zero sem cupom. O contrato avaliado tem n≥1 e IDs válidos; não invente regras de erros fora dessas condições. Explique como evitar overflow numa linguagem de inteiros fixos.

**Exemplo:** n=3 com arestas (0,1,9), (1,2,5), (0,2,30). A melhor resposta é **9**: percorra 0→1 com desconto floor(9/2)=4, depois 1→2 com custo 5. Aplicar desconto à aresta direta custaria 15. Descontar a maior aresta de todo o grafo nem sempre funciona, pois ela pode não estar em rota útil.

## Desafio B: rodadas mínimas de implantação paralela

Existem n tarefas de build/implantação numeradas 0 até n−1 e relações de pré-requisito (u,v): a tarefa u precisa **terminar numa rodada anterior** à tarefa v. Em uma rodada, qualquer número de tarefas elegíveis pode executar em paralelo. Determine o mínimo de rodadas sequenciais para concluir todas. Retorne −1 se houver ciclo dirigido, tornando a conclusão impossível.

Arestas duplicadas representam a mesma dependência e não devem aumentar artificialmente contagem. Tarefas independentes compartilham rodada um; conjunto vazio requer zero rodadas. Grafo pode ter componentes desconectados, losangos e cadeia longa. Não se trata de escalonamento com computadores limitados: suponha **trabalhadores ilimitados e tarefas com duração de uma rodada**. Mudar essas hipóteses altera o problema.

**Exemplo:** n=4, pré-requisitos (0,2),(1,2),(2,3), demanda **três rodadas**: {0,1}, depois {2}, depois {3}. Ciclo (0,1),(1,2),(2,0) retorna −1. Explique por que é impossível satisfazer requisitos “antes” em um ciclo.

## Casos públicos e execução

O verificador possui seis exemplos por problema, incluindo ausência de caminho, peso zero, nó único, dependência duplicada e ciclos. Você pode inspecionar fixtures, mas alterar resultados esperados **não** resolve a tarefa.

~~~python
from pathlib import Path
arquivos = [
    Path("examples/python/unsolved_drills.py"),
    Path("examples/python/drill_grader.py"),
]
assert all(arquivo.is_file() for arquivo in arquivos)
assert len(list(range(6))) * 2 == 12
~~~

Depois de implementar, execute na raiz do projeto:

~~~text
python examples/python/drill_grader.py
~~~

Até implementar, `NotImplementedError` é **proposital** e o verificador não será aprovado; o CI do site testa apenas as fixtures e a capacidade do verificador de rejeitar erros, sem incluir uma solução pronta. Doze exemplos não demonstram correção geral: tabela de respostas memorizadas poderia passar e falhar em qualquer grafo novo. Crie testes para grafos alterados, casos adversariais e entradas maiores [2].

## Argumento obrigatório de correção e complexidade

No Desafio A, identifique qual informação sobre **cupom disponível ou já usado** precisa acompanhar os estados da busca. Explique por que não pode misturar posições no mesmo nó com disponibilidade diferente. Justifique término sob ciclos, hipóteses sobre pesos e complexidade em n vértices e m arestas.

No Desafio B, explique quando tarefa se torna elegível, como a rodada mínima de uma tarefa depende das rodadas de seus antecessores e o que constitui prova de impossibilidade. Mostre por que arestas duplicadas não alteram a resposta. Conte quantas vezes cada tarefa e dependência são visitadas.

Não entregue apenas diagrama ou pseudocódigo: o produto esperado é uma **função executável**, com justificativa revisável. `unittest` permite comparar saídas esperadas; se gerar casos aleatórios, derive o oráculo independentemente da solução otimizada [2].

## Erros para testar contra si mesmo

| Erro | Efeito | Caso que revela |
| --- | --- | --- |
| Tratar aresta dirigida como bidirecional | Inventa caminho inexistente | Grafo sem retorno |
| Sempre descontar maior aresta | Pode não participar da rota ótima | Rotas alternativas |
| Alterar arestas fornecidas | Mutação indesejada no chamador | Reutilizar entrada |
| Ignorar componentes desconectados | Omite tarefas independentes | Pré-requisitos separados |
| Contar duplicatas duas vezes | Distorce elegibilidade | Mesma aresta repetida |
| Não detectar ciclos | Loop ou rodada falsa | Self-loop e ciclo longo |

## Rubrica de avaliação

Use autoavaliação de 100 pontos: 20 para contrato e bordas; 30 para implementação correta em testes desconhecidos; 20 para invariante/prova e término; 15 para complexidade; 15 para clareza e testes. É **rubrica educacional independente**, não esquema de pontuação da Amazon. Passar apenas nos casos visíveis não demonstra domínio.

## Exercícios e verificação

1. Implemente as duas funções sem mudar assinaturas nem memorizar as respostas da tabela.
2. Inclua arestas paralelas de pesos diferentes no Desafio A e justifique caminho ótimo.
3. Crie rota direta cara e alternativa com várias arestas na qual um desconto na alternativa vence.
4. Adicione self-loop ao Desafio B e confira retorno −1.
5. Depois dos casos públicos, gere entrada grande e confronte tempo medido com complexidade esperada.

**Capítulos relacionados:** [Caminhos mínimos](/pt/topics/shortest-paths/), [busca em grafos](/pt/topics/graph-traversal/), [oficina de algoritmos](/pt/topics/algorithm-interview-workshop/) e [testes](/pt/topics/testing-strategies/) oferecem técnicas de base, sem entregar essas implementações.
