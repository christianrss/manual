---
id: evidence-based-interviews
title: Comunicar decisões técnicas com evidências
description: Estruture experiências profissionais em contexto, responsabilidade, ação, decisão e resultados mensuráveis, reconhecendo limites e trade-offs.
category: communication
difficulty: foundational
updated: 2026-10-09
prerequisites: []
sources:
- title: MIT CAPD — STAR Method for Behavioral Interviews
  url: https://capd.mit.edu/resources/the-star-method-for-behavioral-interviews/
  kind: university career guidance
- title: Google SRE Book — Postmortem Culture
  url: https://sre.google/sre-book/postmortem-culture/
  kind: engineering book
---
Explicar um projeto em entrevista técnica é diferente de enumerar tecnologias usadas. O entrevistador precisa compreender o problema real, sua responsabilidade, as alternativas consideradas, o critério de decisão e a evidência dos resultados. Uma descrição precisa informa o que ocorreu, não o que seria impressionante dizer [1].

## Contexto, ação e resultado
Uma estrutura útil é separar: situação, tarefa sob sua responsabilidade, ações realizadas e resultados observados. É semelhante ao método STAR documentado em orientações públicas de entrevistas. Mas a estrutura não substitui detalhes verificáveis: o candidato deve distinguir resultados coletivos de decisões próprias, e métricas antes e depois de alterações.

Por exemplo, dizer “melhorei a escalabilidade do backend” não explica o mecanismo. É mais claro formular: “o percentil 95 de latência aumentava após 1.200 req/s; instrumentei consultas, identifiquei falta de índice, propus índice seletivo, medi redução de leituras do banco e acompanhei erros durante rollout”. Valores numéricos devem ser reais ou rotulados claramente como exemplos. Evite atribuir causalidade a uma mudança quando outras variáveis se alteraram simultaneamente.

## Exemplo de comunicação técnica
Imagine que a aplicação teve aumento de erros após um deploy. A resposta rigorosa inclui linha do tempo, sinais observados, impacto ao usuário, hipótese inicialmente testada, verificação da causa, mitigação, correção definitiva e monitoramento posterior. A análise deve evitar buscar culpados e concentrar-se nos mecanismos e barreiras que falharam.

Ao responder uma pergunta de system design, comece com requisitos funcionais e não funcionais. Se a escala foi omitida, pergunte. Desenhe uma versão simples, estime volume de dados e consultas, identifique ponto de saturação e apresente alternativas com custos. O valor está em saber por que uma escolha é suficiente **sob hipóteses explícitas**.

## Trade-offs sem retórica
Quando compara monólito modular e microsserviços, não trate uma arquitetura como universalmente superior. Monólito reduz latência de chamadas internas e simplifica transações locais; microsserviços permitem evolução independente em alguns cenários, mas adicionam rede, observabilidade e consistência distribuída. Explique o contexto que mudaria sua decisão, a migração possível e o custo de operação.

Em histórias de liderança, comente como obteve consenso técnico, documentou discordâncias, recebeu críticas e mudou de abordagem quando medições contrariaram a hipótese. Atribuir resultados apenas a “trabalho duro” não demonstra raciocínio de engenharia.

## Preparação e validação
Construa fichas de projetos com problema, escala, restrições, alternativas, trade-offs, evidências e aprendizados. Treine respostas curtas seguidas de aprofundamento técnico quando solicitado. Se não souber um dado, explicite incerteza e apresente como faria a medição em vez de inventar um número.

Para incidentes, a cultura de postmortem sem culpabilização documentada no Google SRE favorece análise causal e correções sistêmicas [2].

## Narrativa causal de engenharia

Uma descrição de trabalho precisa separar **observação**, **hipótese**, **intervenção** e **resultado medido**. Se a latência caiu após implantar cache, não se conclui automaticamente que todo o ganho foi causado pelo cache: mistura de requisições, horário e mudanças simultâneas são fatores de confusão. Apresente janela de base, população, percentil medido, tamanho da amostra, alterações paralelas e incertezas restantes. Isso demonstra julgamento técnico, não apenas vocabulário decorado de entrevistas [1].

Use STAR como ferramenta de comunicação, não substituto de fatos técnicos. 'Situação' estabelece limites e restrições; 'Tarefa' distingue responsabilidade pessoal da equipe; 'Ação' deve mostrar alternativas rejeitadas e justificativa; 'Resultado' separa impacto medido de estimativa ou expectativa. Se não há dados do resultado, diga isso e descreva o que realmente foi observado.

## Escada de explicação arquitetural

Uma apresentação eficaz de arquitetura percorre: (1) requisito visível ao usuário; (2) metas não funcionais mensuráveis; (3) arquitetura-base plausível; (4) autoridade sobre dados e operações; (5) gargalo ou modo de falha concreto; (6) alternativa e trade-off; e (7) validação. 'Usar uma fila' é escolha de componente. 'Aceitamos tarefas de modo durável e processamos assincronamente porque conclusão em até 30 segundos é permitida; duplicatas são tratadas por chave única de negócio' é contrato defensável.

## Questione a própria proposta

Antes de apresentar uma solução, tente refutá-la. Se existe um banco único, explique uma pane. Se usa caches, mostre leituras obsoletas após escritas. Se repete chamadas, discuta idempotência e tempestades de retries. Se particiona dados, trate operações cruzadas e hot keys. Se escala horizontalmente, identifique o gargalo compartilhado. Não é necessário multiplicar componentes; complexidade deve entrar somente quando uma necessidade mensurável a justificar.

## Evidência comportamental sem inventar realizações

```text
Contexto: Observamos falha recorrente na condição X.
Responsabilidade: Eu projetei/implementei Y; a equipe cuidou de Z.
Restrições: Precisávamos preservar invariante I e entregar no prazo D.
Alternativas: A oferecia menor latência; B tinha recuperação superior.
Ação: Escolhemos B porque o invariante I não tolerava o risco de A.
Evidência: Testes T1/T2 e métricas M sustentaram a decisão.
Resultado: Descreva resultado observado, limites e próximos passos.
```

As letras são modelos, nunca números que devem ser inventados. Em projetos malsucedidos, trate lacunas de detecção e ações corretivas com o mesmo rigor de entregas bem-sucedidas. Revisões de incidentes sem culpabilização procuram falhas sistêmicas; não eliminam a responsabilidade por decisões efetivamente tomadas [2].

## Prática e rubrica

Grave explicação de dois minutos sobre um projeto. Verifique se outro engenheiro identifica problema, restrições reais, contribuição, medidas e alternativa plausível. Depois defenda a arquitetura com um requisito alterado: tráfego dobrado, réplica perdida, consistência estrita ou orçamento pela metade. Por fim, explique um incidente sem atribuir culpa pessoal e com passos concretos de prevenção. A avaliação mede raciocínio estruturado, não inglês perfeito ou confiança encenada.

## Exercícios e verificação
1. Reescreva “otimizei uma API” especificando métrica, baseline, ação e resultado, usando apenas dados realmente medidos.
2. Explique em dois minutos uma decisão que saiu errada, indicando como o diagnóstico mudou seus critérios técnicos.
3. Para um projeto pessoal, diferencie benchmark local de desempenho de produção e liste a hipótese de generalização.

Respostas sólidas dependem de evidência concreta e clareza causal, não de slogans de entrevista.
