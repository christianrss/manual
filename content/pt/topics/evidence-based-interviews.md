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

## Exercícios e verificação
1. Reescreva “otimizei uma API” especificando métrica, baseline, ação e resultado, usando apenas dados realmente medidos.
2. Explique em dois minutos uma decisão que saiu errada, indicando como o diagnóstico mudou seus critérios técnicos.
3. Para um projeto pessoal, diferencie benchmark local de desempenho de produção e liste a hipótese de generalização.

Respostas sólidas dependem de evidência concreta e clareza causal, não de slogans de entrevista.
