---
id: formal-languages-finite-automata
title: "Linguagens Formais e Autômatos Finitos: AFD, AFN, Fecho Épsilon e Determinização"
description: "Fundamentos de AFD e AFN: linguagens regulares, fecho épsilon, determinização, provas e testes independentes em Python."
category: foundations
difficulty: intermediate
updated: 2026-10-11
prerequisites: [logic-proofs-invariants, discrete-relations-orders, graph-traversal]
sources:
  - {title: "MIT OpenCourseWare — 6.045J Automata, Computability, and Complexity, Lecture Notes", url: "https://ocw.mit.edu/courses/6-045j-automata-computability-and-complexity-spring-2011/pages/lecture-notes/", kind: "university lecture notes"}
  - {title: "Stanford CS103 — Guide to the Subset Construction", url: "https://web.stanford.edu/class/archive/cs/cs103/cs103.1244/guide_to_the_subset_construction", kind: "university teaching guide"}
  - {title: "MIT 6.045 (2019) — Finite Automata, Regular Expressions and Minimization", url: "https://people.csail.mit.edu/rrw/6.045-2019/", kind: "original university course outline"}
---
Um algoritmo pode reconhecer uma sequência específica de símbolos, mas um **reconhecedor de linguagens** decide se *cada sequência finita possível* pertence a um conjunto definido. Os autômatos finitos permitem formular essa distinção com precisão. Eles constituem o primeiro modelo numa sequência que inclui linguagens regulares, gramáticas, parsing, computabilidade e complexidade. Também fundamentam muitos reconhecedores léxicos. Neste capítulo, um autômato determinístico é construído e executado a partir de outro não determinístico, sem reduzir o tema a uma sintaxe de expressões regulares [1][3].

## Alfabeto, palavras, linguagens e reconhecimento

Um **alfabeto**, Sigma, é um conjunto finito de símbolos. Fixaremos Sigma = {0,1}. Uma **palavra** é uma sequência finita de símbolos do alfabeto. A palavra vazia é chamada épsilon e tem comprimento zero. Sigma-estrela representa todas as palavras finitas sobre Sigma, inclusive a vazia. Uma **linguagem** é qualquer subconjunto de Sigma-estrela. A linguagem L das palavras binárias terminadas em 01 contém 01, 001, 101 e 0101, mas não a palavra vazia, 0, 10 ou 011. Reconhecer uma linguagem significa decidir a pertinência da **palavra inteira**; localizar uma substring dentro de um texto maior é outro contrato.

Um analisador léxico de compilador identifica tokens num fluxo maior, portanto também necessita de regras para limites, maior correspondência, prioridade e caracteres inválidos. Essas necessidades são distintas do reconhecimento matemático: um autômato não é, por si só, um lexer com diagnósticos, Unicode, lookahead e localização de tokens. Além disso, motores de regex de linguagens de programação podem oferecer retroreferências (*backreferences*) que ultrapassam a capacidade de expressões regulares formais. Não se deve confundir esses dois modelos [3].

## Autômatos determinísticos e funções totais

Um autômato finito determinístico (AFD, ou DFA) é descrito pela quíntupla (Q, Sigma, delta, q0, F): conjunto finito de estados Q, alfabeto finito Sigma, função de transição **total** delta: Q × Sigma -> Q, estado inicial q0 em Q e conjunto de estados finais F contido em Q. Para uma palavra a1...ak, inicie em q0 e aplique delta a cada símbolo na ordem. Aceite somente quando o estado alcançado após **todos** os símbolos pertencer a F. A aceitação da palavra vazia depende exclusivamente de q0 estar ou não em F.

Para L igual às palavras que terminam em 01, considere os estados S (nenhum sufixo relevante), Z (o último símbolo é 0) e A (o sufixo atual é 01). As transições são S --0--> Z, S --1--> S; Z --0--> Z, Z --1--> A; A --0--> Z, A --1--> S. Apenas A aceita. Chegar a A **não interrompe a leitura**: acrescentar 1 à palavra 01 leva o autômato de volta a S, e 011 é rejeitada. Portanto, A não deve ser tratada como uma parada imediata.

