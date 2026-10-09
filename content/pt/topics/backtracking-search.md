---
id: backtracking-search
title: "Backtracking: espaço de estados, poda e correção"
description: "Derive árvores de busca com backtracking, segurança das podas, restrições de N-rainhas e limites de complexidade com testes."
category: algorithms
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis, graph-traversal]
sources:
  - {title: "MIT 6.006 — Introduction to Algorithms", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", kind: "university course"}
  - {title: "Python Standard Library — itertools combinatoric iterators", url: "https://docs.python.org/3/library/itertools.html", kind: "official documentation"}
---
**Backtracking** percorre decisões parciais e desfaz escolhas quando sua continuação não pode produzir uma solução válida. É uma **estratégia de busca**, não uma estrutura específica nem promessa de tempo polinomial. Uma solução precisa definir estados possíveis, ordem das decisões, restrições que devem permanecer verdadeiras e uma poda demonstravelmente segura para não eliminar respostas admissíveis [1].

## Modelagem da árvore de estados

Considere construir sequência de n símbolos, escolhendo um por profundidade. A raiz representa sequência vazia, cada aresta acrescenta escolha e cada folha corresponde a candidato completo. Com b opções por decisão, uma árvore sem poda pode conter 1+b+...+b^n nós, ou O(b^n) quando b>1. É um *limite para quantidade de estados*, não para o custo de examinar cada estado. Copiar uma solução parcial de comprimento O(n) a cada visita pode acrescentar fator n.

A distinção entre **permutações**, **combinações** e **subconjuntos** altera o universo de busca. Existem n! permutações totais de n itens distintos, C(n,k) subconjuntos de tamanho k e 2^n subconjuntos totais. O módulo itertools de Python fornece enumeradores independentes para conferir pequenas instâncias [2].

## Invariantes e podas seguras

Um procedimento recursivo busca(estado) deve preservar todas as restrições que já podem ser avaliadas com as escolhas parciais. A poda é **correta** apenas quando sua condição garante que nenhuma conclusão da ramificação satisfará o problema. Em N-rainhas, duas rainhas já posicionadas que se atacam nunca deixarão de se atacar pela adição de outras; pode-se podar imediatamente. Mas interromper busca quando uma pontuação parcial está abaixo da meta pode ser incorreto se decisões posteriores elevarem a pontuação.

Restaurar o estado também é essencial. Ao adicionar elementos a uma lista ou conjunto antes da recursão, é necessário removê-los depois, mesmo que uma busca interna falhe ou retorne cedo. Outra possibilidade é copiar estados imutáveis, consumindo memória adicional.

## Representação de N-rainhas

Coloque uma rainha por linha num tabuleiro n×n. Represente a solução como coluna de cada rainha, na ordem das linhas. Duas rainhas se atacam na mesma coluna ou diagonal; identidades das diagonais são linha-coluna e linha+coluna. Como cada chamada trabalha com linha diferente, o conflito de linhas já foi eliminado pela representação.

![Backtracking em N-rainhas: árvore de decisões e ramo rejeitado por conflito.](/diagrams/backtracking-tree.svg)

~~~python
def rainhas(n):
    if n < 0: raise ValueError("n deve ser nao negativo")
    solucoes = []
    colunas, diagonal1, diagonal2 = set(), set(), set()
    escolhidas = []

    def buscar(linha):
        if linha == n:
            solucoes.append(tuple(escolhidas))
            return
        for coluna in range(n):
            d1, d2 = linha-coluna, linha+coluna
            if coluna in colunas or d1 in diagonal1 or d2 in diagonal2:
                continue
            colunas.add(coluna); diagonal1.add(d1); diagonal2.add(d2)
            escolhidas.append(coluna)
            buscar(linha+1)
            escolhidas.pop()
            colunas.remove(coluna); diagonal1.remove(d1); diagonal2.remove(d2)

    buscar(0)
    return solucoes

assert rainhas(0) == [()]
assert len(rainhas(1)) == 1
assert rainhas(2) == [] and rainhas(3) == []
assert len(rainhas(4)) == 2
~~~

A contagem para n=0 segue propositalmente a convenção matemática de uma solução vazia. Outro contrato poderia rejeitar n=0; é indispensável documentar a escolha. Para n grande, armazenar todas as soluções pode consumir memória excessiva, mesmo se contar soluções por fluxo exigisse menos espaço.

## Demonstração de completude e unicidade

Demonstre por indução na linha. Na raiz, a escolha vazia é válida. Suponha que toda configuração válida nas primeiras r linhas corresponda a algum caminho recursivo único. Para qualquer tabuleiro completo válido, a rainha na linha r ocupa uma coluna c que não conflita com as anteriores; logo buscar não poda esse filho. Por indução, toda solução completa será alcançada. Cada linha experimenta uma coluna uma só vez, portanto uma sequência completa de colunas não se repete. O algoritmo é **completo e sem duplicação** sob essa representação.

## Tempo, memória e ramificações

Na profundidade r, no máximo n-r colunas estão livres, mesmo sem considerar diagonais. Há, portanto, no máximo n! configurações completas e, como cada nó experimenta até n colunas, um limite superior simples para o tempo dessa implementação é O(n·n!), não automaticamente O(n!). As podas reduzem muito os nós práticos, mas não garantem complexidade polinomial. Pilha e conjuntos usam memória auxiliar O(n), excluindo saída; guardar S soluções com n entradas exige Θ(Sn).

Em outros problemas, **propagação de restrições** reduz ramificações, enquanto **branch and bound** descarta estados cujo melhor resultado possível não supera o atual. Ambas exigem limites válidos: uma estimativa heurística qualquer não prova segurança de poda. Memoização ajuda quando caminhos diferentes alcançam de fato estados de futuro equivalente; caso contrário, ocupa memória sem benefício.

## Contraexemplos e alternativas

Algoritmo guloso escolhe uma opção local e não a revisita; backtracking pode desfazer, mas eventualmente examina combinações exponenciais. Programação dinâmica consolida subproblemas repetidos quando existe estado suficiente para representar o futuro. Backtracking é adequado a restrições combinatórias e instâncias controladas; resolvedores SAT ou de restrições podem ser melhores em problemas grandes e estruturados. Não memorize N-rainhas apenas pela 'profundidade': colunas e diagonais ocupadas alteram o futuro.

## Exercícios e verificação

1. Para n=4, confira soluções (1,3,0,2) e (2,0,3,1) e explique por que (0,1,2,3) é rejeitada.
2. Calcule permutações completas de quatro itens distintos: 4!=24. Compare gerador próprio com itertools.permutations como oráculo [2].
3. Proponha poda para soma de subconjunto com elementos restantes **não negativos** e demonstre por que números negativos impedem podar somente quando soma_atual>T.
4. Converta a função para gerar respostas sem armazená-las e identifique mudanças de memória e contrato.
5. Remova propositalmente escolhidas.pop() e explique qual invariante falha ao explorar ramificação irmã.
