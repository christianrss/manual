---
id: resizable-arrays-capacity-amortized-cost
title: "Arrays dinâmicos: capacidade, redução e análise amortizada"
description: "Implemente array redimensionável com append, pop e redução de capacidade; demonstre custos amortizados."
category: algorithms
difficulty: foundational
updated: 2026-10-12
prerequisites: [arrays-and-strings, complexity-analysis, abstract-data-types-representation-invariants]
sources:
  - {title: "Open Data Structures — Array-Based Lists", url: "https://opendatastructures.org/ods-python/2_Array_Based_Lists.html", kind: "open computer science textbook"}
  - {title: "MIT 6.006 — Introduction to Algorithms", url: "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", kind: "university course"}
  - {title: "Python Tutorial — Data Structures", url: "https://docs.python.org/3/tutorial/datastructures.html", kind: "official programming documentation"}
---
Um array fixo reserva uma quantidade conhecida de posições. Um array dinâmico distingue **comprimento lógico n** de **capacidade alocada C**, possibilitando crescimento sem criar novo buffer a cada inserção. A introdução aos arrays já apresenta crescimento geométrico; aqui implementamos expansão e contração, demonstramos correção e analisamos sequências **mistas de inserção e remoção**, não apenas inserções consecutivas [1][2].

## Invariantes da representação

O buffer privado contém C posições, com 0 <= n <= C e C >= 1. Apenas posições de 0 até n-1 pertencem à sequência lógica. As posições não utilizadas permanecem privadas e são limpas após remoções, evitando retenção desnecessária de referências antigas.

Um elemento válido pode ser None. Portanto, uma posição contendo None não revela se há elemento: o campo n determina quais posições são válidas. A estrutura armazena referências para objetos, não cópias profundas. A lista nativa Python também usa array extensível de referências, mas sua política exata de capacidade depende da implementação [3].

Acesso indexado tem custo Θ(1) no modelo RAM convencional. Separar C de n explica por que a memória alocada pode exceder a quantidade de elementos vivos e por que um snapshot precisa copiar n referências, custando Θ(n).

## Expandir dobrando a capacidade

Quando n=C, append primeiro aloca 2C posições e copia as n referências, depois grava o valor novo. Caso haja espaço, apenas grava na próxima posição. Logo, uma inserção que provoca expansão custa Θ(n) no pior caso, embora a maioria das inserções execute trabalho constante.

Se a capacidade aumentasse apenas uma posição a cada vez, n inserções poderiam copiar 1+2+...+(n-1)=Θ(n²) referências. Dobrando a capacidade, copiam-se blocos de tamanhos 1,2,4,8 e assim por diante, com menos de 2n cópias no total de n inserções. Somadas as n gravações, o trabalho é O(n): **append O(1) amortizado**, não O(1) no pior caso de uma operação individual [1][2].

Essa garantia corresponde à política descrita, não a todo contêiner que utiliza a palavra array.

## Contrair sem oscilar a cada operação

Contrair assim que o array fica com metade da capacidade pode provocar realocações repetidas em sequências adversariais, oscilando perto do limiar. Nossa implementação só contrai quando o novo tamanho satisfaz 4n <= C e C > 1, reduzindo a capacidade para max(1,C/2). Após a contração, a ocupação fica aproximadamente na metade; é preciso executar várias operações antes de outra realocação semelhante.

A separação entre expansão com buffer cheio e contração ao atingir um quarto é chamada **histerese**. Uma remoção precisa guardar o elemento retirado, limpar sua posição, atualizar n e somente então verificar a redução. Retirar de uma estrutura vazia lança IndexError sem alterar qualquer estado.

## Implementação verificável