Uma tabela de transições parcial pode tornar-se total mediante um estado sumidouro rejeitador com laços para todos os símbolos. Na construção deste capítulo, o **subconjunto vazio de estados de um AFN** desempenha esse papel automaticamente. Por outro lado, um símbolo que nem sequer pertence ao alfabeto é uma entrada inválida, não uma palavra válida rejeitada pela linguagem.

## Não determinismo, transições épsilon e semântica de caminhos

Num autômato finito não determinístico (AFN, ou NFA), cada par estado/símbolo pode possuir um **conjunto** de destinos. Também podem existir **transições épsilon**, que não consomem entrada. Uma palavra é aceita quando **existe pelo menos um caminho** que consome todos os símbolos e termina num estado final, admitindo transições épsilon antes, entre e depois dos símbolos. Não determinismo exprime uma condição existencial sobre caminhos: não significa necessariamente aleatoriedade, execução paralela ou adivinhação numa máquina real [1].

O **fecho épsilon** E(S) é o conjunto de estados alcançáveis a partir de S por zero ou mais arestas épsilon. Inclui os estados originais e precisa terminar mesmo diante de ciclos épsilon. Para avançar um conjunto corrente S sobre o símbolo a, reúna todos os destinos das arestas rotuladas a que saem dos estados de S e depois calcule o fecho épsilon do resultado. Assim, o estado efetivo do AFN é o **conjunto de estados possíveis**, não um único caminho arbitrariamente escolhido.

No exemplo executável, os estados são 0, 1, 2 e 3. O inicial 3 possui transição épsilon para 0. O estado 0 tem laços em 0 e 1, podendo adicionalmente seguir por 0 até 1. O estado 1 consome 1 e alcança o estado final 2. Um caminho de aceitação escolhe qual zero dá início ao **último** 01 da palavra. Como o estado 2 não tem arestas de saída, esse caminho só aceita se a entrada acabar ali.

## Construção por subconjuntos e equivalência AFD/AFN

Na construção por subconjuntos, cada estado do AFD é um subconjunto dos estados do AFN. O estado inicial do AFD é E({q0}). Para um subconjunto S e símbolo a, a transição determinística calcula o fecho épsilon da união de todos os destinos rotulados a alcançáveis a partir de S. Um subconjunto é final se possuir **ao menos um** estado final do AFN. O procedimento percorre apenas os subconjuntos alcançáveis, evitando construir os demais [2].

O exemplo começa em {0,3}. Ler 0 produz {0,1}; a seguir, ler 1 produz {0,2}, que aceita. Acrescentar outro 1 resulta em {0}, que rejeita. Apenas quatro subconjuntos distintos são alcançáveis, embora um AFN de quatro estados possa, em princípio, formar até 2^4 = 16 subconjuntos. Quando alcançável, o subconjunto vazio transita para si mesmo com qualquer símbolo do alfabeto. Não é obrigatório construir todos os subconjuntos possíveis.

**Invariante de correção:** depois de ler qualquer prefixo w, o subconjunto atual do AFD coincide exatamente com o conjunto de estados do AFN alcançáveis após consumir w, incluindo movimentos épsilon admissíveis. O caso-base w igual à palavra vazia decorre do fecho inicial. Admitindo o invariante válido para w, a operação de movimento e fecho demonstra sua validade para wa. Logo, o subconjunto do AFD contém algum estado final se, e somente se, existir um caminho de aceitação no AFN. Esta indução demonstra equivalência para **todas as palavras finitas**, não apenas para os exemplos testados [1][2].

## Implementação executável do fecho e da determinização

