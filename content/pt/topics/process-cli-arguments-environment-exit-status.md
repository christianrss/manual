---
id: process-cli-arguments-environment-exit-status
title: "Como programas executam: argumentos, ambiente, streams e status de saída"
description: "Estude a execução de programas C11 com argumentos, ambiente, stdout, stderr e testes de processo."
category: operating-systems
difficulty: foundational
updated: 2026-10-12
prerequisites: [c-compilation-object-files-linking, c-pointers-arrays-object-lifetimes]
sources:
  - {title: "POSIX.1-2024 — exec functions", url: "https://pubs.opengroup.org/onlinepubs/9799919799/functions/exec.html", kind: "official POSIX standard"}
  - {title: "POSIX.1-2024 — Environment variables", url: "https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap08.html", kind: "official POSIX standard"}
  - {title: "POSIX.1-2024 — Process termination", url: "https://pubs.opengroup.org/onlinepubs/9799919799/functions/_exit.html", kind: "official POSIX standard"}
---
Executável armazenado em disco não é processo em execução. Iniciar um programa estabelece, além das instruções de máquina, um **vetor de argumentos, configuração de ambiente, streams de entrada e saída e status de término**. Esses contratos fundamentam ferramentas de shell, build, testes e ambientes de desenvolvimento. Distinguir o que um processo recebe no início daquilo que calcula depois é o primeiro passo para compreender a interface com o sistema operacional [1][2].

## Arquivo executável e processo são diferentes

Compilar e ligar produzem um artefato executável. Num host compatível, um mecanismo de inicialização organiza a imagem de execução e os recursos associados ao processo. Sob POSIX, uma chamada da família exec substitui a imagem do *processo que a invocou*; por si só não cria outro identificador de processo. Uma operação de criação, como fork ou API de spawn apropriada, é necessária para obter processo separado [1].

A função main de C constitui uma entrada no nível da linguagem. Pode haver inicialização pela runtime antes de main, portanto o ponto inicial de baixo nível não precisa ser a própria função main. Um arquivo executável válido ainda pode não iniciar por falta de permissões, dependências ou incompatibilidade da arquitetura de instruções.

## Argumentos chegam como texto

Os parâmetros argc e argv descrevem quantidade e vetor de strings de argumentos. Para um operando informado, argc normalmente vale 2: o nome de invocação argv[0] e o operando argv[1]. O nome de invocação não é necessariamente caminho absoluto confiável e não deve autorizar operações sensíveis [1].

O argumento 42 chega como caracteres, não como número inteiro já validado. Um parser correto verifica conversão numérica, entrada não vazia, consumo da string inteira e eventuais erros de intervalo. Aceitar o prefixo de 12lixo como número 12 violaria o contrato de inteiro estrito. O exemplo permite exatamente um inteiro decimal no intervalo fechado de 0 a 100.

Aspas, expansão de curingas e substituição de variáveis ocorrem no shell chamador. Um programa também pode ser iniciado diretamente por outros aplicativos, sem shell. Portanto, a API deve definir seu contrato de argumentos independentemente da aparência do texto digitado no terminal.

## Variáveis de ambiente são outra entrada

O ambiente fornece valores em strings associadas a nomes quando o programa começa [2]. A função getenv de C consulta variável nomeada ou devolve ponteiro nulo quando ausente. O exemplo reconhece MANUAL_EXAMPLE_MODE=verbose e ignora outros valores dessa variável.

Variáveis de ambiente ajudam na configuração, mas não constituem autenticação. Processo pai ou usuário frequentemente conseguem controlá-las. Modificar o ambiente de um processo não altera automaticamente o ambiente já entregue a outro processo em execução. Testes devem criar ambiente controlado para o filho, em vez de herdar configurações acidentais de quem está desenvolvendo.

Alguns valores de ambiente são sensíveis. Nosso programa compara um valor predefinido, sem imprimir indiscriminadamente as variáveis. Não interprete a existência de variável como prova de identidade, permissão ou armazenamento seguro de segredos.

## Stdout e stderr possuem responsabilidades distintas

Stdout transporta o resultado destinado ao consumo automático, enquanto stderr recebe convencionalmente orientações de uso e diagnósticos. São fluxos diferentes mesmo quando um terminal mostra ambos na mesma janela. Um processo pai pode capturar e conferir cada um separadamente.

