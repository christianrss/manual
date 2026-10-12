---
id: sqlite-schema-migrations-user-version
title: "Migrações de esquema SQLite: user_version, compatibilidade e rollback"
description: "Evolua o esquema SQLite entre versões preservando registros, rejeitando estados inconsistentes e revertendo falhas."
category: databases
difficulty: foundational
updated: 2026-10-12
prerequisites: [sqlite-parameterized-crud-transactions]
sources:
  - {title: "SQLite — PRAGMA user_version", url: "https://www.sqlite.org/pragma.html#pragma_user_version", kind: "official SQLite reference"}
  - {title: "SQLite — ALTER TABLE", url: "https://www.sqlite.org/lang_altertable.html", kind: "official SQLite reference"}
  - {title: "SQLite — Transactions", url: "https://www.sqlite.org/lang_transaction.html", kind: "official SQLite reference"}
  - {title: "Python standard library — sqlite3", url: "https://docs.python.org/3/library/sqlite3.html", kind: "official Python documentation"}
---
O esquema de um banco muda à medida que o programa evolui. Uma aplicação pode começar com tabela contendo códigos de produtos e quantidades e, posteriormente, precisar armazenar uma descrição textual. Apagar e recriar a tabela destruiria registros existentes. Uma **migração de esquema** transforma de maneira controlada uma representação conhecida em outra, preservando os invariantes de dados prometidos pela aplicação [1][2].

## Diferencie esquema e registros armazenados

Um esquema define nomes de tabelas, colunas, restrições e relacionamentos. As linhas são instâncias de dados subordinadas à estrutura. Acrescentar coluna pode preservar compatibilidade com linhas antigas quando houver valor padrão apropriado; remover ou dividir colunas pode exigir transformação mais complexa.

Neste exemplo, a versão um contém tabela inventory com SKU obrigatório e quantidade inteira não negativa. A versão dois acrescenta description obrigatório cujo valor padrão é string vazia. A migração deve preservar cada SKU e quantidade existente e permitir que linhas anteriores recebam descrição vazia.

É uma sequência pequena e unidirecional. Sistemas de produção podem exigir versões distintas da aplicação acessando o mesmo banco, backups, janelas de manutenção e procedimentos de recuperação. Esses requisitos não estão automaticamente resolvidos por executar ALTER TABLE.

## Mantenha uma versão controlada pela aplicação

O SQLite oferece PRAGMA user_version, inteiro de 32 bits controlado pela aplicação e armazenado no cabeçalho do banco. **O SQLite não incrementa automaticamente esse valor quando uma tabela muda** [1]. O programa pode usá-lo como marcador, mas precisa mantê-lo coerente com as próprias migrações.

A versão zero representa o estado inicial neste exercício. A primeira etapa cria inventory e registra versão um. A etapa seguinte acrescenta description e registra versão dois. Executar migrate novamente sobre esquema válido de versão dois não deve repetir nenhuma transformação estrutural.

Não confunda user_version com schema_version. Este último participa de controles internos do SQLite para invalidação do esquema e não substitui um marcador mantido pela aplicação [1]. Manipular metadados internos para forçar a versão não corrige uma migração mal executada.

## Escolha uma mudança compatível

A instrução ALTER TABLE acrescenta description como TEXT NOT NULL DEFAULT ''. As linhas anteriores passam a observar o valor padrão documentado e mantêm suas colunas originais [2]. Isso é apropriado porque nenhuma linha histórica pode fornecer manualmente uma descrição desconhecida no momento da mudança.

Acrescentar campo obrigatório sem valor padrão apropriado a tabela já preenchida pode falhar. Alterar significados de colunas, dividir tabelas ou mover informações exige transformação explícita. A escolha entre string vazia e NULL também é uma decisão de domínio: aqui vazio indica que a descrição histórica não foi fornecida, sem inventar texto.

A restrição da quantidade verifica typeof(quantity) para impedir que um valor de ponto flutuante seja armazenado como quantidade não inteira apenas porque SQLite possui afinidade de tipos flexível. O esquema precisa impor o contrato de domínio, não confiar somente no nome do tipo declarado.

## Confirme esquema e versão numa mesma transação

Uma migração interrompida não deve deixar uma coluna nova presente com marcador de versão antiga, nem marcar uma versão nova antes que a coluna exista. O exemplo abre transação de escrita com BEGIN IMMEDIATE, executa as instruções separadamente e confirma a mudança estrutural junto com user_version [3][4].

Se algum comando ou verificação falhar, ROLLBACK descarta mudanças efetuadas dentro daquela transação. Em sqlite3 do Python, executescript pode realizar confirmação implícita de transação pendente conforme o comportamento documentado; utilizá-lo nesta transação sem compreender a fronteira seria incorreto [4]. Por isso usamos chamadas execute separadas.

Quando o banco possui versão futura desconhecida, a migração lança erro em vez de reinterpretá-lo como versão zero. Reverter esquema não é uma suposição segura; pode exigir transformação reversa desenvolvida e testada separadamente.

