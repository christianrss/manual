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


![Duas transações concorrentes desativam médicos diferentes após lerem ambos ativos, produzindo write skew.](/diagrams/database-consistency-invariant.svg)

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

## Dois níveis de concorrência diferentes

Dentro de um banco, o **isolamento transacional** limita anomalias entre transações concorrentes. Entre nós ou serviços replicados, o **modelo de consistência** descreve quais histórias de leitura e escrita são permitidas. O adjetivo 'forte' não especifica nenhum deles. Serializabilidade exige equivalência a alguma ordem serial de transações; **serializabilidade estrita** também respeita precedência em tempo real. Linearizabilidade aplica atomicidade em tempo real às operações de um objeto. Vincule cada garantia a uma interface concreta e a um modelo de falhas [1][2].

## Demonstração de write skew por invariante

Considere dois médicos, A e B, de plantão. O invariante é **ao menos um médico deve permanecer de plantão**. Duas transações leem A=true e B=true. T1 desativa A; T2 desativa B. Se o isolamento permite que ambas confirmem com base no mesmo snapshot, sem detectar a restrição entre linhas, o estado final é A=false, B=false. Nenhuma transação escreveu na mesma linha; impedir somente *lost update* não basta. Uma solução pode usar execução serializável com tratamento de abortos e tentativas ou esquema/bloqueios que imponham o invariante [1].

## MVCC e isolamento efetivamente oferecido

O controle multiversão (MVCC) permite a leitores e escritores observar versões confirmadas distintas segundo snapshots transacionais. Melhora determinados padrões de concorrência, mas **não garante serializabilidade automaticamente**. O Repeatable Read do PostgreSQL fornece snapshot estável com garantias específicas documentadas; Serializable acrescenta proteção contra anomalias de serialização e pode abortar transações. Quando apropriado, a aplicação deve saber repetir com segurança essas transações [1].

| Exigência | Falha sem proteção | Possível mecanismo |
| --- | --- | --- |
| Não sobrescrever versão recente | Lost update | Atualização condicional por versão |
| Manter ao menos um recurso ativo | Write skew | Serializable ou locks/constraints que preservem invariante |
| Leitura deve observar escrita concluída | Réplica obsoleta | Leitura autoritativa ou sincronização por versão |
| Efeito entre banco e broker | Publicação parcial | Outbox transacional e consumidor idempotente |

## Histórico e contraexemplo

Cliente A termina escrita `x=1` em `t1`; cliente B começa leitura em `t2>t1` e recebe `0` de réplica atrasada. Isso viola linearizabilidade de um registrador lógico, supondo que a escrita confirmada prometia visibilidade. A mesma história pode ser permitida por consistência eventual. Se o serviço promete 'ler os próprios escritos' **apenas numa sessão fixa**, a observação obsoleta de outro cliente ainda pode ser permitida. Defina o escopo da garantia [2].

## Transações distribuídas e problema da escrita dupla

Salvar pedido no banco e publicar evento no broker são efeitos distintos. Se o banco confirma antes da publicação e o processo cai, pode faltar evento. Se publica antes e depois o banco reverte, consumidores podem agir sobre estado inexistente. Um **outbox** grava alteração e registro de evento na *mesma transação local*; outro processo publica depois, possivelmente mais de uma vez, e o consumidor precisa ser idempotente. Não é uma transação global mágica e não fornece necessariamente ordem total entre partições.

## Verificação com históricos adversariais

Registre operações com instante de invocação, resposta, chave e valor observado. Teste operações simultâneas com barreiras, atrasos de réplicas e desconexões; compare histórias ao modelo prometido em vez de observar apenas o estado final. Para reservas únicas, use restrição de unicidade durável, não um teste prévio de disponibilidade seguido de gravação separada. Clientes sequenciais não revelam anomalias concorrentes. Consistência é contrato da aplicação, não slogan do banco.

## Exercícios e verificação
1. Uma leitura em réplica atrasada viola linearizabilidade se a escrita já foi concluída antes de começar a leitura e o contrato exige essa propriedade.
2. Demonstre com dois clientes por que verificação de disponibilidade seguida de insert sem restrição permite corrida.
3. Simule uma conexão interrompida após commit: diferencie falha confirmada de resultado desconhecido e proponha mecanismo idempotente.

Especifique sempre o objeto protegido, o limite transacional e o comportamento de falha.
