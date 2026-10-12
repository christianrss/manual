---
id: git-version-control-commits-branches
title: "Fundamentos de Git: diretório de trabalho, index, commits e branches"
description: "Compreenda os três estados do Git, snapshots versionados, branches e merges com uma sequência testável em repositório isolado."
category: engineering
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions, modular-programming-interfaces]
sources:
  - {title: "Pro Git — Recording Changes to the Repository", url: "https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository", kind: "official Git reference book"}
  - {title: "Pro Git — Branches in a Nutshell", url: "https://git-scm.com/book/en/v2/Git-Branching-Branches-in-a-Nutshell", kind: "official Git reference book"}
  - {title: "Git — git-restore manual", url: "https://git-scm.com/docs/git-restore", kind: "official Git manual"}
  - {title: "Git — git-merge manual", url: "https://git-scm.com/docs/git-merge", kind: "official Git manual"}
---
Um projeto de software precisa preservar qual alteração introduziu determinado comportamento e como uma linha de desenvolvimento se relaciona com outra. Guardar cópias chamadas final, final2 ou ultima não fornece histórico confiável. Git oferece **snapshots versionados e um histórico de commits**, mas exige compreender três estados locais antes de usar seus comandos: diretório de trabalho, index e árvore já registrada. Esse modelo antecede revisão de código, políticas de branches e implantação automatizada [1][2].

## Três estados de uma alteração local

O **diretório de trabalho** contém os arquivos que o desenvolvedor modifica. O **index**, também chamado área de staging, registra as versões específicas de arquivos candidatas ao próximo commit. O **commit HEAD** identifica um snapshot já preservado. Os três podem divergir: arquivo editado no diretório de trabalho, versão distinta preparada no index e versão anterior gravada no HEAD [1].

Imagine note.txt na versão A do commit. Editá-lo cria a versão B no diretório de trabalho, sem mudar o index. Executar git add copia o conteúdo B para o index. Editar novamente para C deixa C no diretório, mas B continua preparado. Fazer commit nesse momento registra B, não C. Essa é a razão para verificar git status e analisar diferenças preparadas e não preparadas antes de cada registro.

O index não é simplesmente um indicador booleano de arquivo alterado. Ele mantém o conteúdo e informações para montar a árvore do próximo commit. Um commit representa um snapshot de conteúdo rastreado, com referências a ancestrais e metadados; não grava necessariamente o estado completo do computador.

## O que um commit registra

Um commit identifica uma árvore de conteúdo e geralmente um ou mais commits ancestrais, além de metadados como autoria e mensagem. O commit inicial não possui pais; commit normal fora de merge costuma possuir um; merge convencional de dois ramos pode possuir dois. Assim surge um **grafo acíclico dirigido de ancestralidade**, não uma sequência obrigatoriamente linear para todos os colaboradores [2].

Identidade do conteúdo e identidade do commit não são equivalentes. Alterar mensagem, pai, timestamp ou outros metadados pode produzir outro ID de commit mesmo com o mesmo conteúdo da árvore. Portanto, o hash identifica um objeto de histórico, não uma prova de que o software está correto ou passou nos testes.

Os metadados do autor também não comprovam automaticamente identidade pessoal. Revisão, permissões do repositório e políticas de assinatura são controles separados. O exemplo define identidade sintética local apenas para permitir commits sem depender da configuração global do leitor.

## Branches são referências móveis

O nome de um branch é uma referência a commit, não outra cópia completa dos arquivos do projeto. Ao acessar o branch edit e fazer commit, a referência avança. Enquanto isso, main pode permanecer apontando para o commit original. Os históricos são relacionados depois por um merge. O mecanismo é eficiente porque Git não duplica cada versão integral de todos os arquivos em diretórios independentes [2].

HEAD geralmente identifica o branch selecionado. Pode também apontar diretamente para commit no modo detached HEAD; nesse estado, novos commits não avançam automaticamente um branch nomeado. É útil para inspeção, mas exige atenção se as alterações precisam continuar acessíveis posteriormente.

Um branch remoto rastreado localmente, como origin/main, representa a situação conhecida na última sincronização. Não é garantia de atualização contínua do servidor. Fetch e push são operações separadas: fazer commit local não publica alterações automaticamente.

## Crie um branch e integre a alteração

O exemplo de shell deve ser executado num diretório temporário vazio. Utiliza apenas arquivos Git locais, sem comunicação remota. O branch main registra o primeiro snapshot; edit registra a segunda versão. O merge com no-fast-forward produz commit de integração com dois pais. Trata-se de demonstração do histórico, não política obrigatória para toda equipe.

