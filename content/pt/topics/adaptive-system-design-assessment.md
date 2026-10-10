---
id: adaptive-system-design-assessment
title: "Oficina adaptativa de System Design: processamento sob novos requisitos"
description: "Reprojete pipeline multitenant conforme mudam tráfego, tenants ruidosos, panes, exclusão e residência dos dados."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, service-boundaries, asynchronous-messaging]
sources:
  - {title: "Amazon SDE II Interview Preparation", url: "https://amazon.jobs/content/en/how-we-hire/sde-ii-interview-prep", kind: "official employer guidance"}
  - {title: "AWS Builders Library — Avoiding Insurmountable Queue Backlogs", url: "https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/", kind: "original engineering guidance"}
---
Uma boa resposta de System Design é uma **sequência de revisões justificadas diante de novas restrições**, não um diagrama memorizado. Um entrevistador pode alterar tráfego, retenção, localização dos dados ou consistência depois da primeira arquitetura. A competência consiste em preservar invariantes, refazer dimensionamento, reconhecer novos modos de falha e justificar quando novos componentes compensam. Esta oficina original usa processamento multitenant de documentos; **não** é questão oficial ou recuperada de entrevistas. O guia público SDE II cita design e julgamento técnico sem especificar esse exercício [1].

## Rodada zero: defina o menor produto útil

Um SaaS recebe PDFs de tenants autenticados, extrai texto e oferece status pesquisável. O usuário envia POST /v1/documents com chave de operação, transfere arquivo para object storage autorizado, consulta GET /v1/documents/{id} e pode excluir documento. HTTP 202 significa **trabalho de processamento aceito de forma durável**, não extração concluída.

A tabela autoritativa registra documento, tenant, hash de conteúdo, estado, ponteiro do blob e versão. Object storage guarda bytes; fila durável alimenta workers; índice de busca é **visão derivada**, não autoridade para permissão ou exclusão. A primeira versão pode ser monólito modular e um banco, com workers separados, antes de justificar microsserviços independentes.

## Estados e autoridade dos dados

Documento passa por `uploaded → queued → processing → ready` ou `processing → failed`. Exclusão grava tombstone e deve eliminar depois blob e entradas derivadas. Defina se cliente pode repetir falhas e como versionar tentativa e documento. Se worker termina após exclusão, **não pode ressuscitar** índice nem visibilidade. Versão do registro e autorização atual precisam proteger o commit de conclusão.

![A arquitetura evolui de uma fila durável para capacidade consciente de tenants e regiões.](/diagrams/adaptive-system-design-drill.svg)

Upload e commit SQL normalmente não são uma transação ACID única. Faça persistência em etapas: reservar ID, subir objeto temporário privado, conferir checksum, registrar ponteiro processável e recolher uploads abandonados. Isso é mais preciso do que dizer “API grava blob e linha de uma vez”, pois explicita uma lacuna a testar.

## Primeira mudança: dimensione carga

Considere **120 mil documentos novos/dia**, tamanho médio **4 MiB** e tempo médio de extração **2 segundos de CPU por documento**, sem indexação e I/O. Isso representa 1,39 jobs/s em média, 468.750 MiB/dia (aproximadamente 468,75 GiB/dia) em bytes de entrada e 240 mil segundos de CPU por dia. Em pico 20×, a taxa é 27,8 jobs/s. Para suportá-la em workers que entregam **um segundo de CPU por segundo real**, cálculo simplificado exige aproximadamente 56 núcleos ocupados antes de folga e overhead.

É exercício hipotético. Carga OCR muda muito conforme páginas escaneadas, idiomas, compressão e hardware; **média pode esconder tarefas muito lentas**. Meça p95 do processamento e memória, não compre servidores apenas pela média. Declare se OCR faz parte do contrato e limite tamanho de arquivo.

~~~python
from math import ceil

def nucleos_minimos(documentos_por_dia, segundos_cpu_por_documento,
                    multiplicador_pico=1):
    if documentos_por_dia < 0 or segundos_cpu_por_documento <= 0 or multiplicador_pico <= 0:
        raise ValueError("carga invalida")
    pico_por_segundo = documentos_por_dia / 86400 * multiplicador_pico
    return ceil(pico_por_segundo * segundos_cpu_por_documento)

assert nucleos_minimos(120_000, 2, 20) == 56
assert nucleos_minimos(86_400, 1, 1) == 1
~~~

O resultado 56 é orçamento nominal com utilização idealizada, **não** quantidade recomendada para produção. Acrescente redundância, admissão e perfil de recursos medido.

## Segunda mudança: um tenant domina a fila

Novo requisito: um tenant passa a produzir **75% dos trabalhos** e muitos arquivos grandes. FIFO global permite que monopolize workers, atrasando outras contas. Redesenhe com limite de jobs simultâneos por tenant, escalonamento ponderado entre filas/partições e quotas de admissão antes de prometer um prazo impossível [2].