## Migração executável e verificação

O código opera sobre conexão SQLite configurada para controle transacional explícito. Após a migração, confere os nomes das três colunas esperadas. Essa verificação detecta algumas divergências entre marcador e estrutura, mas não prova que todas as restrições e índices correspondam exatamente a um esquema formal completo de versão dois.

~~~python
import sqlite3

def migrate(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            raise ValueError("unsupported schema version")
        if version == 0:
            db.execute("""
                CREATE TABLE inventory (
                    sku TEXT PRIMARY KEY NOT NULL,
                    quantity INTEGER NOT NULL
                        CHECK(typeof(quantity) = 'integer' AND quantity >= 0)
                )
            """)
            db.execute("PRAGMA user_version = 1")
            version = 1
        if version == 1:
            db.execute("""
                ALTER TABLE inventory
                ADD COLUMN description TEXT NOT NULL DEFAULT ''
            """)
            db.execute("PRAGMA user_version = 2")
        names = [r[1] for r in db.execute("PRAGMA table_info(inventory)")]
        if names != ["sku", "quantity", "description"]:
            raise ValueError("schema does not match version 2")
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise

db = sqlite3.connect(":memory:", isolation_level=None)
try:
    migrate(db)
    db.execute("INSERT INTO inventory(sku, quantity) VALUES (?, ?)",
               ("guitar-01", 4))
    migrate(db)
    row = db.execute(
        "SELECT sku, quantity, description FROM inventory WHERE sku = ?",
        ("guitar-01",)
    ).fetchone()
    assert row == ("guitar-01", 4, "")
    assert db.execute("PRAGMA user_version").fetchone()[0] == 2
finally:
    db.close()
~~~

## Preserve dados existentes e aceite reexecução

Para banco existente de versão um, uma linha como (guitar-01,4) precisa permanecer após a atualização, com description igual ao padrão vazio. Uma consulta parametrizada recupera esse registro. Nenhuma etapa de CREATE TABLE ou ALTER TABLE deve ser repetida quando o marcador está em dois e a verificação estrutural passa.

Reexecutar é importante porque scripts de implantação podem ser reiniciados quando seu status final é incerto. Idempotência significa aqui que executar migrate num banco válido de versão dois preserva os registros e colunas. Não significa que qualquer banco corrompido ou conflitante possa ser recuperado automaticamente.

Uma migração partindo da versão zero cria tabela, registra um e realiza a atualização à versão dois na mesma transação explícita. Se uma etapa posterior falhar, toda tentativa pode ser revertida, deixando o estado anterior em vez de uma versão intermediária inesperada [3].

## Contraexemplos e testes de falhas

Crie um banco versão um contendo registros e execute migrate. Confira quantidade preservada, descrição padrão e marcador dois. Reabra o arquivo e execute a mesma migração novamente, verificando que dados e colunas não sofreram mudanças.

Depois crie banco cujo marcador vale um, mas a tabela inventory não existe. ALTER TABLE precisa falhar e o marcador continuar em um. Banco marcado como versão dois sem a tabela esperada também deve ser rejeitado pela verificação estrutural. Versão 99 não deve provocar downgrade silencioso.

Esses testes separam três contratos: atualização correta de dados históricos suportados, rejeição de estados inconsistentes e estabilidade depois da atualização bem-sucedida. Executar apenas sobre banco novo e vazio não comprova a preservação de dados antigos.

## Custos e limites operacionais

Consultar marcador e nomes de colunas exige trabalho limitado para este esquema pequeno. O custo de alteração depende da versão do SQLite, das restrições, da necessidade de percorrer registros anteriores, da quantidade de dados e do filesystem. É incorreto afirmar que todas as migrações custam O(1) apenas pela quantidade pequena de instruções SQL [2].

Uma transação oferece fronteira lógica de atomicidade, enquanto recuperação de crash depende de configuração e armazenamento [3]. Antes de alterar banco de produção, preserve backups testados, valide compatibilidade das aplicações e defina estratégia de rollback ou reparação progressiva. O marcador automático de versão não substitui esses controles.

## Exercícios e verificação

1. Atualize arquivo SQLite versão um com registros existentes e demonstre que SKU e quantidade foram preservados.
2. Execute a migração duas vezes e compare colunas e quantidade de linhas.
3. Comece com marcador 99 e demonstre que a migração rejeita a versão sem modificar o esquema.
4. Prepare marcador versão um sem a tabela obrigatória e confirme rollback.
5. Explique por que atualizar user_version numa transação diferente da mudança estrutural abre uma janela de inconsistência.
6. Indique uma mudança de esquema que não possa ser feita com simples adição de coluna com valor padrão.

Continue com [CRUD transacional em SQLite](/pt/topics/sqlite-parameterized-crud-transactions/), [modelagem relacional](/pt/topics/relational-model-sql-basics/) e [persistência e recuperação](/pt/topics/database-storage-wal/).