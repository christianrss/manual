---
id: sqlite-parameterized-crud-transactions
title: "Fundamentos de SQLite: CRUD parametrizado e transações atômicas"
description: "Construa e teste um repositório SQLite com parâmetros vinculados, limites de saldo e rollback transacional."
category: databases
difficulty: foundational
updated: 2026-10-12
prerequisites: [relational-model-sql-basics, python-error-contracts-resource-cleanup]
sources:
  - {title: "Python standard library — sqlite3", url: "https://docs.python.org/3/library/sqlite3.html", kind: "official Python documentation"}
  - {title: "SQLite — Transactions", url: "https://www.sqlite.org/lang_transaction.html", kind: "official SQLite reference"}
  - {title: "SQLite — CREATE TABLE constraints", url: "https://www.sqlite.org/lang_createtable.html", kind: "official SQLite reference"}
  - {title: "SQLite — Isolation", url: "https://www.sqlite.org/isolation.html", kind: "official SQLite reference"}
---
Um banco de dados relacional começa a servir uma aplicação quando o código consegue **armazenar registros, consultá-los e realizar alterações relacionadas sem deixar resultados parciais**. A sintaxe SQL isolada não estabelece um contrato completo. Transferir valores entre contas exige definir entradas permitidas, contas inexistentes, saldo insuficiente e comportamento quando a segunda atualização falha. Este capítulo conecta a modelagem relacional introdutória a um banco SQLite real e testes executáveis independentes [1][2].

## Defina o contrato dos dados

Represente cada conta por um identificador único de proprietário e saldo inteiro em centavos, evitando valores monetários aproximados com ponto flutuante binário. O saldo permitido está no intervalo fechado de zero até um milhão de centavos. O identificador é uma string Python não vazia de no máximo quarenta pontos de código. É um dado sintético, não autenticação nem identidade bancária real.

O esquema possui chave primária, restrição NOT NULL e condição CHECK. A chave impede proprietários duplicados e a restrição do saldo rejeita valores armazenados fora do intervalo [3]. A validação em Python continua necessária porque entradas podem apresentar tipos surpreendentes. Booleanos são subclasses de inteiros em Python; usar comparação exata de tipo evita aceitar True como se fosse um centavo.

A interface disponibiliza create_account, balance e transfer. Cada função deve declarar entrada válida, saída, erros e efeitos. Uma consulta de saldo devolve None quando a conta não existe, distinguindo esse caso de uma conta existente com saldo zero.

## Parâmetros não são texto-fonte SQL

O driver aceita placeholders: uma consulta com WHERE owner = ? recebe a string do proprietário separadamente do comando SQL [1]. Os caracteres de um nome aparentemente malicioso são comparados como dados literais. Eles não introduzem novos predicados quando são fornecidos por essa vinculação.

Interpolar entradas arbitrárias diretamente numa string SQL pode mudar o significado da consulta e permitir injeção. Placeholders protegem valores, mas **não substituem nomes de tabelas, colunas nem palavras-chave SQL**. Identificadores selecionados dinamicamente exigem política diferente, como lista fechada de nomes permitidos.

A vinculação também facilita revisão de código. A estrutura da consulta permanece constante enquanto os valores mudam. A aplicação não precisa reconstruir por conta própria todas as regras de escape de aspas.

## Transferência exige dois efeitos e um resultado

Transferir quantidade positiva de centavos entre contas diferentes provoca débito na origem e crédito no destino. Ambos devem ter sucesso ou nenhum pode ser confirmado. Se uma conta não existe, se a origem não tem saldo ou se o destino ultrapassaria o saldo máximo, a operação falha sem deixar transferência parcial.

O UPDATE da origem inclui a condição de saldo suficiente e deve atingir exatamente uma linha. O UPDATE do destino verifica quanto saldo pode receber e também precisa atingir uma linha. As condições são avaliadas pelo SQLite durante a gravação, evitando depender apenas de um SELECT anterior que poderia estar desatualizado. A quantidade de linhas afetadas é verificada explicitamente.

O modelo exclui tarifas, moedas diferentes, redes externas de pagamento, autorização e trilhas de auditoria. Esses são requisitos separados que não devem ser presumidos apenas porque a aritmética da transferência está correta.

## Declare a fronteira da transação

O módulo sqlite3 de Python possui vários modos de controle transacional. O exemplo configura isolation_level=None e envia explicitamente BEGIN IMMEDIATE, COMMIT e ROLLBACK, conforme o modo legado de transações documentado [1]. BEGIN IMMEDIATE solicita a transação de escrita antes das duas atualizações condicionais [2].

Se qualquer UPDATE falhar, ROLLBACK descarta a mudança parcial anterior. COMMIT ocorre somente depois que os dois efeitos são confirmados. O bloco de exceção também consulta a existência de transação ativa se uma etapa posterior falhar. O processo pode encontrar banco ocupado ou erros de I/O; deve propagar essas falhas em vez de declarar sucesso [4].

Utilizar a conexão como gerenciador de contexto em Python pode controlar confirmação e reversão, mas **não fecha automaticamente a conexão**. O exemplo executável libera o recurso no bloco finally, inclusive se alguma verificação falhar.

## Exemplo executável de contas

