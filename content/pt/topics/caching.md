---
id: caching
title: 'Cache: correção, invalidação e falhas'
description: Entenda cache-aside, TTL, leituras obsoletas, stampede e estratégias de falha sob requisitos explícitos de consistência, privacidade e escala.
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites:
- hash-tables
- capacity-estimation
sources:
- title: RFC 9111 — HTTP Caching
  url: https://www.rfc-editor.org/rfc/rfc9111
  kind: internet standard
- title: AWS Builders Library — Caching challenges and strategies
  url: https://aws.amazon.com/builders-library/caching-challenges-and-strategies/
  kind: engineering article
---
Cache armazena um resultado reutilizável próximo do consumidor para reduzir latência e carga na origem. Porém, ele também introduz uma segunda representação de dados. Por isso, uma decisão de cache afeta **correção**, consistência e disponibilidade, não apenas desempenho. HTTP define regras próprias de armazenamento e validação, diferentes das de um cache de aplicação [1][2].

## O contrato de validade
Defina a chave, o valor, as condições de validade, quem invalida e qual desatualização é tolerável. Se a resposta depende da identidade do usuário, permissões ou localidade, usar somente o endereço da página como chave global pode divulgar informações de outro usuário. Uma taxa de acertos `H` reduz a leitura básica da origem para aproximadamente `(1-H) × RPS` apenas quando cada erro de cache provoca exatamente uma leitura, sem revalidação paralela ou tempestade de misses.

Considere 10.000 leituras/s com 90% de acertos: a estimativa ingênua é 1.000 leituras/s na origem. Isso não representa um limite de pico; uma expiração sincronizada pode forçar muitas requisições concorrentes ao mesmo dado.

## Fluxo cache-aside
No padrão cache-aside, a aplicação consulta primeiro o cache. Se não encontrar a chave, consulta a fonte de verdade e tenta guardar o resultado com TTL. Valores jamais consultados não ocupam cache; por outro lado, um cache frio expõe diretamente a origem à carga [2].

```text
GET(chave) → existe em cache? → sim: devolver valor
                       não: ler banco → cache.set(chave, valor, TTL)
                                        → devolver valor
```

TTL limita a idade admissível de uma entrada não atualizada, mas não garante consistência imediata após escrita. Uma leitura concorrente pode recuperar uma versão antiga do banco e reinseri-la depois de uma invalidação. Para evitar a condição de corrida, considere chaves versionadas ou validação de versão ao publicar o resultado.

## Stampede e indisponibilidade
Quando uma chave popular expira, centenas de requisições podem recalcular o mesmo valor: *cache stampede*. Soluções incluem agrupamento de requisições por chave (single-flight), jitter de TTL, renovação antecipada e stale-while-revalidate sob limite temporal explícito. Dados bancários ou permissões não devem continuar obsoletos indefinidamente.

A falha do cache também exige política definida: ignorá-lo pode derrubar o banco por excesso de leituras, enquanto falhar fechado pode indisponibilizar o produto. Sistemas críticos precisam testar esses modos de falha, e não apenas medir hit rate.

| Estratégia | Benefício | Risco |
| --- | --- | --- |
| Cache-aside | Simplicidade | Misses concentrados |
| Write-through | Atualização no caminho de escrita | Acoplamento e latência |
| TTL curto | Menor desatualização normal | Maior carga na origem |
| Chaves versionadas | Dificulta sobrescrita antiga | Capacidade extra |

## HTTP não é Redis
`Cache-Control: no-cache` exige normalmente validação antes da reutilização, enquanto `no-store` proíbe o armazenamento intencional em caches conformes. Confundir as diretivas pode causar erros de privacidade. Um cache Redis não herda automaticamente a semântica de RFC 9111 [1].

## Exercícios e verificação
1. Dois usuários solicitam `/profile`. Defina uma chave segura incluindo identidade, ou impeça cache compartilhado.
2. Modele uma leitura antiga terminando depois da invalidação. Como impedir que ela recoloque o resultado obsoleto?
3. Com 4.000 req/s e 95% de acertos, a origem recebe cerca de 200 leituras/s no caso simplificado. Explique por que um stampede pode superar muito essa taxa.
