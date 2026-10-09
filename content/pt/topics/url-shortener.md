---
id: url-shortener
title: 'Estudo de caso: projetar um encurtador de URLs'
description: Projete um serviço de URLs curtas desde requisitos e estimativas até identificadores, armazenamento, cache, disponibilidade e prevenção de abuso.
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites:
- capacity-estimation
- caching
- database-consistency
sources:
- title: RFC 3986 — Uniform Resource Identifier Syntax
  url: https://www.rfc-editor.org/rfc/rfc3986
  kind: internet standard
- title: OWASP — Unvalidated Redirects and Forwards
  url: https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
  kind: security guidance
- title: RFC 9110 — HTTP Semantics
  url: https://www.rfc-editor.org/rfc/rfc9110
  kind: internet standard
---
Um encurtador de URLs recebe um endereço longo, cria um identificador curto e resolve visitas futuras por redirecionamento. É um estudo de caso pequeno o bastante para ser desenhado em uma entrevista, mas rico em decisões de durabilidade, segurança, geração de identificadores e escala. Um desenho começa por requisitos, não por escolher serviços de nuvem [1].

## Requisitos antes dos componentes
Defina se URLs expiram, se códigos personalizados são permitidos, se haverá autenticação, proteção contra abuso, métricas, exclusão e atualizações. Diferencie a operação de criação da resolução do redirecionamento: esta tende a ser muito mais frequente, mas a razão real deve ser medida. Decida se códigos são sensíveis a maiúsculas, se URLs de destino são validadas e se redirecionamentos são temporários ou permanentes.

As métricas de disponibilidade e latência precisam de uma fronteira. Um link não encontrado pode retornar `404`; link removido pode ter comportamento diferente por política. Redirecionamento `301` pode ser armazenado em caches de navegador por mais tempo que um `302`, complicando mudanças futuras. A semântica de respostas HTTP deve seguir o contrato publicado [1].

## Cenário quantitativo explícito
Suponha dez milhões de novas URLs por mês e razão de 100 redirecionamentos para cada criação. A média de escritas é aproximadamente `3,86/s` num mês idealizado de 30 dias, enquanto leituras médias são `386/s`. Com pico dez vezes maior, planejamos em torno de `3.860/s` de leitura. Esses números são exemplos, não medições do tráfego de um produto real. Estime bytes por registro, índice e réplicas separadamente antes de escolher infraestrutura.

## API e fonte de verdade
Uma API mínima poderia aceitar `POST /links` com URL de destino válida e retornar código mais URL curta. `GET /{code}` resolve o código em banco autoritativo e devolve redirecionamento. A criação precisa definir idempotência para evitar resultados ambíguos quando o cliente repete uma requisição após timeout.

```text
Cliente → API → validação de URL → identificador → banco
Navegador → GET /{code} → cache → banco em miss → 302 Location: destino
```

![Caminho simplificado de criação e leitura de uma URL curta](/diagrams/request-path.svg)

## Identificadores e colisões
Uma sequência inteira codificada em base62 cria códigos curtos e exclusivos se os IDs forem exclusivos; porém códigos previsíveis permitem enumeração. IDs aleatórios reduzem previsibilidade, mas exigem detectar colisão com restrição UNIQUE e repetir a geração quando necessário. Distribuição de IDs entre regiões exige coordenação ou esquema com espaço de chaves dividido. Jamais assuma que strings aleatórias são únicas por definição.

## Cache, falhas e segurança
Leituras populares podem ficar em cache com TTL e invalidação apropriados. Se o destino puder mudar, escolha TTL e código de redirecionamento compatíveis. Um cache indisponível pode levar pico repentino ao banco, exigindo proteção. Para reduzir abuso, implemente limites de criação, classificação de destino e bloqueio de URLs maliciosas conforme política. Um encurtador público também pode virar ferramenta de phishing; não confunda funcionalidade com segurança operacional.

A validação de destinos deve considerar redirecionamentos não validados, risco documentado pela OWASP [2]. A diferença operacional entre códigos de status HTTP deve seguir a RFC 9110 [3].

## Exercícios e verificação
1. Se os links podem mudar, explique por que um `301` extensamente cacheado pode ser inadequado.
2. Compare códigos sequenciais base62 e códigos aleatórios quanto a unicidade, previsibilidade e tratamento de colisões.
3. Trace a operação quando o banco responde, mas a API perde a conexão: como reencontrar a criação anterior sem duplicar registros?

Uma solução defensável expõe hipóteses e comportamento em falhas, e evolui da arquitetura mínima quando os requisitos justificam.