~~~sh
git init -q
git config user.name "Local Example"
git config user.email "example@example.invalid"
printf 'first\n' > note.txt
git add -- note.txt
git commit -q -m "record first version"
git branch -M main
git switch -q -c edit
printf 'second\n' > note.txt
git add -- note.txt
git commit -q -m "change note"
git switch -q main
git merge -q --no-ff -m "merge edit" edit
git log --oneline --graph --all
git status --short
~~~

Ao final, note.txt contém second, enquanto index e diretório de trabalho estão limpos. O grafo contém commit inicial, alteração no branch edit e merge. Quando não há divergência, merge convencional pode simplesmente avançar a referência, sem criar outro commit; a opção no-fast-forward foi escolhida para tornar visível a estrutura com dois pais [4].

## Merge não é concatenação automática de texto

Se ambos os branches modificam trechos sobrepostos, Git pode indicar conflito que exige resolução humana. O conflito significa que o sistema não consegue selecionar com segurança uma versão única; não demonstra que qualquer autor esteja necessariamente errado. Numa integração de três vias, o ancestral comum e os conteúdos de ambos os lados participam da decisão [4].

Revise o comportamento pretendido, edite o arquivo conflitante para produzir a versão correta, prepare essa versão e finalize o merge. Em determinadas situações, git merge --abort permite cancelar uma integração não concluída, mas iniciar com edições não registradas aumenta o risco de perda. Prefira estado de trabalho limpo antes do merge [4].

Merge cria histórico de integração. Rebase é outra operação, que recria commits sobre uma base diferente e modifica suas identidades. Um force push que reescreve histórico compartilhado pode descartar alterações de colaboradores; exige política explícita, não deve ser empregado por conveniência.

## Restaurar estado sem destruir trabalho

Existem objetivos diferentes: retirar conteúdo do staging preservando edições e substituir o conteúdo do diretório por versão registrada. O primeiro pode usar git restore --staged; o segundo usa git restore no arquivo do diretório de trabalho. A fonte padrão muda conforme as opções: restaurar staging normalmente usa HEAD, e restaurar diretório normalmente usa o index [3].

Restaurar arquivo do diretório pode descartar edições não registradas. Comandos que reescrevem histórico ou apagam arquivos rastreados podem produzir perdas mais difíceis de reverter. Antes disso, use git status, git diff e git diff --staged para identificar em qual estado está o trabalho valioso.

Git registra conteúdo rastreado, não automaticamente todo arquivo que ainda não foi adicionado. Um segredo já commitado pode permanecer no histórico mesmo depois de apagado por novo commit; exclusão posterior não equivale a remoção segura do segredo. Examine regras de ignore e proteções, lembrando que ignore não retira retroativamente um arquivo já rastreado.

## Testes, invariantes e limites de complexidade

Um teste independente pode criar repositório em diretório temporário, registrar um arquivo, preparar a versão B, editar novamente para C e demonstrar que o commit contém B. Outro teste cria branches e exige um merge com exatamente dois pais. São testes de comportamento real dos comandos, não de formatação textual presumida do terminal.

O invariante do histórico é que commits normais apontam para árvore de conteúdo e objetos ancestrais pelos quais é possível rastrear relações. O merge modifica a estrutura sem garantir que o programa combinado passe nos testes. Revisão deve relacionar alterações a requisitos e verificações executáveis, sem confundir nome de branch com evidência de qualidade.

Custos de armazenamento e tempo dependem do volume de objetos alterados, tamanho do histórico, compactação e manutenção. É incorreto afirmar que toda operação Git custa O(1) simplesmente porque branch é referência. Criar referência costuma ser barato, mas checkout de muitos arquivos e merge de conteúdos conflitantes exigem trabalho adicional.

## Exercícios e verificação

1. Prepare versão B de arquivo, altere diretório para C e explique qual será incluída no commit.
2. Inspecione diffs de staging e de trabalho separadamente, identificando a referência consultada.
3. Conte os pais de um commit de merge e compare-o ao avanço fast-forward.
4. Explique por que novo commit local não está automaticamente publicado no servidor remoto.
5. Demonstre retirar arquivo do staging sem destruir sua edição local [3].
6. Explique por que resolver conflito e passar em testes comportamentais são responsabilidades distintas.

Continue com [limites de módulos](/pt/topics/modular-programming-interfaces/), [build incremental](/pt/topics/build-dependency-graphs-gnu-make/) e [ciclo de desenvolvimento](/pt/topics/software-project-lifecycle/).