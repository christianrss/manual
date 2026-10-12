---
id: relational-model-sql-basics
title: "Fundamentos de bancos relacionais: chaves, JOINs e integridade"
description: "Derive tabelas, chaves primárias e estrangeiras, normalização e consultas SQL com restrições e exemplos executáveis."
category: databases
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions]
sources:
  - {title: "PostgreSQL tutorial — SQL language", url: "https://www.postgresql.org/docs/current/tutorial-sql.html", kind: "official database tutorial"}
  - {title: "PostgreSQL documentation — Constraints", url: "https://www.postgresql.org/docs/current/ddl-constraints.html", kind: "official database documentation"}
  - {title: "SQLite documentation — Foreign key support", url: "https://www.sqlite.org/foreignkeys.html", kind: "official database documentation"}
---
Banco de dados relacional deve ser compreendido primeiro como **relações, chaves, restrições e consultas**, não como catálogo de produtos. Antes de estudar replicação, isolamento transacional ou persistência distribuída, é preciso explicar o que cada registro representa, quais valores o identificam, como tabelas se relacionam e por que uma consulta pode duplicar ou omitir linhas. SQL define operações de criação, atualização e consulta, enquanto as constraints preservam parte das regras de dados [1][2].

## Relações, tuplas, atributos e esquema

Uma relação possui atributos nomeados (colunas) e tuplas (linhas) com valores pertencentes a domínios definidos. A tabela SQL é representação prática, mas pode conter linhas duplicadas sem restrições e valores NULL, portanto não corresponde perfeitamente ao conjunto matemático. Um esquema define tabelas, colunas, tipos, valores padrão e condições de integridade. Cada tabela deve representar um conceito reconhecível: clientes armazenam atributos de clientes; pedidos representam compras; linhas ligam pedidos aos produtos adquiridos.

Escolher tipo de coluna é parte da modelagem. Preço em centavos inteiros evita arredondamentos de ponto flutuante binário em exemplo simples de moeda única que exige exatidão até centavos. Isso não define regras fiscais ou cambiais. Quantidade deve ser positiva e o banco pode impor CHECK, em vez de confiar somente na validação da aplicação.

## Chaves, unicidade e referências

Uma **chave candidata** é conjunto mínimo de atributos que identifica exclusivamente uma linha segundo o modelo. A chave primária seleciona um desses identificadores; constraints de unicidade podem proteger outras chaves candidatas. A **chave estrangeira** exige que valores apontem para uma chave válida da relação de destino e implementa integridade referencial [2]. Uma chave composta, como (order_id, product_id), usa os dois campos para identificar uma linha de pedido; cada campo isolado pode repetir.

Chaves expressam hipóteses de negócio. Se o mesmo produto puder aparecer várias vezes num pedido por diferenças de lote ou desconto, (order_id, product_id) deixa de ser identificador adequado. Pode ser necessário line_id ou posição da linha. O projeto começa pelo significado da identidade, não por copiar um esquema de dados de exemplo.

Chave estrangeira não autoriza automaticamente leitura de dados do cliente; índice único não implementa todas as políticas de negócio. Autorização e fluxos transacionais exigem decisões independentes. Chaves estrangeiras anuláveis podem ser permitidas dependendo do modelo; NOT NULL impede o caso. No SQLite, a integridade referencial precisa ser habilitada explicitamente na conexão deste exemplo [3].

## Dependências funcionais e normalização

Uma *dependência funcional* A → B afirma que atributos A determinam um único valor dos atributos B segundo as regras do domínio. Imagine tabela de pedidos que repete customer_name em cada linha de produto. Se customer_id determina customer_name, trocar o nome de um cliente obriga a atualizar várias linhas; uma atualização incompleta gera nomes contraditórios. Separar clientes de pedidos reduz essa anomalia.

A primeira forma normal (1FN) é ensinada como trabalhar com valores adequados aos domínios relacionais, sem grupos repetidos arbitrários numa mesma coluna. A segunda forma normal trata dependências indevidas de atributos não chave sobre parte de chaves compostas; a terceira trata certas dependências transitivas sobre chaves. Essas regras possuem definições formais. Afirmar apenas “nunca armazene listas” ou “toda tabela deve ter ID autoincremental” não basta.

Desnormalizar pode ser razoável por requisitos medidos de leitura e atualização, mas a informação duplicada então precisa de política de sincronização explícita. Normalização não garante desempenho superior nem correção automática de transações concorrentes.

## SELECT, JOIN, agrupamento e NULL

`SELECT ... FROM` constrói o resultado; `WHERE` filtra linhas, `JOIN` combina registros que satisfazem a condição de junção e `GROUP BY` organiza registros em grupos para agregações. INNER JOIN elimina linhas sem correspondência. LEFT JOIN preserva registros à esquerda e produz NULL para campos sem correspondência à direita. NULL não é string vazia nem zero; expressões que envolvem NULL frequentemente resultam em NULL, e predicados podem ter valor lógico UNKNOWN [1].

Um pedido sem linhas ainda deve aparecer num relatório que lista pedidos. A consulta abaixo usa LEFT JOIN e COALESCE para devolver total zero nesse cenário. Essa é uma **convenção do relatório**, não afirmação de que checkout real pode confirmar pedidos vazios. Preços das linhas são snapshots, para que futuras alterações do catálogo não modifiquem o total histórico.

