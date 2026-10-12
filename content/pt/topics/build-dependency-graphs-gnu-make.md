---
id: build-dependency-graphs-gnu-make
title: "Fundamentos de build: grafos de dependência, compilação incremental e GNU Make"
description: "Derive o grafo de build e teste regras C11 com dependências de cabeçalhos, alvos phony e propagação de falhas."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [git-version-control-commits-branches, c-compilation-object-files-linking]
sources:
  - {title: "GNU make — What a Rule Looks Like", url: "https://www.gnu.org/software/make/manual/html_node/Rule-Introduction.html", kind: "official build tool manual"}
  - {title: "GNU make — Rules and prerequisites", url: "https://www.gnu.org/software/make/manual/html_node/Rules.html", kind: "official build tool manual"}
  - {title: "GNU make — Automatic Variables", url: "https://www.gnu.org/software/make/manual/html_node/Automatic-Variables.html", kind: "official build tool manual"}
  - {title: "GNU make — Phony Targets", url: "https://www.gnu.org/software/make/manual/html_node/Phony-Targets.html", kind: "official build tool manual"}
---
Compilar manualmente um programa C com dois arquivos é simples até que um cabeçalho seja alterado e alguém precise decidir quais arquivos-objeto reconstruir. Um **sistema de build** registra essa decisão por dependências entre fontes, resultados intermediários e executável final. Sua responsabilidade principal não é esconder comandos do compilador, mas tornar builds repetidos corretos e incrementais sob hipóteses explícitas. GNU Make descreve o processo com alvos, pré-requisitos e receitas [1][2].

## Comece pelo grafo de dependências

Cada arquivo gerado representa um nó no grafo dirigido. No exemplo, o executável demo depende de main.o e math_ops.o. O objeto main.o depende de main.c e math_ops.h; math_ops.o depende de math_ops.c e math_ops.h. Uma seta do alvo para o pré-requisito indica que esse alvo pode precisar ser reconstruído quando o pré-requisito mudar.

Uma dependência é uma **afirmação semântica**: o resultado produzido depende daquele arquivo. Listar argumentos do compilador não basta se um cabeçalho incluído não estiver entre os pré-requisitos. Quando math_ops.h muda, ambos os objetos devem ser recompilados. Assim, o grafo de build complementa, sem substituir, o modelo de unidades de tradução de C.

Quando as arestas não formam ciclos, o build pode compilar objetos independentes em paralelo e realizar a ligação somente depois que ambos estiverem prontos. Uma ordenação topológica respeita essas restrições. Ciclos entre resultados gerados podem impedir o agendamento correto, salvo mecanismos explicitamente suportados.

## Alvos, pré-requisitos e receitas

Uma regra Make possui alvo à esquerda, pré-requisitos após os dois-pontos e receita que descreve como produzir esse alvo. Para alvos que representam arquivos, o Make normalmente compara datas de modificação: alvo inexistente ou pré-requisito mais novo indica necessidade de reconstrução [1][2].

As linhas de receita do exemplo começam com um caractere TAB verdadeiro. Espaços comuns não equivalem ao prefixo de receita num Makefile convencional. Make chama um shell para executar comandos, e retorno de falha normalmente interrompe a construção do alvo e suas dependências em vez de tratar resultado inválido como válido.

Uma regra expressa *quando* e *como* construir. Se apenas o texto da receita for modificado, sem alteração dos timestamps dos arquivos de entrada, o modelo simples pode não detectar necessidade de reconstrução. O limite importa quando são alteradas flags do compilador, ferramentas selecionadas ou comportamentos influenciados pelo ambiente.

## Construa duas unidades de tradução

O programa utiliza cabeçalho compartilhado e função com limites definidos. Uma entrada válida entre -100 e 100 é multiplicada por dois e armazenada no endereço de saída. O ponteiro de saída deve designar inteiro gravável; NULL ou valor fora do intervalo provoca falha sem modificar o resultado anterior. Multiplicar por dois não causa overflow de int sob esse contrato.

~~~c
// file: math_ops.h
#ifndef MATH_OPS_H
#define MATH_OPS_H
int twice_bounded(int value, int *result);
#endif
~~~

~~~c
// file: math_ops.c
#include "math_ops.h"
#include <stddef.h>
int twice_bounded(int value, int *result) {
    if (!result || value < -100 || value > 100)
        return 0;
    *result = value * 2;
    return 1;
}
~~~

~~~c
// file: main.c
#include "math_ops.h"
#include <stdio.h>
int main(void) {
    int result = 0;
    if (!twice_bounded(21, &result))
        return 1;
    printf("answer=%d\n", result);
    return 0;
}
~~~

~~~make
# file: Makefile
CC = cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic
.PHONY: all check clean

all: demo

demo: main.o math_ops.o
	$(CC) $(CFLAGS) $^ -o $@

main.o: main.c math_ops.h
	$(CC) $(CFLAGS) -c $< -o $@

math_ops.o: math_ops.c math_ops.h
	$(CC) $(CFLAGS) -c $< -o $@

check: demo
	./demo

