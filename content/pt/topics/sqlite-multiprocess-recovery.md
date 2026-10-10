---
id: sqlite-multiprocess-recovery
title: "Oficina SQLite multiprocessos: reservas atômicas e recuperação"
description: "Teste processos reais, transações SQLite em arquivo, constraints de estoque e replay após encerramento abrupto."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [failure-recovery-workshop, transactional-indexing-isolation]
sources:
  - {title: "SQLite — Isolation In SQLite", url: "https://www.sqlite.org/isolation.html", kind: "official database documentation"}
  - {title: "SQLite — Atomic Commit", url: "https://www.sqlite.org/atomiccommit.html", kind: "official database documentation"}
  - {title: "AWS Builders Library — Idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
Simulação SQLite num processo ilustra transações, mas **não prova o comportamento quando duas aplicações independentes acessam o mesmo banco persistente**. Esta oficina transfere reserva para um CLI Python real, inicia processos do sistema operacional que competem, injeta encerramento imediato após commit e reabre o arquivo por outro processo. Verifica uma autoridade SQLite local real, não cluster nem broker remoto. SQLite documenta isolamento entre conexões e processos e serializa escritores no mesmo arquivo [1].

## Contrato e modelo de falhas

Um banco em arquivo começa com **três unidades disponíveis** de SKU `seat`. Dois clientes solicitam duas unidades cada, com chaves de operação diferentes. O invariante é `available >= 0`, portanto **somente um pedido pode ser aceito**; o outro recebe `insufficient`. Reserva bem-sucedida confirma reserva e intenção outbox única **na mesma transação**. Repetir chave aceita com mesmo payload devolve `replayed` sem consumir novamente.

Reutilizar chave com quantidade diferente produz conflito. Uma resposta **insufficient** não grava resultado idempotente neste protocolo didático; se estoque for reposto, repetir operação antes rejeitada poderá funcionar. É limite declarado, não semântica universal de pagamento ou estoque. Produto real pode persistir rejeições definitivas sob chaves por conta, conforme contrato.

## Processos não são threads

Threads podem compartilhar um Lock Python, mas dois processos CLI não compartilham aquele lock nem o heap do interpretador. A autoridade é o **arquivo SQLite**. Cada worker abre sua própria conexão `sqlite3.connect` e executa `BEGIN IMMEDIATE`, obtendo transação de escrita antes de verificar reserva e estoque. SQLite serializa escritores: um termina a transação enquanto outro espera ou recebe timeout de bloqueio [1][2].

![Dois workers independentes disputam estoque em SQLite; crash após commit conserva reserva e outbox duráveis.](/diagrams/sqlite-process-recovery.svg)

A demonstração está em [sqlite_process_race.py](https://github.com/christianrss/manual/blob/main/examples/python/sqlite_process_race.py). Os testes executam o script via `subprocess.Popen` e `subprocess.run`, não um mock. Fonte e testes acompanham o artigo para auditoria completa.

## Transação e argumento de correção

Primeiro, a transação consulta `reservations(op_key)` sob lock de escrita. Se a chave existir, compara quantidade e devolve `replayed`. Caso contrário realiza atualização SQL condicional:

~~~sql
UPDATE stock SET available=available-?
WHERE sku='seat' AND available>=?;
~~~

Com uma linha alterada, insere reserva e outbox, confirmando. Sem linha alterada, reverte e retorna `insufficient`. CHECK em available fornece camada adicional, mas não substitui comparação de quantidade e identidade da operação.

Atualização de estoque e inserts sob transação única garantem que reserva confirmada possua uma intenção outbox. PRIMARY KEY/UNIQUE protegem identidade. Isso é **atomicidade local de banco**: broker pode publicar duas vezes se relay falhar após enviar, e um provedor de pagamentos pode ter resultado ambíguo [3].

## Teste real com dois processos

O código executado a partir da raiz cria SQLite temporário e abre dois processos Python. Não depende de sleeps artificiais para provocar lost update. Ambos disputam a mesma autoridade; o multiconjunto correto tem exatamente um `accepted` e um `insufficient`.

~~~python
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

script = Path("examples/python/sqlite_process_race.py")
assert script.is_file()
with tempfile.TemporaryDirectory() as pasta:
    caminho = str(Path(pasta) / "estoque.sqlite")
    subprocess.run([sys.executable, str(script), "init", caminho],
                   check=True, capture_output=True, timeout=10)
    workers = [
        subprocess.Popen([sys.executable, str(script), "reserve", caminho,
                          f"cliente-{n}", "2"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
        for n in (1,2)
    ]
    resultados = []
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=10)
        assert worker.returncode == 0, stderr
        resultados.append(json.loads(stdout)["status"])
    assert sorted(resultados) == ["accepted", "insufficient"]
    with sqlite3.connect(caminho) as db:
        assert db.execute("SELECT available FROM stock").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM reservations").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM outbox").fetchone() == (1,)
~~~

Este teste executa **um cenário verdadeiro de disputa**, não prova todas as escalas e interleavings. A correção decorre de serialização e constraints do banco. Execute repetidamente e monitore busy errors para avaliar confiabilidade sob contenção maior.

## Injete saída do processo depois do commit

Um `os._exit(23)` termina o processo imediatamente após confirmar transação, ignorando limpeza usual do Python. Outro processo repete a chamada com a **mesma chave**, que precisa retornar `replayed`. Conexão nova comprova reserva e outbox persistidos. Exit anormal é esperado e **não** significa falta de commit.

~~~python
with tempfile.TemporaryDirectory() as pasta:
    caminho_db = str(Path(pasta) / "duravel.sqlite")
    subprocess.run([sys.executable, str(script), "init", caminho_db],
                   check=True, capture_output=True, timeout=10)
    falhou = subprocess.run(
        [sys.executable, str(script), "reserve", caminho_db,
         "checkout-7", "2", "--crash-after-commit"],
        capture_output=True, timeout=10)
    assert falhou.returncode == 23
    repetiu = subprocess.run(
        [sys.executable, str(script), "reserve", caminho_db, "checkout-7", "2"],
        check=True, capture_output=True, text=True, timeout=10)
    assert json.loads(repetiu.stdout)["status"] == "replayed"
    with sqlite3.connect(caminho_db) as db:
        assert db.execute("SELECT available FROM stock").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM outbox").fetchone() == (1,)
~~~

Isso demonstra recuperação após **saída de processo depois de commit SQLite concluído** no sistema de arquivos testado. Não simula corte de energia, dano físico, partição de rede, pane do host ou backups. Durabilidade física depende do modo de journal, configuração `synchronous`, filesystem e ambiente [2].

## Correção é diferente de disponibilidade

`BEGIN IMMEDIATE` torna a região crítica segura, mas cria **contenção**. Outro escritor espera ou termina por busy timeout; uma carga de escrita pode ser limitada pelo escritor único do SQLite. Portanto não conclua que o desenho escala arbitrariamente. Meça duração de transações, espera, erros de bloqueio e backlog sob carga representativa.

Para produção horizontal, é possível transferir a autoridade ao PostgreSQL ou outro banco com constraints e isolamento apropriados. Isso não elimina idempotência e necessidade de testes. Não substitua invariante verificado num banco por repositório fake não testado só porque ambos possuem um método chamado `reserve`.

## Matriz de falhas e contraexemplos

| Evento | Estado esperado | O que não é provado |
| --- | --- | --- |
| Dois processos pedem duas de três unidades | Um sucesso, saldo não negativo | Todas as falhas de host |
| Chave aceita repetida com mesmo corpo | Replay sem novo outbox | Escopo entre tenants |
| Chave aceita repetida com quantidade distinta | Conflito | Canonicalização de payload |
| Processo sai após commit | Linhas persistem e retry recupera | Perda de energia |
| Publisher cai após enviar | Outbox pode publicar novamente | Exactly once no destino |
| Banco atinge busy timeout | Requisição pode falhar | Disponibilidade universal |

## Exercícios e verificação

1. Altere estoque inicial para quatro e explique resultados das duas reservas concorrentes.
2. Acrescente terceiro processo com **mesma** chave e quantidade diferente; explique conflito.
3. Mostre por que um mutex interno em cada processo não coordena os dois compradores.
4. Injete falha logo antes do commit e confirme numa conexão nova que não existe reserva nem outbox daquela chave.
5. Rode o teste sob contenção repetida e registre tempos de espera sem enfraquecer invariante SQL.

**Capítulos relacionados:** [Oficina de falhas](/pt/topics/failure-recovery-workshop/), [índices transacionais](/pt/topics/transactional-indexing-isolation/), [oficina de concorrência](/pt/topics/concurrency-interview-workshop/) e [projeto de pedidos](/pt/topics/system-design-order-service/) sustentam o experimento.
