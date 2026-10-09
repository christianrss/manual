---
id: processes-virtual-memory
title: "Processos, memória virtual e chamadas de sistema"
description: "Deduza isolamento de processos, tradução de endereços, tabelas de páginas, TLB, troca de contexto e proteção do kernel."
category: foundations
difficulty: intermediate
updated: 2026-10-09
prerequisites: [complexity-analysis]
sources:
  - {title: "MIT 6.1810 — xv6 teaching operating system", url: "https://pdos.csail.mit.edu/6.1810/2025/xv6.html", kind: "university reference"}
  - {title: "Operating Systems: Three Easy Pieces", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
---
Um sistema operacional oferece compartilhamento controlado de CPUs, memória e dispositivos, mantendo isolados programas que não devem confiar uns nos outros. Um **processo** não é apenas executável em execução: possui espaço de endereçamento, estado de CPU, recursos abertos, permissões e identidade mantida pelo kernel. Uma **thread** representa fluxo de execução dentro de um processo; threads normalmente compartilham memória do processo, mas possuem registradores e pilhas próprios [1][2].

## Por que o isolamento existe

Duas aplicações podem usar o *mesmo número de endereço virtual* sem acessar os mesmos bytes físicos. Modos de privilégio do processador, tradução de memória virtual e tabelas configuradas pelo kernel impõem as fronteiras. Um processo não pode escrever memória arbitrária do kernel apenas calculando um endereço: verificações de modo, mapeamento e permissão precisam impedir isso. Isolamento é um **mecanismo** de segurança, não promessa de imunidade a canais laterais, falhas do kernel ou regiões indevidamente compartilhadas.

Um executável em disco é passivo; o processo mantém estado dinâmico: contador de programa, registradores, mapeamentos e descritores. Carregar um programa cria imagem inicial e prepara a execução em modo usuário. Escalonamento define qual thread executa, e troca de contexto salva/restaura estado para outra prosseguir. Cache e TLB podem sofrer impactos, portanto trocar contexto não é sempre uma instrução gratuita [2].

## Dedução da tradução virtual para física

O endereço virtual não designa diretamente uma célula física arbitrária. Para página de tamanho P, decomponha endereço v em número de página virtual floor(v/P) e deslocamento v mod P. A tabela de páginas liga página virtual ao número de quadro físico e aos bits de permissão/validade. Se o mapeamento existe e autoriza a operação, endereço físico = quadro×P + deslocamento. Páginas virtuais distintas podem apontar ao mesmo quadro quando compartilhamento intencional é permitido; daí a necessidade de sincronizar acessos.

![Número da página virtual, deslocamento e tradução para o quadro físico.](/diagrams/page-translation.svg)

~~~python
def traduzir(endereco, tamanho_pagina, tabela, operacao="ler"):
    if endereco < 0 or tamanho_pagina <= 0:
        raise ValueError("endereco ou tamanho invalido")
    vpn, deslocamento = divmod(endereco, tamanho_pagina)
    if vpn not in tabela:
        raise MemoryError("pagina nao mapeada")
    quadro, permissoes = tabela[vpn]
    if quadro < 0 or operacao not in permissoes:
        raise PermissionError("mapeamento invalido ou acesso negado")
    return quadro * tamanho_pagina + deslocamento

tabela = {1: (7, {"ler", "escrever"}), 2: (11, {"ler"})}
assert traduzir(4096 + 13, 4096, tabela) == 7*4096 + 13
assert traduzir(8192, 4096, tabela, "ler") == 11*4096
try:
    traduzir(8192, 4096, tabela, "escrever")
    assert False
except PermissionError:
    pass
~~~

Esse modelo simula tradução de um nível; sistemas reais utilizam tabelas multinível, tamanhos de página definidos pela arquitetura e bits específicos de proteção. A tabela pertence a um espaço de endereçamento. O exemplo serve para ilustrar aritmética e condições, **não** para impor proteção real de memória.

## Page faults, TLB e paginação sob demanda

Mapeamento ausente ou proibido gera **falta de página** ou exceção de proteção, conforme arquitetura e política. Nem toda falta indica erro do programa: o SO pode alocar página anônima antes inexistente ou buscar dados do armazenamento. Acesso proibido pode encerrar o processo. O kernel trata a exceção, distingue casos recuperáveis de ilegais e retoma execução ou comunica erro.

O **translation lookaside buffer (TLB)** armazena traduções recentemente utilizadas. Quando não encontra entrada apropriada, processador ou software percorre estruturas de tabelas, mesmo que os dados estejam em RAM. Alterar espaço de endereçamento pode exigir invalidar entradas ou empregar tags como identificadores de espaço, dependendo da CPU. Padrões de memória e faltas de página influenciam desempenho mesmo com pouco trabalho aritmético [1].

## Chamadas de sistema e troca de privilégio

Uma syscall é entrada controlada do modo usuário em código privilegiado, normalmente através de instrução especial e identificação/validação da operação solicitada. O kernel verifica ponteiros e comprimentos fornecidos pelo usuário; um ponteiro recebido não passa a ser memória confiável do kernel. Argumentos podem indicar arquivos, buffers ou processos. O retorno restaura contexto e privilégios adequados. Interrupções decorrem de eventos externos, enquanto chamadas de sistema são traps síncronas solicitadas intencionalmente; ambas podem chegar ao kernel, mas suas origens diferem.

Numa leitura de arquivo, read(fd, buffer, count) exige validar descritor e destino, resolver objeto subjacente, copiar dados conforme implementação e retornar quantidade efetivamente lida ou erro. Leitura bem-sucedida pode devolver menos bytes que o solicitado: o usuário deve tratar leitura parcial. Uma syscall não implica obrigatoriamente uma operação física direta no disco.

## Escalonamento, contexto e recursos

O processo em execução pode ser preemptado, bloquear esperando E/S ou ceder CPU voluntariamente. O escalonador escolhe tarefas prontas segundo política e metas de justiça, prioridade e responsividade. Alternar threads do mesmo processo pode evitar mudanças do mapa de memória, mas ainda precisa preservar pilha e registradores; concorrência introduz condições de corrida quando o estado é compartilhado.

| Conceito | O que controla | Equívoco |
| --- | --- | --- |
| Memória virtual | Tradução e permissões | Todo byte virtual já ocupa RAM |
| Processo | Isolamento e recursos | Processo tem sempre uma thread |
| Syscall | Serviço privilegiado controlado | Ponteiro do usuário é confiável |
| Page fault | Falta ou proibição de tradução | Toda falta encerra o programa |
| Troca de contexto | Qual execução usa CPU | A troca não custa recursos |

## Decisões e limites

Páginas grandes reduzem parte do custo de tradução, mas aumentam fragmentação interna e complexidade de alocação. Copy-on-write permite compartilhar quadros até ocorrer escrita, quando pode ser necessário copiar; exige proteções e tratamento corretos de exceções. Threads em excesso consomem pilhas e tempo de escalonamento, enquanto poucas threads podem desperdiçar intervalos de E/S. A linguagem de programação não substitui a fronteira de proteção do kernel.

## Exercícios e verificação

1. Para página de 4096 bytes e endereço 12.345, calcule VPN=3 e deslocamento=57; confira 3×4096+57=12.345.
2. Explique por que dois processos podem mapear página virtual 3 para quadros físicos diferentes sem conflito.
3. Diferencie falta em página sob demanda de gravação numa página somente leitura: qual resposta do kernel é válida para cada caso segundo uma política definida?
4. Por que atualizar a tabela sem tratar entradas antigas de TLB pode manter traduções incorretas?
5. Percorra open→read→close e identifique a fronteira de validação para descritores e buffers do usuário.
