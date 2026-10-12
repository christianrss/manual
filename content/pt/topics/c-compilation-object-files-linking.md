---
id: c-compilation-object-files-linking
title: "Do código C ao executável: pré-processamento, objetos e ligação"
description: "Compile C11 com vários arquivos e compreenda unidades de tradução, símbolos, falhas de ligação e carregamento."
category: foundations
difficulty: foundational
updated: 2026-10-12
prerequisites: [c-pointers-arrays-object-lifetimes, modular-programming-interfaces]
sources:
  - {title: "GCC — Options Controlling the Kind of Output", url: "https://gcc.gnu.org/onlinedocs/gcc/Overall-Options.html", kind: "official compiler documentation"}
  - {title: "GCC — Link Options", url: "https://gcc.gnu.org/onlinedocs/gcc/Link-Options.html", kind: "official compiler documentation"}
  - {title: "GNU ld — Linker documentation", url: "https://sourceware.org/binutils/docs/ld/", kind: "official linker documentation"}
---
Um arquivo-fonte C pode compilar corretamente e, ainda assim, falhar na construção do executável quando a implementação de outra unidade está ausente. Para explicar o problema, precisamos distinguir **código-fonte, declarações, unidades de tradução, arquivos-objeto, resolução de símbolos, ligação e execução**. Essas etapas recebem entradas distintas e produzem classes diferentes de erros. O compilador não fornece automaticamente o corpo de toda função cuja declaração conhece. O GCC documenta a execução separada dessas fases [1][2].

## Arquivos e unidades de tradução

Uma unidade de tradução é o código entregue ao compilador C depois do pré-processamento. O arquivo-fonte e o conteúdo de seus cabeçalhos formam normalmente uma unidade. Outro arquivo-fonte é compilado como unidade diferente. As unidades podem compartilhar declarações compatíveis e contribuir com definições para o mesmo programa.

Declaração informa nome e tipo de função. Definição fornece seu corpo. Uma unidade que chama uma função pode ser compilada usando declaração correta mesmo que a implementação ainda não esteja compilada, pois o arquivo-objeto preserva referência externa para o linker. É a base de programas modulares, mas exige contrato explícito entre produtor e consumidor.

Cabeçalho é texto-fonte, não biblioteca binária já compilada. Colocar definição externa de função comum num cabeçalho incluído por vários arquivos pode produzir definições conflitantes. O exemplo mantém declaração em cabeçalho protegido por guarda e corpo da função em exatamente um arquivo de implementação.

## Pré-processamento e tradução

O pré-processador trata diretivas de inclusão e compilação condicional antes da compilação convencional. A inclusão de cabeçalho entre aspas incorpora seus tokens à unidade de tradução; guardas evitam inclusões repetidas na mesma unidade. Uma guarda não opera em tempo de execução e não impede que outros arquivos incluam o mesmo cabeçalho.

Macros são substituições de tokens e podem repetir a avaliação de expressões usadas como argumentos. Não equivalem necessariamente a funções com tipos. Prefira função real quando for importante verificar tipos e avaliar cada argumento somente uma vez.

Num compilador compatível com GCC, a flag -E termina após o pré-processamento, portanto a saída ainda é texto C. A flag -S interrompe após a compilação propriamente dita, produzindo normalmente Assembly específico da arquitetura. A opção -c compila e monta conforme necessário, mas não executa a ligação final. A saída Assembly depende de compilador, otimização e arquitetura [1].

## Arquivos-objeto e símbolos

Um arquivo-objeto costuma conter instruções, dados, símbolos e registros de relocação. Uma chamada pode referenciar símbolo definido em outro objeto. O arquivo não precisa conter o ponto completo de entrada nem os endereços finais de todas as funções usadas. O linker resolve referências compatíveis e organiza seções no programa produzido [2][3].

O nome externo double_small aparece como declaração na unidade chamadora. Seu corpo aparece na unidade de implementação. Nenhum dos dois objetos isoladamente constitui o programa completo. Durante a ligação, a referência não resolvida do chamador é associada à definição da implementação.

A ABI estabelece detalhes binários, como convenção de chamada, uso de registradores, layout de dados e regras de símbolos. Combinar arquivos compilados para alvos incompatíveis não se torna correto porque seus nomes terminam com a mesma extensão. Tampouco se deve supor que Windows, Unix e sistemas embarcados compartilhem o mesmo formato executável.

## Exemplo: interface, implementação e consumidor

O contrato aceita inteiro entre -10000 e 10000 e ponteiro de saída para inteiro gravável. Em caso de sucesso, grava o dobro da entrada e devolve 1. Argumento fora do intervalo ou ponteiro nulo produz falha 0 sem alterar a saída anterior do chamador. A magnitude do resultado é no máximo 20000, valor que cabe no intervalo mínimo garantido de int em C.