O exemplo Python é autossuficiente, utiliza alfabeto binário, valida estados de origem e destino e transforma os subconjuntos alcançáveis em IDs inteiros no AFD. A estrutura do grafo é fornecida pelo exercício e não constitui um parser endurecido para objetos Python arbitrários e hostis. Ausência de transição no AFN significa ausência de destino; após a compilação, cada estado do AFD possui transições para os dois símbolos válidos.

~~~python
from collections import deque

ALPHABET = ("0", "1")

def epsilon_closure(seed, edges):
    """States reachable with zero or more epsilon (None) transitions."""
    found = set(seed)
    stack = list(seed)
    while stack:
        state = stack.pop()
        for target in edges.get((state, None), ()):
            if target not in found:
                found.add(target)
                stack.append(target)
    return frozenset(found)

def determinize(states, start, accepting, edges):
    """Compile a binary epsilon-NFA into a total DFA with integer state IDs.

    edges maps (state, symbol) to sets of destinations; None is epsilon.
    Returns (start_id, final_ids, dfa_edges, id_to_subset).
    """
    states = frozenset(states)
    accepting = frozenset(accepting)
    if not states or start not in states or not accepting <= states:
        raise ValueError("invalid state set or start/final state")
    for (source, symbol), targets in edges.items():
        if (source not in states or symbol not in (None, *ALPHABET)
                or not set(targets) <= states):
            raise ValueError("invalid NFA transition")
    initial = epsilon_closure({start}, edges)
    names = {initial: 0}
    pending = deque([initial])
    finals = set()
    dfa_edges = {}
    while pending:
        subset = pending.popleft()
        source_id = names[subset]
        if subset & accepting:
            finals.add(source_id)
        for symbol in ALPHABET:
            moved = {target for source in subset
                     for target in edges.get((source, symbol), ())}
            destination = epsilon_closure(moved, edges)
            if destination not in names:
                names[destination] = len(names)
                pending.append(destination)
            dfa_edges[(source_id, symbol)] = names[destination]
    return 0, frozenset(finals), dfa_edges, tuple(names)

def accepts_dfa(word, dfa):
    if type(word) is not str or any(ch not in ALPHABET for ch in word):
        raise ValueError("word must use the binary alphabet")
    state, finals, transitions, subsets = dfa
    for symbol in word:
        state = transitions[(state, symbol)]
    return state in finals

# A binary string ends in 01: the initial epsilon edge is intentional.
states = {0, 1, 2, 3}
edges = {(3, None): {0}, (0, "0"): {0, 1},
         (0, "1"): {0}, (1, "1"): {2}}
dfa = determinize(states, 3, {2}, edges)
assert len(dfa[3]) == 4
assert dfa[3][0] == frozenset({0, 3})
for word, expected in (("", False), ("01", True), ("101", True),
                       ("0101", True), ("010", False), ("11", False)):
    assert accepts_dfa(word, dfa) is expected
try:
    accepts_dfa("012", dfa)
    assert False
except ValueError:
    pass
~~~

A fila termina porque há um número finito de subconjuntos possíveis. A busca do fecho marca cada estado para evitar visitas repetidas, inclusive diante de ciclos. A correspondência entre subconjuntos e IDs inteiros pode ser inspecionada no retorno e evita representar o conjunto de estados possíveis durante a leitura de cada símbolo de uma palavra. Trata-se de um **compilador de autômatos**, não de um compilador completo de linguagem de programação.

## Complexidade, explosão de estados e limites do modelo

Seja m o número de estados do AFN, t o número total de arestas armazenadas e k a quantidade de símbolos do alfabeto (k=2 neste exemplo). Uma busca de fecho custa O(m+t) usando adjacências simples. Processar todas as k transições de um subconjunto descoberto custa no máximo O(k(m+t)) sob o modelo usual de operações unitárias em conjuntos com hash. Existem até 2^m subconjuntos, portanto um limite superior conservador de compilação é O(2^m × k × (m+t)), com O(2^m × (m+k)) para IDs, subconjuntos e tabela, além das arestas de entrada. São **limites de pior caso**; o exemplo executável não materializa dezesseis estados.