Para argumento válido 42, o exemplo escreve next=43 em stdout. Argumentos ausentes produzem mensagem de uso em stderr, sem resultado normal. Número inválido produz outra mensagem de erro. Modo verbose adiciona diagnóstico em stderr sem modificar stdout. Essa separação permite que scripts consumam os dados sem precisar extrair diagnósticos da mesma saída.

O stdio possui buffering. Juntar streams num destino não preserva automaticamente uma ordem total que corresponda à sequência de instruções printf e fprintf no fonte. Quando a ordem exata importa, é necessário protocolo explícito ou sincronização, e não suposição de escrita imediata.

## Status de saída é parte do contrato

Um programa C hospedado que retorna zero de main indica sucesso. Valores não nulos indicam falha e seus significados são escolhas da aplicação. O exemplo usa código 2 para quantidade errada de argumentos, código 3 para número inválido e zero para sucesso. Um processo pai pode empregar essas informações para decidir se um comando terminou normalmente.

As interfaces POSIX diferenciam código de encerramento normal de término causado por sinal. Algumas funções wait disponibilizam somente oito bits inferiores do código normal; outras fornecem informações adicionais [3]. Bibliotecas de testes podem normalizar esses detalhes. Uma automação deve conferir status e saída esperados, não inferir sucesso apenas por stdout não vazio.

## Programa C11 executável e limitado

O código interpreta inteiro decimal com strtol, verifica que todo o token foi consumido, consulta errno em busca de erros de conversão e aplica intervalo [0,100]. Imprime o sucessor e opcionalmente uma mensagem verbose. Não constrói comando de shell com a entrada nem usa números não validados como índices ou comprimentos de memória.

~~~c
// file: cli.c
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "usage: cli NUMBER\n");
        return 2;
    }
    char *end = NULL;
    errno = 0;
    long number = strtol(argv[1], &end, 10);
    if (errno != 0 || end == argv[1] || *end != '\0'
            || number < 0 || number > 100) {
        fprintf(stderr, "invalid NUMBER\n");
        return 3;
    }
    const char *mode = getenv("MANUAL_EXAMPLE_MODE");
    if (mode != NULL && strcmp(mode, "verbose") == 0)
        fprintf(stderr, "mode=verbose\n");
    printf("next=%ld\n", number + 1);
    return 0;
}
~~~


O programa não lê stdin. Para processar entradas transmitidas por pipe, seria necessário contrato adicional sobre delimitação de registros, propagação de erros e conclusão do fluxo de entrada.

## Teste o comportamento de fora do processo

Um teste de caixa-preta deve compilar o C, iniciá-lo com vetor explícito de argumentos, capturar stdout e stderr separadamente e verificar o código de retorno. Com 42 sem verbose, espere somente next=43, stderr vazio e status zero. Com 101, espere invalid NUMBER em stderr e status 3, sem stdout.

Cubra também argumento vazio, argumentos adicionais, valores negativos, sufixos numéricos inválidos e inteiros grandes demais para strtol. Definir verbose no ambiente controlado deve produzir diagnóstico extra em stderr sem alterar o resultado nem o status de sucesso.

A tentativa de criar o processo pode falhar antes de seu início. Esse evento difere de um programa que efetivamente executou e devolveu código não nulo. Testes confiáveis distinguem as situações em vez de tratar ambas como erro genérico de comando.

## Portabilidade, limites e verificação

C define entrada por argumentos e streams; POSIX define determinadas convenções de execução e espera de processos. Outros sistemas podem usar APIs e representação de status diferentes. A aula não pressupõe que todo ambiente tenha fork, pipes de shell, executáveis ELF ou interpretação idêntica de Unicode para argumentos.

Validar status e streams demonstra o *contrato local de execução* para os casos testados. Não comprova ausência de todo defeito nem segurança de conteúdos arbitrários do ambiente.

## Exercícios e verificação

1. Diferencie arquivo executável, processo em execução e função main.
2. Preveja saídas e códigos para 42, -1, 101, texto vazio e dois operandos.
3. Explique por que ignorar o ponteiro final na conversão permite entradas numéricas inválidas.
4. Demonstre que verbose não modifica o resultado em stdout.
5. Explique por que retorno não nulo e encerramento por sinal nem sempre representam o mesmo evento.
6. Distinga substituir imagem com exec de criar um processo separado [1].

Continue com [compilador e linker C](/pt/topics/c-compilation-object-files-linking/), [descritores de arquivos](/pt/topics/file-descriptors-buffering-fsync/) e [memória de processos](/pt/topics/processes-virtual-memory/).