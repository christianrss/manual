---
id: c-pointers-arrays-object-lifetimes
title: "Fundamentos de C: ponteiros, arrays, limites e duração de objetos"
description: "Aprenda ponteiros em C, conversão de arrays, aritmética válida, propriedade e duração com um programa C11 verificável."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [data-types-bytes-and-representation, program-memory-references-lifetimes]
sources:
  - {title: "C language — pointer declaration", url: "https://en.cppreference.com/w/c/language/pointer", kind: "C language reference"}
  - {title: "C language — pointer arithmetic", url: "https://en.cppreference.com/w/c/language/operator_arithmetic", kind: "C language reference"}
  - {title: "C language — object lifetime", url: "https://en.cppreference.com/w/c/language/lifetime", kind: "C language reference"}
  - {title: "C language — storage duration", url: "https://en.cppreference.com/w/c/language/storage_duration", kind: "C language reference"}
---
As referências de objetos em Python ajudam a compreender aliasing, mas quem desenvolve sistemas também precisa entender como C expõe **endereços, arrays, indireção e duração dos objetos**. Esses conceitos explicam o acesso eficiente a dados e categorias inteiras de falhas de segurança de memória. A finalidade não é decorar truques perigosos: é definir operações válidas antes de considerar alocação manual ou otimizações [1][2].

## Objetos, endereços e tipos de ponteiro

Um objeto ocupa armazenamento durante uma duração definida. O operador de endereço obtém um ponteiro para um objeto apropriado, enquanto o operador de indireção permite acessar objeto por meio de ponteiro válido. Numa declaração de ponteiro para inteiro p inicializado com endereço do inteiro local x, p é do tipo ponteiro e *p designa x. Atribuir a *p modifica x, e não o próprio ponteiro p [1].

Ponteiro não é número inteiro sem tipo que armazena um endereço. O tipo apontado influencia desreferência e aritmética válidas. Em C, ponteiro nulo não identifica objeto e não deve ser desreferenciado. Um ponteiro que identificava objeto cuja duração acabou não volta a ser válido apenas porque a memória parece conservar seus bytes. Acessar esse objeto tem comportamento indefinido [3].

A distinção entre ponteiro e objeto apontado se aproxima, mas é mais explícita, da distinção entre nome e objeto em Python. C admite operações diretas com armazenamento; nomes em Python não disponibilizam aritmética portátil de ponteiros equivalente.

## Arrays não são ponteiros

Declarar um array de quatro inteiros cria agregado contíguo de quatro objetos inteiros. Na maioria dos contextos de expressão, o array é convertido em ponteiro para seu primeiro elemento. Por isso passar um array a uma função cujo parâmetro é ponteiro de inteiro funciona. Entretanto, um array **não é uma variável ponteiro**: tipo e armazenamento são diferentes [1].

Para array local, sizeof aplicado ao array completo devolve a extensão total em bytes; aplicado a ponteiro, devolve o tamanho do objeto ponteiro. Dividir sizeof array por sizeof array[0] fornece quantidade de elementos somente onde o compilador ainda reconhece o array, não depois da conversão dentro de um parâmetro de função. Uma função que recebe ponteiro precisa receber também quantidade ou outro limite confiável.

Arrays bidimensionais exigem cuidado adicional: array de linhas não é automaticamente conversível em int**. Seu primeiro elemento também é array, e aritmética de ponteiro para linhas avança em blocos de linha inteira. Confundir tipos pode produzir indexação inválida mesmo quando a memória aparenta continuidade.

## Aritmética de ponteiros e a posição após o fim

Num array de N elementos, ponteiro para elemento i pode avançar dentro do intervalo do array ou até a posição **uma após o último elemento**. Esse ponteiro após o fim pode ser formado, comparado ou subtraído em relação a ponteiros do mesmo array nas condições permitidas, mas não pode ser desreferenciado. Formar ponteiro antes do início ou além da posição posterior ao fim não constitui apenas um ponteiro perigoso para acesso: a própria aritmética já pode ter comportamento indefinido [2].

Somar um a ponteiro de int avança pelo tamanho de um elemento int, não apenas um byte. Subtrair ponteiros pertencentes ao mesmo array fornece distância em elementos, com tipo ptrdiff_t, não quantidade bruta de bytes. Aritmética entre objetos alocados independentemente não é maneira geral de comparar posições de memória.

O exemplo forma ponteiro após o fim de array de quatro elementos, calcula distância até o primeiro ponteiro e desreferencia somente posições internas válidas. Nunca lê a posição após o último elemento.

## Uma função com contrato de limites explícitos

Considere função que soma sequência de inteiros não negativos, com cada valor no máximo 1000 e quantidade máxima de 1000 elementos. Sua entrada é ponteiro e tamanho; sua saída é ponteiro para variável do chamador. Se o ponteiro de resultado for nulo, retorne falso. Se quantidade não for zero, mas entrada for nula, retorne falso. Sequência vazia admite ponteiro de entrada nulo e soma igual a zero.

Esse contrato limita a soma matemática a um milhão, valor que cabe no intervalo mínimo garantido para long long em C. A função verifica os elementos antes de alterar o resultado disponibilizado pelo chamador; ao rejeitar valor inválido, mantém a saída anterior. É responsabilidade de quem chama garantir que o ponteiro não nulo de entrada referencie pelo menos a quantidade especificada de inteiros válidos, e que a saída não nula referencie armazenamento gravável de long long. Não é possível recuperar a capacidade real inspecionando um ponteiro bruto.