Uma vez construído o AFD com IDs inteiros e alfabeto fixo, reconhecer uma palavra de comprimento n exige O(n) consultas esperadas ao dicionário e O(1) memória de trabalho adicional, excluindo o autômato pré-compilado e a entrada. Também é possível simular diretamente o AFN, mantendo os estados alcançáveis a cada símbolo. Isso pode evitar uma compilação exponencial, mas exige trabalho proporcional aos conjuntos de estados durante a leitura. A melhor escolha depende do número de palavras analisadas e dos limites de memória.

Nem toda linguagem computável é reconhecível por autômato finito. Considere L_igual = {0^n1^n : n >= 0}. Se ela fosse regular, existiria um comprimento de bombeamento p. Para a palavra 0^p1^p, qualquer decomposição xyz com |xy|<=p e |y|>0 colocaria y somente entre os zeros. Remover y reduziria a quantidade de zeros sem reduzir os uns, produzindo palavra fora de L_igual, uma contradição. Isso **demonstra que a linguagem não é regular**. O lema do bombeamento fornece uma propriedade necessária das linguagens regulares; verificar alguns exemplos não prova regularidade. Linguagens com aninhamento arbitrário podem precisar de autômato com pilha ou parser que mantenha uma pilha explícita [3].

## Oráculo independente, ciclos e contraexemplos

Os seis testes incorporados ao exemplo não bastam para estabelecer equivalência. Um **oráculo independente** pode explorar diretamente configurações (posição da entrada, estado do AFN): arestas épsilon preservam a posição, enquanto uma aresta rotulada pelo próximo símbolo avança uma posição. Um conjunto de visitados impede loops infinitos. É possível comparar essa busca em grafo com o AFD compilado para todas as palavras binárias até determinado tamanho, incluindo a vazia. Como o oráculo não constrói subconjuntos nem calcula fechos, ele ajuda a detectar erros compartilhados pelo algoritmo principal.

Teste também estados iniciais que já aceitam, AFNs que não aceitam nenhuma palavra, transições ausentes que levam ao sumidouro vazio, ciclos épsilon, estados inalcançáveis e múltiplos caminhos concorrentes. Rejeite arestas inválidas em vez de aceitar silenciosamente estados fora do universo declarado. Testes gerados e enumerações finitas aumentam confiança, mas **não substituem a indução**: nenhuma quantidade finita de palavras comprova uma propriedade universal sobre uma linguagem infinita.

## Exercícios e verificação

1. Rastreie os prefixos épsilon, 0, 01 e 011 no AFN e no AFD gerado. **Verificação:** {0,3}, {0,1}, {0,2}, {0}; somente o terceiro prefixo é aceito.
2. Modifique o AFN para que o fecho épsilon do estado inicial inclua um estado final. A palavra vazia é aceita? **Sim**, pois o subconjunto inicial intersecta F.
3. Remova todas as transições rotuladas 1 dos estados do fecho inicial. Descreva o destino correspondente no AFD e seus sucessores. **Verificação:** subconjunto vazio, que permanece no sumidouro.
4. Demonstre por indução no comprimento da palavra que a construção preserva o conjunto de estados alcançáveis, incluindo movimentos épsilon **depois** do último símbolo.
5. Explique por que escolher apenas um caminho do AFN não simula não determinismo. Construa uma palavra aceita exclusivamente por outro caminho.
6. Uma expressão com retroreferência necessariamente define linguagem regular? **Não**: expressões regulares formais e recursos estendidos de motores possuem capacidades diferentes.

Este capítulo estabelece reconhecimento por estados finitos e determinização. Gramáticas livres de contexto e parsing, máquinas de Turing e indecidibilidade, classes de complexidade, compiladores e sistemas de tipos devem ser estudados em capítulos separados. A presente construção não substitui esses conteúdos.