clean:
	rm -f demo main.o math_ops.o
~~~

No diretório contendo os quatro arquivos, executar make constrói os dois objetos e o executável. Executar make check atualiza dependências necessárias e depois roda o programa; stdout esperado é answer=42. Executar make clean remove os resultados gerados sem modificar os fontes.

As regras de compilação mencionam o cabeçalho porque os dois arquivos-fonte o incluem. Omitir essa dependência produz um **defeito reproduzível de build desatualizado**: modificar o cabeçalho pode não provocar recompilação, permitindo objetos inconsistentes até acontecer um build limpo.

## Variáveis automáticas e reutilização

A variável automática $@ representa o arquivo-alvo; $< representa o primeiro pré-requisito; $^ lista os pré-requisitos normais sem duplicatas [3]. Na regra main.o, o comando expandido compila main.c para main.o. Na regra demo, $^ expande para main.o math_ops.o, usados no comando de ligação.

Esses símbolos possuem significado no contexto de receita Make e não devem ser confundidos com variáveis de shell de mesma sintaxe. O Make realiza sua expansão antes de enviar o comando ao shell. Misturar expansão Make e shell é origem comum de comandos incorretos.

O exemplo pequeno repete CFLAGS intencionalmente para garantir que os dois arquivos sejam compilados com as mesmas opções. Projetos reais podem separar flags de compilação e ligação, mas isso não deve esconder o grafo elementar.

## Tarefas phony e arquivos gerados

Um alvo comum como demo representa arquivo. Já check representa uma ação que deve executar quando solicitada, mesmo que exista arquivo real chamado check. Declarar check, clean e all como .PHONY torna essa intenção explícita [4].

A dependência check: demo garante que o executável exista antes do teste. Não comprova sozinha que a saída do programa está correta: a receita ./demo verifica status de saída, enquanto conferir stdout exato exige asserção adicional ou teste externo.

O alvo clean não deve ser pré-requisito do build padrão; isso destruiria a vantagem de reconstrução incremental. Da mesma forma, rodar testes depois de toda edição pode ser uma política desejável, mas é distinta do grafo necessário para produzir os objetos.

## Derive os resultados da recompilação incremental

Na primeira construção, nenhum alvo gerado existe; logo as duas receitas de compilação e a de ligação executam. Sem novas edições, um segundo make demo deve perceber que os arquivos estão atualizados e não repetir esses comandos. Se apenas main.c ficar mais novo, main.o e demo precisam ser reconstruídos, mas math_ops.o não. Se o cabeçalho compartilhado math_ops.h ficar mais novo, ambos os objetos e demo precisam de reconstrução.

A conclusão decorre do grafo e do modelo de timestamps, não de palpites. Um bom teste utiliza diretório temporário isolado, registra o build inicial, verifica que dry run subsequente não compila e depois modifica a data do cabeçalho para inspecionar o plano de compilação dos dois objetos. Por último, executa o programa reconstruído e confirma o resultado esperado.

Datas de modificação não representam perfeitamente todas as alterações de dependência. Resolução do filesystem, divergência entre relógios e timestamps preservados propositalmente podem confundir a comparação simples. Caches por hash de conteúdo utilizam outras regras; a aula trata especificamente do modelo temporal do GNU Make [2].

## Complexidade e limites das falhas

Se V representa quantidade de nós e E representa dependências, percorrer um grafo de build bem formado pode ser analisado em função de V+E, mas o tempo real também inclui pré-processamento, compilação, ligação e I/O. Seria incorreto afirmar que um build inteiro custa O(V+E) sem considerar quantidade de código e custo das ferramentas.

Execução paralela pode reduzir tempo de parede quando tarefas são independentes, mas precisa respeitar ordem de pré-requisitos. Receitas teoricamente independentes não devem compartilhar acidentalmente um mesmo arquivo de saída. Comandos paralelos que modificam arquivo temporário comum podem introduzir condições de corrida não representadas pelo grafo declarado.

Compilação correta não garante testes aprovados, e teste aprovado não garante portabilidade para outra arquitetura. Versões de ferramentas, bibliotecas, flags e ambiente influenciam o resultado. Para repetibilidade maior, registre versões, parâmetros e entradas em vez de afirmar que toda execução Make produz binários byte a byte idênticos.

## Exercícios e verificação

1. Desenhe o grafo e indique quais alvos devem ser reconstruídos após mudar apenas main.c.
2. Explique por que alterar math_ops.h exige recompilar os dois objetos.
3. Preveja o que acontece se math_ops.o estiver ausente ao tentar ligar main.o.
4. Explique $@, $< e $^ numa receita fornecida [3].
5. Crie arquivo comum chamado check e explique por que .PHONY ainda executa o teste [4].
6. Compare make demo duas vezes sem alterações, distinguindo validade do build e teste comportamental independente.

Continue com [compilação e ligação](/pt/topics/c-compilation-object-files-linking/), [histórico e branches Git](/pt/topics/git-version-control-commits-branches/) e [CI/CD e releases](/pt/topics/ci-cd-release-engineering/).