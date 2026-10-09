---
id: database-consistency
title: Transações, isolamento e consistência distribuída
description: Diferencie ACID, anomalias transacionais, serialização, linearizabilidade e defasagem de réplicas usando modelos explícitos de operações.
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites:
- complexity-analysis
- caching
sources:
- title: PostgreSQL — Transaction Isolation
  url: https://www.postgresql.org/docs/current/transaction-iso.html
  kind: official database documentation
- title: Jepsen — Consistency Models
  url: https://jepsen.io/consistency/models
  kind: technical reference
---
Consistência não é um único atributo que se liga ou desliga. Sistemas de armazenamento oferecem propriedades distintas para transações, ordem de operações e replicação. Um projeto correto começa por declarar **qual observação é proibida**: duas reservas da mesma vaga, leitura de saldo antigo ou perda de atualização. Documentos técnicos de PostgreSQL e materiais de sistemas distribuídos descrevem garantias que não devem ser confundidas [1][2].

## Transações e isolamento
Atomicidade significa que uma transação é aplicada por completo ou não é aplicada; durabilidade significa que seus efeitos confirmados sobrevivem conforme o contrato do sistema. Isolamento delimita como transações concorrentes podem observar efeitos umas das outras. `READ COMMITTED` normalmente impede leitura de valores não confirmados, mas pode permitir que duas leituras consecutivas dentro da transação vejam estados diferentes.

Uma anomalia de **atualização perdida** ocorre quando transações derivam mudanças do mesmo valor antigo e uma sobrescreve a outra. Um padrão de atualização condicional, restrições de unicidade e isolamento adequado podem impedir certas classes de erro. Não substitua esses mecanismos por um simples `if` na aplicação, pois outra instância pode modificar o mesmo registro entre a verificação e a escrita.

## Serialização versus linearizabilidade
Serializabilidade exige que o efeito de transações concorrentes seja equivalente a alguma execução serial. Linearizabilidade adiciona a exigência de respeitar a ordem real de operações que não se sobrepõem: se uma escrita terminou antes de uma leitura começar, a leitura não pode retornar um estado anterior dentro do modelo linearizável. São conceitos relacionados, porém não idênticos [2].

Replicação assíncrona pode deixar réplicas atrasadas em relação ao nó primário. Uma leitura feita em réplica pode ser aceitável para contadores de visualização, mas perigosa para autorização ou uma decisão de cobrança. A solução depende do requisito: leitura no primário, sessão consistente, versão mínima ou leitura após escrita coordenada.

## Exemplo: reservar um único recurso
Admita uma tabela `reservations` com restrição `UNIQUE(resource_id, slot)`. Dois clientes tentam reservar o mesmo recurso e horário. Uma aplicação que primeiro consulta e depois insere, sem restrição no banco, pode aprovar os dois pedidos sob concorrência. Com a restrição, apenas um insert pode confirmar para a mesma chave; o outro recebe conflito e precisa comunicar resultado adequado. A regra de unicidade é explícita, verificável e independente do número de processos de aplicação.

```sql
CREATE TABLE reservations (
  id BIGINT PRIMARY KEY,
  resource_id BIGINT NOT NULL,
  slot TIMESTAMP NOT NULL,
  UNIQUE (resource_id, slot)
);
```

## Falhas, limites e decisão
Conexão interrompida após `COMMIT` gera resultado **desconhecido** para o cliente: o servidor pode ter gravado apesar de a resposta não ter chegado. A repetição cega da operação pode duplicar efeitos. Use chaves de idempotência, confirmação por leitura e reconciliação. Não prometa consistência forte em toda a arquitetura apenas porque um banco local usa transações.

## Exercícios e verificação
1. Uma leitura em réplica atrasada viola linearizabilidade se a escrita já foi concluída antes de começar a leitura e o contrato exige essa propriedade.
2. Demonstre com dois clientes por que verificação de disponibilidade seguida de insert sem restrição permite corrida.
3. Simule uma conexão interrompida após commit: diferencie falha confirmada de resultado desconhecido e proponha mecanismo idempotente.

Especifique sempre o objeto protegido, o limite transacional e o comportamento de falha.
