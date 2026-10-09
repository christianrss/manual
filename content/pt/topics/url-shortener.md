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

## Identidade da URL e semântica do redirecionamento

Um código curto é identificador público, **não token de acesso**. Se existirem destinos privados, autenticação e autorização devem ser independentes da dificuldade de adivinhar o código. Decida se links são mutáveis, como expiração é aplicada, se aliases customizados podem ser reassociados e se maiúsculas têm significado. Isso determina chaves de cache, esquema e possibilidades de abuso. Valide esquemas da URL por allowlist e trate redirecionamentos conforme política de segurança; URL sintaticamente válida também pode levar a destino malicioso.

Nos redirects, `301` e `308` comunicam permanência, ao passo que `302` e `307` são temporários, com distinções sobre preservação de método e corpo. Cache de navegadores e proxies pode dificultar revogação ou edição após redirecionamentos permanentes. Escolha código HTTP pelo contrato e teste clientes reais [3].

## Cálculo do espaço de identificadores

Um alfabeto de tamanho `b` e identificador de comprimento `k` permitem `b^k` combinações. Para Base62 e sete símbolos, são `62^7=3.521.614.606.208` códigos. Isso é capacidade, não proteção absoluta contra colisões aleatórias. Com amostras independentes e uniformes em espaço `M`, a aproximação do aniversário para a probabilidade de **ao menos uma colisão entre pares** em `n` amostras é `1-exp[-n(n-1)/(2M)]`, dentro de suas hipóteses. Imponha chave única no banco e repita conflitos atomicamente; não confie em 'verificar se existe e depois inserir' sem unicidade transacional.

## Rota de leitura com consistência explícita

Em `GET /{code}`, valide sintaxe, procure o mapeamento no cache se permitido, consulte a fonte de verdade em caso de falta, aplique expiração/revogação e responda com o status definido. Cache negativo de códigos inexistentes ajuda contra abuso, mas atrasa visibilidade de novo alias customizado. Exclusão ou edição precisa definir defasagem máxima admitida nos caches. Se revogação é crítica à segurança, TTL elevado sem invalidação coordenada contradiz a exigência.

## Capacidade e chaves extremamente populares

Para 100 milhões de redirects/dia, média aproximada de 1.157 RPS; assumindo pico 10×, cerca de 11.574 RPS. Um link popular pode concentrar grande parte das leituras; particionar uniformemente por chave **não garante** tráfego uniforme. CDN ou cache replicado absorvem hotspots quando cópias obsoletas são aceitáveis; análises podem ser assíncronas com tratamento de entregas duplicadas. Gravação e redirecionamento têm padrões de escala distintos e, portanto, orçamentos de desempenho próprios.

## Matriz de falhas

| Evento | Comportamento esperado | Solução |
| --- | --- | --- |
| Código aleatório duplicado | Repetir inserção | Constraint única e retries limitados |
| Banco indisponível, falta no cache | Erro controlado ou leitura obsoleta explicitamente permitida | SLO e contrato de defasagem |
| URL revogada em cache | Cumprir a política de revogação | Chave versionada / invalidação |
| Código popular satura shard | Pressão de filas/retries | Réplicas ou cache frontal |
| Redirecionamento malicioso | Rejeitar/quarentenar conforme política | Detecção de abuso e auditoria |

**Revisão:** a arquitetura mínima pode ser um serviço web sem estado e banco relacional, com cache apenas depois de necessidade medida. Não introduza coordenação distribuída para uma escala que as medições ainda não demonstraram.

## Exercícios e verificação
1. Se os links podem mudar, explique por que um `301` extensamente cacheado pode ser inadequado.
2. Compare códigos sequenciais base62 e códigos aleatórios quanto a unicidade, previsibilidade e tratamento de colisões.
3. Trace a operação quando o banco responde, mas a API perde a conexão: como reencontrar a criação anterior sem duplicar registros?

Uma solução defensável expõe hipóteses e comportamento em falhas, e evolui da arquitetura mínima quando os requisitos justificam.