O parâmetro de saída exemplifica indireção explícita: a função grava no objeto do chamador por endereço válido, em vez de tentar alterar a associação de um nome em outra função. O ponteiro de entrada com const restringe a função a não modificar valores por meio daquela referência.

~~~c
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

static bool sum_bounded(const int *values, size_t count, long long *out) {
    if (out == NULL || count > 1000 || (count != 0 && values == NULL))
        return false;
    long long sum = 0;
    for (size_t i = 0; i < count; ++i) {
        if (values[i] < 0 || values[i] > 1000)
            return false;
        sum += (long long)values[i];
    }
    *out = sum;
    return true;
}

int main(void) {
    int values[4] = {3, 5, 7, 9};
    int *first = &values[0];
    int *one_past = values + 4;
    assert(*(first + 2) == 7);
    assert(one_past - first == 4);
    assert(sizeof values / sizeof values[0] == 4);

    long long total = -1;
    assert(sum_bounded(values, 4, &total) && total == 24);
    assert(!sum_bounded(NULL, 1, &total) && total == 24);
    assert(!sum_bounded(NULL, 0, NULL) && total == 24);
    assert(sum_bounded(NULL, 0, &total) && total == 0);

    int *allocated = malloc(4 * sizeof *allocated);
    if (allocated == NULL)
        return 1;
    for (size_t i = 0; i < 4; ++i)
        allocated[i] = values[i];
    assert(sum_bounded(allocated, 4, &total) && total == 24);
    free(allocated);
    allocated = NULL;
    printf("sum=%lld\n", total);
    return 0;
}
~~~

## Armazenamento automático, estático e alocado

C distingue armazenamento automático, estático, por thread e alocado [4]. Um array local não estático normalmente possui duração automática e deixa de existir ao término do escopo determinado. Devolver ponteiro para array local e desreferenciá-lo depois, no chamador, é inválido porque esse objeto já não existe. Ponteiro não prolonga a duração do objeto.

Malloc solicita armazenamento alocado; é necessário verificar resultado nulo antes de desreferenciar. Quando a alocação do exemplo funciona, o buffer possui espaço para quatro inteiros, já que seu tamanho em bytes é quatro vezes sizeof um inteiro. Após o uso, o programa chama free exatamente uma vez e não acessa essa região pelo ponteiro novamente. Atribuir null ao ponteiro após free é útil para aquela variável, mas não corrige outras referências que tenham preservado o endereço inválido.

Esse é gerenciamento manual de duração: o código precisa declarar quem libera a memória e como erros liberam recursos. Objetos de duração estática não exigem malloc/free, porém possuem outro ciclo de vida e talvez estado mutável compartilhado.

## Prova do comportamento e complexidade

Se a quantidade é no máximo 1000, todo elemento da entrada está em [0,1000] e a saída aponta para armazenamento long long gravável, a soma contém no máximo um milhão. O invariante do laço diz que, na iteração i, o acumulador equivale à soma dos primeiros i elementos validados. Cada iteração verifica o elemento corrente e atualiza o total. Ao terminar, o total corresponde à sequência válida inteira. Se a validação falha, a função retorna antes de escrever na saída.

O laço visita n elementos uma vez: O(n) tempo para n igual à quantidade e O(1) espaço escalar auxiliar, supondo aritmética inteira de custo limitado. O array de entrada ocupa O(n), mas é propriedade do chamador e não é alocado por sum_bounded. Long long evita overflow **sob os limites numéricos declarados**, não torna qualquer soma possível automaticamente segura em C.

No programa de exemplo, asserts conferem o comportamento. Validação de entradas em produção não deve existir apenas dentro de expressões assert: quando assertions são desabilitadas, essas expressões podem não executar. Um harness de teste real precisa chamar a função independentemente da configuração NDEBUG e verificar suas saídas.

## Comportamento indefinido, sanitizers e contraexemplos

C pode compilar programa que desreferencia ponteiro após o fim, lê memória liberada ou fornece comprimento errado; compilar com sucesso não comprova a validade dessas operações. Programas inválidos podem aparentar funcionar numa máquina, então testes isolados não bastam. Derive limites e duração a partir do contrato antes de aplicar aritmética de ponteiros [2][3].

Avisos do compilador, sanitizers e testes identificam vários defeitos, mas não comprovam ausência de todo comportamento indefinido. Ponteiros brutos não oferecem propriedade automática, e const numa referência específica não torna imutáveis todos os aliases. Prefira APIs com tamanho, propriedade e regras de erro explícitos. Utilize abstrações existentes quando manipulação direta for dispensável.

## Exercícios e verificação

1. Diferencie tipo e tamanho de array de quatro inteiros e de ponteiro para o primeiro elemento.
2. Forme ponteiro válido após o último elemento e explique por que desreferenciá-lo é indefinido.
3. Estenda o contrato da soma para rejeitar elemento superior a 1000, preservando resultado anterior em caso de erro.
4. Escreva função que devolveria ponteiro para array local automático e identifique o erro conceitual sem executar comportamento indefinido.
5. Teste quantidade zero com entrada nula e saída válida; compare com a saída nula.
6. Compile o programa C11 com avisos e sanitizers disponíveis na plataforma e explique limites de evidência dos testes.

Continue por [memória e aliasing](/pt/topics/program-memory-references-lifetimes/), [representação de dados](/pt/topics/data-types-bytes-and-representation/) e [alocação em heap](/pt/topics/heap-allocation-fragmentation/).