---
id: inode-directories-journaling-recovery
title: "Sistemas de arquivos: inodes, blocos, journaling e recuperação"
description: "Modele inodes, entradas de diretório, alocação não contígua de blocos e recuperação por redo log com testes finitos independentes."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [file-descriptors-buffering-fsync, heap-allocation-fragmentation]
sources:
  - {title: "MIT xv6-riscv book — File systems and logging", url: "https://mit-pdos.github.io/xv6-riscv-book/", kind: "university operating system textbook"}
  - {title: "OSTEP — File System Implementation and Crash Consistency", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
  - {title: "Linux kernel — ext4 on-disk journal (jbd2)", url: "https://www.kernel.org/doc/html/latest/filesystems/ext4/journal.html", kind: "official Linux kernel documentation"}
  - {title: "Linux kernel — ext4 filesystem administrator guide", url: "https://www.kernel.org/doc/html/latest/admin-guide/ext4.html", kind: "official Linux kernel documentation"}
  - {title: "Linux man-pages — fsync(2)", url: "https://man7.org/linux/man-pages/man2/fsync.2.html", kind: "official Linux syscall reference"}
---
Um **sistema de arquivos** atribui nomes a objetos persistentes e administra blocos, metadados e recuperação. O capítulo anterior sobre [descritores de arquivos](/pt/topics/file-descriptors-buffering-fsync/) explica como um processo referencia objetos e o significado de `fsync`. Agora vamos abaixo dessa interface: um diretório associa **nomes a inodes**, o inode descreve o objeto, e o mapeamento de blocos liga posições lógicas do arquivo ao armazenamento. Num filesystem real, alterar essas estruturas exige várias operações sujeitas a falhas [1][2].

Construiremos **dois modelos educacionais distintos**: diretório plano com IDs de inode e tabela de blocos ocupados; e journal de redo exclusivo de metadados, com marca de commit e repetição na recuperação. Os modelos não compartilham estado nem formam juntos um filesystem persistente e seguro. A distinção evita confundir correção de alocação com correção de protocolo de recuperação.

## Nome de arquivo não é identidade do inode

Uma entrada de diretório relaciona componente de caminho a identificador de objeto, frequentemente um número de inode. O inode armazena tipo, tamanho, permissões, timestamps e referências para localizar os blocos. Um descritor obtido por `open` referencia uma **descrição de arquivo aberto** que, por sua vez, aponta para um objeto persistente. São camadas diferentes de identidade [1].

Isso esclarece operações importantes. **Rename** pode trocar o nome sem alterar identidade de inode nem conteúdo. Alguns sistemas permitem vários nomes para um mesmo inode por meio de **hard links**, controlando contagem de ligações. Remover um nome por unlink não exige liberar imediatamente o inode quando outras ligações ou descritores abertos ainda apontam para o objeto. A regra de ciclo de vida depende tanto de nomes quanto de referências ativas [1][2].

O modelo admite **exatamente uma entrada de diretório por inode** e não implementa FDs abertos. Por isso, `unlink` libera imediatamente inode e blocos. Isso **não descreve o comportamento geral do unlink no Linux** quando existem hard links ou descritores abertos. A restrição permite provar invariantes pequenos sem generalizar incorretamente.

## Do offset lógico para o bloco de armazenamento

Um arquivo de tamanho `L`, em blocos de tamanho `B`, precisa de `ceil(L/B)` blocos quando armazenado densamente. Para offset lógico `o`, o índice lógico é `o // B` e o deslocamento interno é `o % B`. O inode associa índice lógico a ID de bloco físico, sem exigir que os IDs sejam consecutivos. Isso difere da [alocação contígua de heap](/pt/topics/heap-allocation-fragmentation/), na qual uma requisição precisa caber numa única região sem interrupções [1][2].

Um bitmap de blocos livres registra disponibilidade. Ele pode permitir localizar candidatos sem percorrer todos os inodes, mas não elimina fragmentação nem garante complexidade constante. Filesystems reais usam apontadores diretos/indiretos, extents, grupos de alocação ou árvores, conforme o formato. O xv6 fornece referência didática de inodes, diretórios e log; o ext4 possui mecanismos muito mais complexos [1][3].

A lista Python possui `None` para bloco livre ou exatamente `B` bytes para ocupado. `None` representa **estado de propriedade**, não bytes reais lidos de dispositivo. Ao crescer um arquivo, são escolhidos os menores IDs livres, mesmo que não contíguos, e seu conteúdo é regravado na representação densa. Não há buracos esparsos, blocos indiretos ou delayed allocation. Trata-se de **mapeamento lógico de blocos**, não de driver.

## Falha de capacidade não pode corromper metadados

Suponha que um arquivo de dois blocos queira um terceiro, mas o restante já pertence a outros arquivos. Neste contrato didático, a operação deve falhar **sem alterar tamanho, diretório nem blocos existentes**. Uma implementação ingênua que atualize o tamanho do inode **antes** de reservar espaço pode produzir metadados inconsistentes quando falta capacidade.

Para testar essa propriedade, `append` constrói o conteúdo proposto, calcula os blocos necessários e verifica antecipadamente se existem IDs livres em quantidade suficiente. Somente depois da verificação altera dados e metadados. Cada crescimento bem-sucedido reserva os blocos adicionais exclusivamente; nenhum ID pode pertencer simultaneamente a dois inodes. Append vazio é operação sem efeito que retorna sucesso mesmo com o armazenamento lotado.

Em um filesystem real, uma operação também pode falhar por quota, I/O, reservas ou condições complexas de ENOSPC. O exemplo não contempla esses motivos e rejeita nomes inválidos e payloads não binários para separar erros de entrada de falta de espaço.

## Modelo executável de diretório, inodes e blocos

O diretório plano aceita nomes simples, sem barra, espaços laterais ou os componentes especiais `.` e `..`. `create` cria inode; `rename` troca a chave sem alterar seu ID; `append` usa tantos blocos livres quanto necessário; `unlink` devolve os blocos ao conjunto disponível. Não há cursor de leitura/escrita: offsets de descrições abertas pertencem ao capítulo anterior.

~~~python
class TinyBlockFS:
    def __init__(self, count=8, block_size=4):
        if (type(count) is not int or count <= 0
                or type(block_size) is not int or block_size <= 0):
            raise ValueError("positive integer block geometry required")
        self.block_size = block_size
        self.slots = [None] * count
        self.directory = {}
        self.inodes = {}
        self.next_inode = 1

    def _name(self, name):
        if (not isinstance(name, str) or not name
                or name != name.strip() or "/" in name
                or name in (".", "..")):
            raise ValueError("invalid flat-directory name")

    def _inode(self, name):
        if name not in self.directory:
            raise KeyError(name)
        return self.inodes[self.directory[name]]

    def create(self, name):
        self._name(name)
        if name in self.directory:
            raise FileExistsError(name)
        inode_id = self.next_inode
        self.next_inode += 1
        self.inodes[inode_id] = {"size": 0, "blocks": []}
        self.directory[name] = inode_id
        return inode_id

    def read(self, name):
        inode = self._inode(name)
        contents = b"".join(self.slots[i] for i in inode["blocks"])
        return contents[:inode["size"]]

    def append(self, name, payload):
        inode = self._inode(name)
        if type(payload) is not bytes:
            raise ValueError("bytes required")
        if not payload:
            return True
        content = self.read(name) + payload
        needed = (len(content) + self.block_size - 1) // self.block_size
        extra = needed - len(inode["blocks"])
        available = [i for i, block in enumerate(self.slots) if block is None]
        if extra > len(available):
            return False  # failure leaves all state unchanged
        allocated = inode["blocks"] + available[:extra]
        for position, index in enumerate(allocated):
            chunk = content[position * self.block_size:
                            (position + 1) * self.block_size]
            self.slots[index] = chunk.ljust(self.block_size, b"\x00")
        inode["blocks"] = allocated
        inode["size"] = len(content)
        return True

    def rename(self, old, new):
        self._name(new)
        if old not in self.directory:
            raise KeyError(old)
        if new in self.directory:
            raise FileExistsError(new)
        self.directory[new] = self.directory.pop(old)

    def unlink(self, name):
        inode = self._inode(name)
        for index in inode["blocks"]:
            self.slots[index] = None
        del self.inodes[self.directory.pop(name)]

    def usage(self):
        used = sum(block is not None for block in self.slots)
        return (used, len(self.slots) - used)

fs = TinyBlockFS(4, 4)
assert fs.create("a") == 1
assert fs.append("a", b"abcde")
assert fs.create("b") == 2
assert fs.append("b", b"1234")
assert fs.append("a", b"fghij")
assert fs.read("a") == b"abcdefghij"
assert fs.usage() == (4, 0)
assert fs.append("b", b"56") is False
assert fs.read("b") == b"1234"  # failed growth did not mutate
fs.unlink("a")
assert fs.usage() == (1, 3)
assert fs.append("b", b"56")
fs.rename("b", "c")
assert fs.read("c") == b"123456"
assert fs.usage() == (2, 2)
~~~

A sequência ocupa inicialmente quatro blocos. Arquivos A e B compartilham o conjunto de recursos, mas nunca recebem o mesmo bloco. A tentativa de ampliar B falha sem alterar estado. Remover A libera três blocos, permitindo crescer B, mesmo que não seja obrigatório obter posições contíguas. Renomear B para C preserva inode, conteúdo e blocos alocados.

**Invariante de conservação:** os blocos ocupados `S` e livres `F` particionam `{0,...,N-1}`. Todo índice ocupado pertence a **exatamente um** inode ativo, e seu total de blocos é `ceil(tamanho/B)` (zero para arquivo vazio). A sobra no último bloco é **padding neste modelo**, não uma segunda alocação. Todo nome aponta para inode vivo, e cada inode vivo possui exatamente um nome.

Se existem `n` blocos e arquivo de `L` bytes, o método `append` percorre até `O(n)` posições, reúne conteúdo e regrava `O(L+payload)` bytes. Não se trata de caminho de escrita eficiente. Consultas em dicionários têm custo médio esperado constante para identificadores de tamanho limitado. A simulação armazena os bytes de todos os blocos ocupados, usando até `O(nB + metadados)` de memória. Uma implementação real precisa resolver muitos outros problemas [1].

## Diretórios, hard links e alcance de objetos

Um diretório real também é objeto de filesystem; resolver caminho com vários componentes exige percorrer entradas sucessivamente. Permissões e links simbólicos mudam o comportamento, inclusive se o caminho é atravessável. Nosso dicionário de um só nível **não** implementa inode raiz, navegação por `..`, symlink, rename entre diretórios nem substituição atômica de nome existente.

Depois de remover a última ligação de nome num sistema real, o inode pode continuar acessível por descrição ainda aberta. Por outro lado, entrada de diretório que aponta para inode inexistente representa metadados inconsistentes. Link counts, listas de órfãos, análise de alcance e recuperação lidam com esses casos [1][2]. Portanto, “um nome por inode” é invariante **exclusivo deste exemplo**, não propriedade geral do ext4.

## Por que a ordem das gravações importa numa falha

Adicionar bloco pode exigir atualizar **três tipos de estado**: conteúdo do bloco, bitmap de alocação e tamanho/apontadores do inode. Uma queda do sistema entre operações pode deixar inode apontando para bloco que o bitmap considera livre, ou bloco marcado ocupado sem referência. O primeiro caso permite reutilização com corrupção; o segundo desperdiça espaço [2].

**Consistência após crash** não equivale à atomicidade de função Python. Nossa checagem de capacidade evita mutação parcial ao receber uma requisição válida que não cabe, mas **não transforma três gravações físicas em operação indivisível** diante de perda de energia. O capítulo de [buffering e fsync](/pt/topics/file-descriptors-buffering-fsync/) explica visibilidade antes da durabilidade e a necessidade de sincronizar diretório ao criar nomes [5].

Um verificador como `fsck` pode reconstruir invariantes examinando o estado armazenado; isso difere de repetir operações registradas previamente em journal. Uma reparação após crash pode corrigir a estrutura e ainda perder bytes ou nomes. Portanto não garante a sobrevivência de toda atualização confirmada [2].

## Journaling de metadados e marcador de commit

O **redo log write-ahead** registra alterações pretendidas antes de aplicá-las aos blocos definitivos de metadados. A transação só pode ser repetida se o conjunto completo de registros e o **marcador de commit** estiverem persistidos. Após esse limite, operações podem ser instaladas na estrutura principal. Se ocorrer falha durante a instalação, a recuperação repete o journal. Como atribuir um valor determinado é idempotente, registros já aplicados podem ser executados novamente [1][3].

A ordem de gravações estáveis é a propriedade essencial: acrescentar registros a uma lista Python **não garante resistência à queda de energia**. Journals reais tratam escrita interrompida, checksum, barreiras, caches, espaço de log e ordenação de recuperação. A documentação do ext4 jbd2 descreve commits e replay; normalmente o ext4 **não grava todos os dados de arquivos no journal**. Os modos `data=ordered`, `data=writeback` e `data=journal` oferecem garantias diferentes de ordenação de dados [3][4].

O segundo modelo armazena somente **campos inteiros de metadados**, como tamanho de inode e quantidade de blocos. O conjunto de registros e a marca de commit são considerados **eventos abstratos indivisíveis e duráveis**. Uma transação confirmada pode ser aplicada parcialmente a `home` antes da falha; a recuperação repete tudo. Não modelamos payloads, journal circular, setores físicos nem chamadas reais a `fsync`.

## Modelo executável de recuperação por redo

~~~python
class MetadataRedoLog:
    def __init__(self, home):
        if (not isinstance(home, dict)
                or any(not isinstance(k, str) or not k
                       or type(v) is not int or v < 0
                       for k, v in home.items())):
            raise ValueError("metadata must map keys to nonnegative integers")
        self.home = dict(home)
        self.records = []
        self.committed = False
        self.installed = 0

    def stage(self, key, value):
        if self.committed:
            raise RuntimeError("finish or recover current transaction first")
        if (not isinstance(key, str) or not key
                or type(value) is not int or value < 0):
            raise ValueError("invalid metadata record")
        self.records.append((key, value))

    def commit(self):
        if self.committed or not self.records:
            raise RuntimeError("no new transaction available")
        self.committed = True  # abstract persisted commit marker

    def install_one(self):
        if not self.committed:
            raise RuntimeError("install requires a committed journal")
        if self.installed == len(self.records):
            return False
        key, value = self.records[self.installed]
        self.home[key] = value
        self.installed += 1
        return True

    def finish(self):
        if not self.committed or self.installed != len(self.records):
            raise RuntimeError("checkpoint cannot precede full installation")
        self.records = []
        self.committed = False
        self.installed = 0

    def recover(self):
        if self.committed:
            # Redo is idempotent: replay from the beginning, including
            # entries possibly installed before the crash.
            for key, value in self.records:
                self.home[key] = value
        self.records = []
        self.committed = False
        self.installed = 0

log = MetadataRedoLog({"inode.size": 0, "bitmap.used": 0})
log.stage("inode.size", 8)
log.stage("bitmap.used", 2)
log.recover()  # crash before commit marker: discard transaction
assert log.home == {"inode.size": 0, "bitmap.used": 0}
log.stage("inode.size", 8)
log.stage("bitmap.used", 2)
log.commit()
assert log.install_one()
assert log.home == {"inode.size": 8, "bitmap.used": 0}
log.recover()  # crash after commit: replay both records
assert log.home == {"inode.size": 8, "bitmap.used": 2}
log.stage("inode.size", 12)
log.commit()
assert log.install_one()
log.finish()
log.recover()
assert log.home["inode.size"] == 12
~~~

Observe os limites: antes de `commit`, `recover` descarta registros e mantém estado original. Após `commit`, `install_one` atualiza somente o tamanho do inode, deixando o estado principal momentaneamente incoerente; `recover` repete ambos os registros e retorna à consistência. O modelo presume que nenhum leitor examina checkpoint parcial e que registros são atribuições repetíveis.

O **invariante de redo** é condicional: sem marcador de commit, nenhuma instalação foi iniciada e a recuperação deve ignorar a transação. Com marcador, todos os registros devem ser reaplicados, ainda que alguns já tenham sido instalados. O código impede instalação antes do commit e `finish` antes de todos os registros. Apagar journal comprometido e ainda incompleto destruiria informações necessárias à recuperação.

Após recuperar, `home` deve ser igual ao estado anterior (sem commit) ou ao estado obtido pela aplicação de **todos** os registros confirmados em ordem. Uma sequência pode atribuir duas vezes a mesma chave; prevalece a última. Oráculo independente pode computar esse dicionário final sem reutilizar `recover`.

## ext4 jbd2, fsync da aplicação e WAL de bancos

No modo usual, ext4 registra **metadados** no journal e ordena determinadas gravações sujas de dados antes de confirmar seus metadados. Isso reduz classes específicas de inconsistência, mas não converte qualquer escrita da aplicação em transação atômica [3][4]. O modo `data=writeback` apresenta ordenação mais fraca; `data=journal` inclui dados e metadados no journal, com custos diferentes. O efeito concreto depende ainda da montagem e da conclusão correta de writeback.

Uma chamada `fsync` bem-sucedida possui obrigações em nível de arquivo e diretório; journaling por si só não substitui o protocolo de sincronização escolhido pela aplicação. Numa substituição com arquivo temporário, devemos estudar escrita e sincronização do temporário, rename e sincronização do diretório, incluindo falhas entre etapas [5].

O **WAL de banco de dados** resolve problema de transação em outra camada: alterações de linhas, índices e recuperação podem exigir registros de log ordenados antes de gravar páginas modificadas. O journal do filesystem pode preservar consistência estrutural de metadados sem provar que uma transação relacional foi confirmada. O capítulo de [armazenamento e WAL](/pt/topics/database-storage-wal/) trata o protocolo distinto.

## Exercícios e verificação

1. Calcule índice de bloco lógico e deslocamento interno para offset de arquivo 19 e bloco 8; explique por que o bloco físico escolhido não precisa ser o ID 2.
2. Monte arquivo de três blocos e outro de um bloco em conjunto de quatro. Mostre por que crescimento adicional falha sem mutação e como a liberação muda a capacidade.
3. Renomeie o arquivo; especifique quais propriedades mudam entre nome, ID de inode, bytes e IDs de blocos. Compare com rename que substitui destino existente.
4. Estenda a tabela com hard links e descritores abertos. Declare exatamente quando blocos podem ser liberados após unlink.
5. Desenhe verificador que encontra blocos com dois proprietários, entrada para inode inexistente, bloco ocupado órfão e erro em `ceil(size/B)`.
6. Enumere crashes antes do marcador de commit e depois de cada registro instalado. Calcule o estado recuperado em todos os casos.
7. Amplie redo para várias transações sequenciais. Explique a ordenação necessária para checkpoint e truncamento do journal, e por que o exemplo não possui concorrência.
8. Compare `fsync` de arquivo recém-criado com `fsync` do diretório pai. Que falha pode deixar nome ausente apesar de bytes persistidos?
9. Diferencie journaling de metadados, journaling completo e WAL da aplicação. Identifique uma garantia que **nenhum** oferece sem hipóteses sobre o dispositivo.

**Continuidade:** laboratórios com injeção de falhas e persistência real permitirão estudar estados intermediários em disco; fundamentos de redes e criptografia permanecem lacunas curriculares distintas. O capítulo comprova somente os **contratos finitos do modelo abstrato**, não a durabilidade do Linux [1][2][3][4][5].