Isso também afeta cobrança e SLOs: requisição rejeitada por quota é distinta de job durável aceito e atrasado. Não prometa conclusão em cinco minutos quando backlog admitido não cabe nessa janela. Meça idade máxima e p95 por tenant, além de volume total.

## Terceira mudança: recuperar depois de pane

Suponha workers parados por **dez minutos** enquanto continuam chegando 30 jobs/s. Acumulam-se 18 mil trabalhos. Depois da recuperação, workers conseguem 50 jobs/s mas continuam chegando 30/s; sobram 20 jobs/s para drenar. São **900 segundos, ou 15 minutos**, com taxas constantes e sem retries [2].

~~~python
def segundos_recuperacao(chegadas, segundos_pane, capacidade):
    if chegadas < 0 or segundos_pane < 0 or capacidade <= chegadas:
        raise ValueError("margem positiva necessaria")
    from math import ceil
    return ceil(chegadas * segundos_pane / (capacidade - chegadas))

assert segundos_recuperacao(30, 600, 50) == 900
assert segundos_recuperacao(30, 600, 45) == 1200
try:
    segundos_recuperacao(30, 600, 30)
    assert False
except ValueError:
    pass
~~~

O cálculo de fluxo contínuo não limita p99, não inclui banda dos uploads nem retries caros. Pode ser necessário reservar capacidade de recuperação ou reduzir admissão temporariamente; fila não gera throughput adicional.

## Quarta mudança: exclusão e localização geográfica

Agora um tenant exige que documentos nunca saiam de uma região especificada. Roteamento por IP do usuário não implementa residência: pessoas viajam, caches de CDN existem e workers de background podem executar em outro lugar. Registre região como **restrição autoritativa do tenant** e fixe blobs, filas, workers, metadados e índices derivados nesse domínio. Failover entre regiões só ocorre quando a política permite, não por pressuposto de disponibilidade.

Outra exigência: documento deve ser excluído sob determinado prazo. Índice de busca demora a atualizar, portanto leitura deve conferir tombstone no banco **mesmo com índice atrasado**. Defina retenção também de backups, logs, arquivos temporários de processamento e texto derivado. Executar SQL `DELETE` não apaga magicamente todas as cópias.

## Quinta mudança: retries com respostas ambíguas

Se extrator escreve no índice e cai antes de confirmar job, broker pode repetir. Worker deve indexar por chave estável (documento, versão), usando upsert determinístico para impedir duplicatas. Se usuário excluiu documento enquanto isso, reconstrução do índice deve respeitar tombstone mais recente. É conflito de **autoridade versionada**, não simples loop de retry.

Timeout do POST após aceite também exige chave idempotente por tenant e fingerprint de payload. Mesma chave com arquivo diferente deve falhar ou seguir política explícita de conflito. Hash informado pelo cliente ajuda a detectar alteração, mas não substitui autenticação.

## Rubrica e decisões

| Exigência nova | O que repensar | O que deve permanecer correto |
| --- | --- | --- |
| Pico 20× | Workers, quotas e filas | Identidade durável por job |
| Tenant dominante | Justiça do escalonador | Isolamento entre contas |
| Pane de dez minutos | Margem e idade do backlog | Nada aceito desaparece silenciosamente |
| Restrição regional | Local de dados e execução | Sem movimento proibido de dados |
| Exclusão imediata | Tombstone e projeções | Documento excluído não é servido |
| Retry após timeout | Idempotência e versão | Mesmo pedido não vira dois |

Adote rubrica de 100 pontos: 20 para requisitos e contrato, 20 para capacidade, 20 para autoridade/consistência, 20 para falhas e 20 para comunicação dos trade-offs. É **rubrica educacional independente**, não pontuação da Amazon. Um diagrama elegante sem resposta para corrida de exclusão não basta numa revisão séria.

## Exercícios e verificação

1. Recalcule CPU nominal para 600 mil documentos/dia, custo médio 1,5 segundos e pico 8×.
2. Explique por que FIFO global pode quebrar justiça quando uma conta produz 75% dos jobs.
3. Desenhe teste de corrida entre exclusão por tombstone e conclusão da extração.
4. Indique componentes que devem permanecer regionais quando tenant possui regra estrita de residência.
5. Refatore a proposta quando chega **novo requisito**: arquivos são criptografados com chaves administradas pelo tenant que podem ser revogadas imediatamente. Cite hipóteses anteriores que deixam de valer.

**Capítulos relacionados:** [Método de System Design](/pt/topics/system-design-process/), [fronteiras de serviços](/pt/topics/service-boundaries/), [laboratório RabbitMQ](/pt/topics/rabbitmq-durable-consumer-integration/) e [recuperação de filas](/pt/topics/system-design-notifications/) ajudam na revisão [1][2].
