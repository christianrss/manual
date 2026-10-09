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

## Correção começa pela autoridade sobre os dados

Um cache armazena uma representação adicional de um valor. A **fonte de verdade** é o componente autorizado a determinar o estado atual; o cache fornece uma cópia sob uma política de validade. Se autorização ou saldo exigem o último estado confirmado, uma cópia obsoleta é erro de correção, não apenas de apresentação. Declare se a aplicação admite defasagem limitada, leitura dos próprios escritos ou garantias mais fortes [1].

A chave do cache deve incluir todos os parâmetros semânticos: tenant, idioma, paginação, permissões, flags ou versão do objeto quando aplicável. Se uma resposta depende do usuário, mas a chave contém somente a URL, o cache compartilhado pode revelar dados de outro usuário. Semânticas HTTP de `Vary` e `Cache-Control` tratam parte do problema de representações HTTP, mas não controlam automaticamente qualquer cache de aplicação [1].

## Cálculo da economia e da taxa de acertos

Considere taxa de leitura `R`, probabilidade de acerto `h`, latência do cache `Lc` e latência da origem `Lo`. Num modelo serial simplificado com latências constantes, tempo médio aproximado é `h×Lc+(1−h)×(Lc+Lo)`; carga na origem é `R(1−h)` somente se cada falta gera uma chamada e não há pré-atualizações. Para `R=20.000` RPS e `h=0,98`, faltas normais são 400 RPS. Se o cache falhar e todas as leituras contornarem-no, a origem recebe 20.000 RPS: **50 vezes** o volume habitual de faltas. A alternativa de emergência precisa ser testada em capacidade, não apenas codificada.

## Corrida que o TTL não resolve

Considere: cliente A não encontra a chave e lê a versão 4 do banco; cliente B grava versão 5, confirma e invalida o cache; A insere agora a versão antiga 4 no cache. O TTL limita a duração, mas não impede a **ressurreição de dado obsoleto**. Soluções variam: chaves imutáveis versionadas, comparação atômica de versões crescentes, invalidação coordenada ou leituras com token explícito de consistência. Cada solução tem custo e precisa de testes com escritores concorrentes [2].

## Expiração, remoção por capacidade e avalanche

**Expiração** determina quando uma entrada deixa de ser válida; **eviction** remove por falta de memória, possivelmente antes do TTL. LRU privilegia uso recente e LFU frequência; ambas podem ser inadequadas conforme a carga. Se milhares de clientes perdem a mesma chave simultaneamente, a combinação de requisições (*request coalescing*) mantém no máximo uma busca em andamento por chave **no escopo de coordenação escolhido**. Jitter de TTL diminui expiração sincronizada, mas não impede toda avalanche de faltas.

Para cache de resultados negativos, determine por quanto tempo 'não encontrado' pode persistir. Se o recurso for criado depois, um TTL negativo longo retarda sua visibilidade. Não armazene indiscriminadamente erros autenticados.

## Evidências exigidas antes de publicar

Documente chaves e cardinalidade, serialização, tamanho máximo do valor, orçamento de memória, distribuição de acessos, taxas de acerto por requisição e por byte, taxa de remoções, idade de cópias, carga da origem e comportamento quando o cache cai. Teste partida a frio e chave extremamente popular. Uma política correta pode preferir erro controlado a contornar o cache sem limites e derrubar a fonte de verdade [2].

## Exercícios e verificação
1. Dois usuários solicitam `/profile`. Defina uma chave segura incluindo identidade, ou impeça cache compartilhado.
2. Modele uma leitura antiga terminando depois da invalidação. Como impedir que ela recoloque o resultado obsoleto?
3. Com 4.000 req/s e 95% de acertos, a origem recebe cerca de 200 leituras/s no caso simplificado. Explique por que um stampede pode superar muito essa taxa.