~~~c
// file: math_ops.h
#ifndef MATH_OPS_H
#define MATH_OPS_H

/* On success, store twice the value and return 1.
   Reject inputs outside [-10000, 10000] or null output. */
int double_small(int value, int *out);

#endif
~~~

~~~c
// file: math_ops.c
#include "math_ops.h"
#include <stddef.h>

int double_small(int value, int *out) {
    if (out == NULL || value < -10000 || value > 10000)
        return 0;
    *out = value * 2;
    return 1;
}
~~~

~~~c
// file: main.c
#include "math_ops.h"
#include <stdio.h>

int main(void) {
    int result = -1;
    if (!double_small(21, &result))
        return 1;
    printf("result=%d\n", result);
    return 0;
}
~~~

Compile e ligue num shell semelhante ao POSIX com toolchain C11 compatível com GCC:

~~~sh
cc -std=c11 -Wall -Wextra -Werror -pedantic -c math_ops.c -o math_ops.o
cc -std=c11 -Wall -Wextra -Werror -pedantic -c main.c -o main.o
cc main.o math_ops.o -o demo
./demo
# result=42
~~~

O contrato de ponteiro é importante: ponteiro inválido não nulo continua perigoso, mesmo após verificação contra null. O sucesso da função pressupõe armazenamento válido fornecido por quem a chamou.

## Por que definições ausentes falham na ligação

Se math_ops.o for omitido, a compilação de main.c ainda funciona porque a declaração existe. Tentar ligar somente o objeto chamador deve falhar, pois não há definição da função. O diagnóstico depende do linker. Da mesma forma, definições externas incompatíveis e duplicadas podem gerar erros de símbolos repetidos.

Ligar objetos não é concatenar arquivos. A resolução de símbolos, relocações, organização de seções e bibliotecas alteram a saída final. Biblioteca estática costuma arquivar objetos; biblioteca compartilhada pode usar mecanismo que inclui linker dinâmico em execução. As regras exatas dependem da plataforma [2][3].

Declaração válida não demonstra que uma implementação respeita a semântica desejada. O compilador pode verificar tipos sem provar limites numéricos nem correção da aplicação. Por isso testes comportamentais continuam necessários mesmo depois de uma ligação bem-sucedida.

## Ligação, carregamento e início do processo

A ligação produz artefato executável, mas não inicia processo. O sistema operacional ainda precisa reconhecer o formato e preparar recursos de execução. Sistemas hospedados normalmente possuem código de inicialização de runtime que finalmente chama a função main de C. O ponto inicial de baixo nível não precisa literalmente ser main.

Arquitetura de CPU incompatível, biblioteca dinâmica ausente, falta de permissão ou runtime incompatível podem impedir a execução de binário válido. São problemas posteriores à compilação. O capítulo seguinte descreve a interface do processo para argumentos, ambiente, streams e código de saída.

## Recompilação, verificação e custos

O teste independente deve compilar cada unidade, ligar os dois objetos e verificar a impressão de result=42 e término bem-sucedido. Também deve omitir deliberadamente o objeto de implementação e exigir falha na ligação. Esses dois resultados diferenciam compilação correta de resolução correta de símbolos.

Ao modificar a implementação sem alterar cabeçalho, pode bastar recompilar a unidade afetada e refazer a ligação. Modificar cabeçalho incluído por vários arquivos pode exigir recompilar todos os dependentes. Sistemas de build automatizam essas dependências, sem alterar o conceito de unidade de tradução.

Não existe limite universal O(S) para toda compilação otimizada em função apenas do tamanho S: expansão de macros, parsing, transformações e estratégias de otimização influenciam o trabalho. A primeira análise útil é quantas unidades precisam ser recompiladas e ligadas após cada alteração.

## Exercícios e verificação

1. Identifique a fase que processa inclusão e a que resolve o símbolo double_small.
2. Compare as saídas de pré-processamento (-E), Assembly (-S) e objeto (-c) para um mesmo arquivo [1].
3. Tente ligar somente o objeto chamador e explique o erro de símbolo ausente.
4. Altere a implementação para divergir do próprio cabeçalho e observe o erro de compilação.
5. Acrescente segunda definição externa e explique por que a ligação fica inválida.
6. Diferencie ligação bem-sucedida e execução em outra máquina.

Continue com [ponteiros em C](/pt/topics/c-pointers-arrays-object-lifetimes/), [programação modular](/pt/topics/modular-programming-interfaces/) e [interfaces de processo](/pt/topics/process-cli-arguments-environment-exit-status/).