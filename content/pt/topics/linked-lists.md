---
id: linked-lists
title: "Listas ligadas: nós, inversão, ciclos e propriedade"
description: "Implemente e demonstre a inversão de lista simplesmente ligada e a detecção de ciclo de Floyd, comparando custos com arrays."
category: algorithms
difficulty: beginner
updated: 2026-10-09
prerequisites: [arrays-and-strings]
sources:
  - {title: "Princeton Algorithms — Linked Lists", url: "https://algs4.cs.princeton.edu/13stacks/", kind: "university textbook"}
---
Uma **lista simplesmente ligada** é uma sequência ordenada de nós. Cada nó guarda valor e referência ao próximo, ou referência nula para indicar fim. Diferentemente de um array dinâmico, nós não precisam ocupar posições contíguas. Inserir após um nó **predecessor já conhecido** exige mudar número constante de referências, mas encontrar essa posição pode demandar percorrer toda a lista [1].

## Invariante dos nós e contrato de representação

Uma lista vazia tem cabeça None. Uma lista acíclica não vazia começa na cabeça e seguir next visita cada nó exatamente uma vez antes de chegar a None. A ordem é determinada por ponteiros, não pelos endereços numéricos. Se existe tail, deve apontar sempre ao último nó, cujo next é None. Se existe campo de comprimento, ele precisa coincidir com os nós alcançáveis. Esses campos aceleram operações particulares, mas precisam ser mantidos corretamente.

Na sequência [8,3,5], a cabeça aponta a nó 8, que aponta para 3, depois 5, cujo next é None. Para inserir 4 na frente, crie nó com next=cabeça e atualize a cabeça. Para remover o primeiro, cabeça=cabeça.next. Ambas as operações alteram O(1) ponteiros, desconsiderando separadamente custo de alocação e liberação.

## Acesso por índice não é remoção por ponteiro

Para ler elemento i, comece na cabeça e percorra i ligações: O(i+1), com pior caso O(n). Inserir depois de **nó conhecido** custa O(1); inserir na posição arbitrária i exige localizar seu predecessor e pode custar O(n). Remover sucessor conhecido de predecessor conhecido também custa O(1) se propriedade dos nós e referências estão válidas. Remover valor específico exige localizá-lo.

Uma lista duplamente ligada armazena referências next e previous. Com nó conhecido, pode desconectar elemento intermediário em O(1), ao custo de mais um ponteiro por nó e invariantes mais exigentes. Nenhum dos tipos fornece O(1) para índice arbitrário. Em linguagens com coleta de lixo, nó removido pode permanecer alocado se outras referências o alcançam; em C/C++, ponteiro pendente pode violar segurança de memória.

## Inverter por reescrita de ligações

A inversão ilustra o invariante principal. Mantenha anterior como prefixo já invertido, atual como primeiro nó ainda não processado, e proximo como ligação temporariamente salva. Em cada rodada, atual.next=anterior; depois avance anterior e atual. O invariante é que anterior lidera o prefixo invertido e atual lidera o sufixo intocado, sem perder nenhum nó. Ao terminar, atual=None e anterior é a nova cabeça.

![Inverter lista ligada exige salvar próximo ponteiro antes de alterar a ligação.](/diagrams/linked-list-reversal.svg)

~~~python
class No:
    def __init__(self, valor, proximo=None):
        self.valor = valor
        self.proximo = proximo

def criar(valores):
    cabeca = None
    for valor in reversed(valores):
        cabeca = No(valor, cabeca)
    return cabeca

def listar(cabeca):
    saida = []
    while cabeca is not None:
        saida.append(cabeca.valor)
        cabeca = cabeca.proximo
    return saida

def inverter(cabeca):
    anterior = None
    atual = cabeca
    while atual is not None:
        proximo = atual.proximo
        atual.proximo = anterior
        anterior = atual
        atual = proximo
    return anterior

assert listar(inverter(criar([1,2,3]))) == [3,2,1]
assert inverter(None) is None
assert listar(inverter(criar([7]))) == [7]
~~~

Inverter custa O(n) de tempo e espaço auxiliar O(1), excluindo os n nós existentes. As funções de construção e conversão consomem O(n) separadamente; suas alocações não integram a alegação de memória da inversão. O algoritmo modifica os ponteiros de entrada; o antigo primeiro nó se transforma no último.