O código utiliza o driver SQLite da biblioteca padrão com banco em memória, mas funciona igualmente com arquivo num diretório temporário. Os valores monetários são inteiros, as consultas vinculam parâmetros e o exemplo de erro exercita rollback por destino inexistente.

~~~python
import sqlite3

MAX_CENTS = 1_000_000

def open_db(path):
    db = sqlite3.connect(path, isolation_level=None, timeout=2.0)
    db.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            owner TEXT PRIMARY KEY NOT NULL,
            balance_cents INTEGER NOT NULL
                CHECK (balance_cents BETWEEN 0 AND 1000000)
        )
    """)
    return db

def create_account(db, owner, cents):
    if (type(owner) is not str or not 1 <= len(owner) <= 40
            or type(cents) is not int or not 0 <= cents <= MAX_CENTS):
        raise ValueError("invalid account")
    db.execute("INSERT INTO accounts(owner, balance_cents) VALUES (?, ?)",
               (owner, cents))

def balance(db, owner):
    row = db.execute(
        "SELECT balance_cents FROM accounts WHERE owner = ?", (owner,)
    ).fetchone()
    return None if row is None else row[0]

def transfer(db, source, destination, cents):
    if (type(source) is not str or type(destination) is not str
            or not 1 <= len(source) <= 40
            or not 1 <= len(destination) <= 40
            or source == destination or type(cents) is not int
            or not 1 <= cents <= MAX_CENTS):
        raise ValueError("invalid transfer")
    db.execute("BEGIN IMMEDIATE")
    try:
        debited = db.execute("""
            UPDATE accounts
            SET balance_cents = balance_cents - ?
            WHERE owner = ? AND balance_cents >= ?
        """, (cents, source, cents)).rowcount
        if debited != 1:
            raise ValueError("source missing or insufficient funds")
        credited = db.execute("""
            UPDATE accounts
            SET balance_cents = balance_cents + ?
            WHERE owner = ? AND balance_cents <= ?
        """, (cents, destination, MAX_CENTS - cents)).rowcount
        if credited != 1:
            raise ValueError("destination missing or balance limit")
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise

db = open_db(":memory:")
try:
    create_account(db, "ada", 900)
    create_account(db, "grace", 100)
    transfer(db, "ada", "grace", 250)
    assert (balance(db, "ada"), balance(db, "grace")) == (650, 350)
    try:
        transfer(db, "ada", "missing", 200)
    except ValueError:
        pass
    else:
        raise AssertionError("missing destination accepted")
    assert (balance(db, "ada"), balance(db, "grace")) == (650, 350)
    assert balance(db, "' OR 1=1 --") is None
finally:
    db.close()
~~~

## Demonstre o invariante principal

Sejam S e D os saldos de duas contas existentes e distintas antes da transferência de x centavos. As precondições são 1 <= x <= MAX_CENTS, S >= x e D <= MAX_CENTS-x. O débito produz S-x; o crédito produz D+x. Portanto, a soma depois da transferência vale (S-x)+(D+x)=S+D. Ambos os saldos permanecem dentro dos limites do esquema.

Se o débito ou crédito não atingir nenhuma linha, a função lança erro antes do COMMIT. O rollback impede que uma das mudanças sobreviva como resultado de operação concluída. A condição CHECK oferece uma barreira adicional mesmo se um defeito na aplicação chegar ao banco [2][3].

O argumento trata de **uma transação SQLite**, não de dois bancos independentes nem de uma rede distribuída de pagamentos. Não demonstra processamento exatamente uma vez de solicitações externas nem impede que um cliente execute intencionalmente duas vezes a mesma transferência válida.

## Teste o banco real e reconheça os limites

Utilize arquivos SQLite temporários reais em testes independentes. Cadastre duas contas, execute transferência válida, feche e reabra o banco e confira os saldos persistidos. Teste destino ou origem inexistente, saldo insuficiente, proprietário duplicado, quantidade negativa, booleano, saldo máximo no destino e caracteres de aspas em nomes.

O SQLite coordena escrita e transações num arquivo de banco, mas o comportamento em falhas depende de journal, configurações de sincronização e sistema de arquivos [4]. Um teste local aprovado não prova que nenhuma alteração recente será perdida sob qualquer falha de energia.

O programa executa quantidade limitada de comandos SQL. A contagem de comandos é O(1), mas o custo real depende de índices, páginas de árvore B, disco, contenção e tamanho do banco. Uma quantidade constante de consultas não implica latência universalmente constante.

## Exercícios e verificação

1. Demonstre rollback após débito bem-sucedido quando a conta de destino não existe.
2. Confirme que saldo insuficiente nunca produz saldo negativo persistido.
3. Teste crédito que excederia o limite do saldo do destino.
4. Mostre que nome de proprietário com aspas é tratado como dado e não muda a consulta SQL.
5. Reabra o arquivo SQLite depois de transferência confirmada e confira os saldos.
6. Explique por que atomicidade de transação local não garante execução exatamente uma vez de uma requisição externa.

Continue com [modelagem relacional](/pt/topics/relational-model-sql-basics/), [migrações de esquema](/pt/topics/sqlite-schema-migrations-user-version/) e [consistência transacional](/pt/topics/database-consistency/).