~~~python
class ResizingArray:
    def __init__(self):
        self._slots = [None]
        self._size = 0
        self.moves = 0

    @property
    def capacity(self):
        return len(self._slots)

    def __len__(self):
        return self._size

    def _resize(self, capacity):
        if capacity < max(1, self._size):
            raise ValueError("capacity would lose elements")
        new_slots = [None] * capacity
        for i in range(self._size):
            new_slots[i] = self._slots[i]
            self.moves += 1
        self._slots = new_slots

    def append(self, value):
        if self._size == self.capacity:
            self._resize(2 * self.capacity)
        self._slots[self._size] = value
        self._size += 1

    def pop(self):
        if self._size == 0:
            raise IndexError("empty array")
        self._size -= 1
        value = self._slots[self._size]
        self._slots[self._size] = None
        if self.capacity > 1 and 4 * self._size <= self.capacity:
            self._resize(max(1, self.capacity // 2))
        return value

    def get(self, index):
        if type(index) is not int or not 0 <= index < self._size:
            raise IndexError("index out of range")
        return self._slots[index]

    def snapshot(self):
        return tuple(self._slots[:self._size])

a = ResizingArray()
for item in (None, 4, 8, 12, 16):
    a.append(item)
assert a.snapshot() == (None, 4, 8, 12, 16)
assert a.capacity == 8 and a.get(0) is None
for item in (16, 12, 8, 4, None):
    assert a.pop() == item
assert len(a) == 0 and a.capacity == 1
~~~

O campo moves conta referências copiadas durante realocações; não mede tempo de execução. Um snapshot cria tupla com as mesmas referências para objetos, não cópia profunda. Essa classe não estabelece sincronização entre threads.

## Demonstração indutiva de correção

Na construção, n=0 e C=1 satisfazem as restrições. Em append, se existe espaço livre, o elemento é gravado e n aumenta em um. Se o array está cheio, dobrar a capacidade conserva os n elementos existentes na mesma ordem e cria espaço suficiente para a inserção.

Em pop, a precondição exige n>0. O elemento final antigo é devolvido e sua posição é limpa; o prefixo restante conserva todos os elementos anteriores, exceto aquele removido. Uma eventual contração copia exatamente o prefixo. Como 4n <= C implica n <= C/4 <= C/2, a capacidade reduzida nunca fica menor que n. A capacidade mínima de um preserva o estado vazio.

Portanto, após toda operação bem-sucedida, a sequência corresponde ao histórico de inserções e remoções, 0 <= n <= C continua verdadeiro e None pode ser armazenado como qualquer valor.

## Demonstração de O(1) amortizado

Defina o potencial não negativo Phi(n,C) como **2n-C se n >= C/2**, e **C/2-n nos demais casos**. Cobre uma unidade pela operação básica append ou pop, mais uma unidade por referência copiada no redimensionamento. O custo amortizado é custo real mais a variação do potencial.

Para expansão em n=C, copiar C referências e inserir custa C+1. O potencial cai de C para 2 depois de dobrar a capacidade, resultando em custo amortizado (C+1)+(2-C)=3. Na contração depois de uma remoção atingir n=C/4, copiar n referências é pago pela queda de aproximadamente C/4 unidades acumuladas de potencial para zero. Sem realocação, alterar n em um modifica o potencial apenas por constante.

Somar os custos amortizados faz as variações de potencial cancelarem entre operações. Como Phi nunca se torna negativo e começa em constante, **qualquer sequência de m operações append/pop iniciada no vazio realiza O(m) movimentações e gravações**. Não existe hipótese probabilística. Alterar os limiares ou fatores exigiria outra demonstração [2].

## Custos e escolha da estrutura

Leitura indexada válida custa Θ(1). Operações individuais com redimensionamento custam Θ(n) no pior caso; append e pop no final são O(1) amortizado. Inserir ou remover elemento perto do início exige Θ(n) deslocamentos no pior caso, mesmo sem redimensionar. Snapshot custa Θ(n) tempo e memória de referências. A capacidade após cada operação é O(max(1,n)) sob essa política; os objetos apontados podem ocupar memória adicional arbitrária.

Essa estrutura atende bem a cenários dominados por indexação e alterações no final. Listas encadeadas e deques especializadas podem ser preferíveis para outros padrões de acesso. Medições isoladas não substituem o modelo de custos, especialmente quando comportamento de alocadores e coleta de lixo varia.

## Exercícios e testes independentes

Compare o array com uma lista Python comum em sequências adversariais e geradas de operações. Inclua None, valores repetidos, tamanhos próximos a potências de dois, remoção completa e erro ao retirar de vazio. Verifique que o contador de referências copiadas cresce linearmente em longas sequências mistas.

1. Calcule a capacidade após nove inserções append.
2. Explique como limpar uma posição altera a duração das referências sem modificar a sequência lógica.
3. Dê contraexemplo à afirmação de que cada append tem Θ(1) no pior caso.
4. Mostre por que reduzir em um quarto evita oscilar entre expansão e contração no mesmo tamanho.
5. Calcule Phi para (n,C)=(8,8), (9,16), (2,8) e (2,4).
6. Compare remoção no final com remoção em posição arbitrária.

Aprofunde em [arrays](/pt/topics/arrays-and-strings/), [contratos de TAD](/pt/topics/abstract-data-types-representation-invariants/) e [análise de complexidade](/pt/topics/complexity-analysis/).