## Detectar ciclo com duas velocidades

Uma lista pode conter ciclo acidental: algum nó aponta para outro já visitado. Percorrer até None **nunca termina** nesse caso. O algoritmo da lebre e tartaruga de Floyd move um ponteiro um passo por vez, outro dois. Se existe ciclo, quando ambos entram, a distância relativa dentro de um ciclo de comprimento c avança de um em um módulo c; eles acabam coincidindo. Sem ciclo, o ponteiro rápido alcança None [1].

~~~python
def tem_ciclo(cabeca):
    lento = rapido = cabeca
    while rapido is not None and rapido.proximo is not None:
        lento = lento.proximo
        rapido = rapido.proximo.proximo
        if lento is rapido:
            return True
    return False

sem_ciclo = criar([1,2,3])
assert not tem_ciclo(sem_ciclo)
com_ciclo = criar([4,5,6])
com_ciclo.proximo.proximo.proximo = com_ciclo.proximo
assert tem_ciclo(com_ciclo)
assert not tem_ciclo(None)
~~~

Compare **identidade**, não igualdade: dois nós podem ter mesmo valor e ser diferentes. O algoritmo custa O(n) tempo até terminar ou encontrar encontro, usa O(1) memória e não altera ligações. Aqui só informa existência do ciclo. Descobrir sua entrada exige fase adicional com o ponto de encontro e a cabeça.

## Simulação de ponteiros passo a passo

Inverta 1→2→3. Inicialmente anterior=None, atual=1. Salve proximo=2 e atualize 1.next=None; anterior=1, atual=2. Salve proximo=3 e faça 2.next=1; anterior=2, atual=3. Salve proximo=None e faça 3.next=2; anterior=3, atual=None. Resultado: 3→2→1. Se omitirmos guardar próximo antes de alterar o ponteiro, podemos perder o restante da lista.

Em Floyd, considere 4→5→6→5. A partir de 4, lento vai a 5 enquanto rápido vai a 6; na rodada seguinte, lento vai a 6 e rápido chega ao mesmo nó 6 depois de duas ligações. As identidades coincidem e há ciclo. Dois valores iguais numa lista acíclica não justificam declarar ciclo.

## Comparação de custos e armadilhas

| Operação | Lista simples | Array dinâmico |
| --- | --- | --- |
| Ler índice i | O(i+1) | O(1) |
| Inserir na frente | O(1) | O(n) por deslocamento |
| Inserir no fim | O(1) com tail mantido | O(1) amortizado |
| Remover após predecessor conhecido | O(1) | O(n) no pior caso |
| Percorrer tudo | O(n) | O(n), frequentemente com melhor localidade |
| Memória extra por item | Ponteiro e alocação | Referências em buffer compacto |

Listas ligadas não são automaticamente mais rápidas porque alterar ponteiros é barato. Alocação de nós, faltas de cache e falta de acesso por índice podem dominar. Linguagens com memória manual ainda introduzem responsabilidade de vida útil. Para várias cargas, um array contíguo vence apesar da vantagem assintótica de inserção.

## Quando o algoritmo é inadequado

Nunca aplique inverter a lista cíclica sem tratar ciclos: pode não terminar ou corromper ligações. Um nó sentinela pode simplificar casos-limite, mas não deve ser confundido com dado do usuário. Duas listas que compartilham nós interferem entre si: inverter uma altera a estrutura observada pela outra. Mutações concorrentes durante percurso exigem sincronização ou snapshot seguro. Numa lista dupla, next e previous devem ser corrigidos em toda inserção e remoção, inclusive nas extremidades.

## Exercícios e verificação

1. Desenhe três nós antes e depois da inversão, indicando anterior, atual e próximo salvo a cada passo.
2. Por que remover nó conhecido é mais simples numa lista dupla do que numa lista simples sem predecessor?
3. Demonstre encontro dos ponteiros no ciclo com distância relativa módulo comprimento do ciclo.
4. Dois nós têm valor 7, mas identidades distintas: por que Floyd deve comparar `is` e não `==`?
5. Implemente inserção após nó conhecido; teste vazio, único nó e cauda preservando alcançabilidade.

**Leituras relacionadas:** [Arrays e strings](/pt/topics/arrays-and-strings/) descreve representação contígua; [pilhas e filas](/pt/topics/stacks-queues/) mostra interfaces implementáveis sobre listas e arrays.