~~~python
import sqlite3

db = sqlite3.connect(":memory:")
db.execute("PRAGMA foreign_keys = ON")
db.executescript("""
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL
);
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id)
);
CREATE TABLE order_lines (
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cents INTEGER NOT NULL CHECK (unit_cents >= 0),
    PRIMARY KEY (order_id, product_id)
);
""")
db.executemany("INSERT INTO customers VALUES (?, ?)",
               [(1, "Ada"), (2, "Grace")])
db.executemany("INSERT INTO products VALUES (?, ?)",
               [(10, "Book"), (11, "Pen")])
db.executemany("INSERT INTO orders VALUES (?, ?)",
               [(100, 1), (101, 2)])
db.executemany("INSERT INTO order_lines VALUES (?, ?, ?, ?)",
               [(100, 10, 2, 1250), (100, 11, 3, 200)])

result = db.execute("""
SELECT c.name, o.order_id,
       COALESCE(SUM(l.quantity * l.unit_cents), 0) AS total_cents
FROM orders AS o
JOIN customers AS c ON c.customer_id = o.customer_id
LEFT JOIN order_lines AS l ON l.order_id = o.order_id
GROUP BY c.name, o.order_id
ORDER BY o.order_id
""").fetchall()
assert result == [("Ada", 100, 3100), ("Grace", 101, 0)]

try:
    db.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)",
               (100, 999, 1, 100))
except sqlite3.IntegrityError:
    pass
else:
    raise AssertionError("foreign key was not enforced")

try:
    db.execute("INSERT INTO order_lines VALUES (?, ?, ?, ?)",
               (100, 10, 1, 100))
except sqlite3.IntegrityError:
    pass
else:
    raise AssertionError("duplicate composite key was accepted")

assert db.execute("SELECT COUNT(*) FROM order_lines").fetchone()[0] == 2
db.close()
~~~

## Demonstre os resultados, não apenas execute SQL

As inserções criam dois clientes, dois produtos e dois pedidos. Somente o pedido 100 possui linhas: 2×1250 mais 3×200 resulta em 3100 centavos. Pedido 101 não possui correspondência em order_lines, então LEFT JOIN o preserva; SUM resulta em NULL e COALESCE converte a zero. Se fosse INNER JOIN, pedido 101 desapareceria. Uma junção com condição errada pode multiplicar linhas e distorcer totais apesar da sintaxe válida.

O banco impõe dois invariantes: uma linha não pode referenciar produto inexistente e um par (order_id, product_id) aparece no máximo uma vez. O código verifica as duas violações. As regras observadas no SQLite dependem da configuração explícita usada; o mesmo texto SQL não demonstra que todos os dialetos implementam detalhes idênticos [3].

## Índices, custos e limites das fórmulas simples

Com n pedidos e m linhas de pedido, comparar ingenuamente cada pedido com cada linha pode custar O(nm) verificações candidatas. O otimizador pode usar busca indexada, hashing ou ordenação. Índices B-tree aceleram diversos filtros por igualdade e intervalo, mas exigem trabalho extra nas escritas e ocupam espaço. O plano depende de cardinalidade, seletividade, estatísticas e mecanismo do banco. Não declare que “JOIN é O(1)” ou que “índice sempre melhora tudo”.

Use `EXPLAIN` sobre volume representativo e inspecione varreduras, estimativas, contagens reais quando disponíveis e índices utilizados. Chave primária costuma possuir mecanismo de indexação em bancos comuns, mas a implementação e organização física variam. O fundamento mais importante é saber **qual resultado é correto** antes de tentar acelerar seu cálculo.

## Contraexemplos de modelagem

Guardar customer_name repetido em cada linha cria anomalia de atualização. Representar muitos-para-muitos sem tabela de ligação pode forçar coleções dentro de colunas, tornando a integridade difícil. A consulta `COUNT(*)` após LEFT JOIN contabiliza a linha preservada mesmo sem correspondência; `COUNT(l.product_id)` contabiliza apenas produtos presentes. No pedido 101, os resultados são diferentes.

Observe também a diferença entre erro de chave e erro de permissão. Um banco pode confirmar que o produto 10 existe sem demonstrar que o usuário autenticado tem autorização para consultá-lo. O serviço de aplicação precisa tratar a identidade do solicitante separadamente da integridade referencial.

## Exercícios e verificação

1. Troque LEFT JOIN por JOIN e preveja qual pedido desaparece; confirme com o exemplo.
2. Acrescente CHECK na quantidade, tente inserir zero e prove que os dados anteriores permaneceram intactos.
3. Permita produtos repetidos na mesma compra e proponha nova chave. Explique por que a chave composta original não serve mais.
4. Diferencie `COUNT(*)` e `COUNT(l.product_id)` num pedido sem linhas.
5. Escreva customer_id → customer_name e demonstre uma anomalia de atualização numa tabela propositalmente desnormalizada.
6. Compare índices (order_id, product_id) e (product_id, order_id) para consultas com diferentes filtros e prefixos.

Continue por [planejamento de consultas](/pt/topics/sql-query-planning/), [consistência de bancos](/pt/topics/database-consistency/) e [isolamento de transações](/pt/topics/transactional-indexing-isolation/) depois de dominar o modelo relacional.