---
id: file-descriptors-buffering-fsync
title: "Descritores de arquivos, buffering de I/O e persistência com fsync"
description: "Estude descritores, dup, offsets compartilhados, read/write, buffering e fsync com modelos Python e testes independentes."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [processes-virtual-memory]
sources:
  - {title: "Operating Systems: Three Easy Pieces — File Systems", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
  - {title: "Linux man-pages — open(2)", url: "https://man7.org/linux/man-pages/man2/open.2.html", kind: "official Linux/POSIX API reference"}
  - {title: "Linux man-pages — dup(2)", url: "https://man7.org/linux/man-pages/man2/dup.2.html", kind: "official Linux/POSIX API reference"}
  - {title: "Linux man-pages — fsync(2)", url: "https://man7.org/linux/man-pages/man2/fsync.2.html", kind: "official Linux/POSIX API reference"}
  - {title: "Linux man-pages — write(2)", url: "https://man7.org/linux/man-pages/man2/write.2.html", kind: "official Linux/POSIX API reference"}
---
Um descritor de arquivo (FD) é um inteiro pequeno que referencia uma **descrição de arquivo aberto**, não um nome de caminho ou endereço físico do disco. O sistema operacional separa a tabela de descritores do processo, o deslocamento (*offset*) e os flags da descrição aberta, e o objeto persistente representado pelo arquivo. Essa diferença explica por que dois descritores podem compartilhar o cursor enquanto duas aberturas independentes normalmente não o compartilham [2][3].

O capítulo de [processos e memória virtual](/pt/topics/processes-virtual-memory/) introduz recursos e limites das syscalls. Aqui estudaremos `open`, `dup`, `read`, `write`, `lseek`, `close`, buffering e `fsync`. Dois **modelos didáticos separados** tornam os contratos observáveis e verificáveis. Não substituem POSIX, um sistema de arquivos de produção, testes de hardware nem protocolos completos de consistência após falhas [1].

## Nome, inode, descrição aberta e descritor

Há pelo menos três camadas: uma **entrada de diretório** associa nome a objeto do filesystem, normalmente um inode; uma **descrição de arquivo aberto** conserva o offset e os flags de status; e um **descritor do processo** aponta para uma descrição. Flags próprios do descritor, como `FD_CLOEXEC`, são conceitualmente diferentes dos flags compartilhados da descrição [2][3].

| Operação | Novo FD? | Nova descrição aberta? | Offset |
| --- | --- | --- | --- |
| `open("note")` | Sim | Sim | Começa em zero (sem outras modalidades) |
| `dup(fd)` | Sim | **Não** | Compartilhado com o FD original |
| Outro `open("note")` | Sim | Sim | Independente; conteúdo subjacente é comum |
| `close(fd)` | Remove FD | Descrição pode continuar referenciada | Outros duplicados permanecem válidos |

No Linux, a descrição aberta não é o próprio pathname usado na abertura; pode continuar acessível após renomeação ou unlink do nome original [2]. `dup(2)` aloca o menor número de FD livre e referencia a **mesma** descrição aberta, compartilhando offset e flags de status, não necessariamente os flags por descritor [3]. Este modelo cobre apenas um processo e não implementa `fork`, `exec`, `dup2`, controle de acesso, troca de path, flags nem identidade real de inode.

## Offsets e posição compartilhada são estado observável

O *offset* define o ponto de partida de `read` e `write` sequenciais. Uma leitura bem-sucedida avança pelo **número realmente lido**, não pela quantidade solicitada. Ao chegar ao fim de arquivo regular, a leitura pode devolver zero bytes sem avançar o cursor. Uma nova abertura cria uma descrição com offset novo; uma duplicação compartilha o objeto, de modo que `seek` por um FD altera a posição usada pelos demais FDs ligados à mesma descrição [2][3].

Uma escrita pode sobrescrever bytes existentes ou ampliar o arquivo. Se o programa buscar posição além do EOF e escrever, este modelo preenche o intervalo com bytes zero num `bytearray` denso. Um filesystem real pode representar o intervalo como **buraco esparso**, retornando zeros na leitura sem precisar alocar blocos físicos para todos os bytes ausentes [1].

As syscalls reais `read(2)` e `write(2)` são mais complexas: podem falhar, sofrer interrupção ou transferir **menos bytes que a quantidade solicitada**. `write` bem-sucedido também não promete, sozinho, persistência na mídia. O programa deve verificar contagem e tratar falhas e progresso parcial conforme o contrato do arquivo e da syscall [5]. Nosso código escolhe transferências completas de arquivo regular **em memória**, sem falhas injetadas.

## Modelo executável de descritores e descrições abertas

Cada `OpenDescription` mantém um offset mutável ligado a um path. A tabela `DescriptorModel.descriptors` conecta números de FD a objetos de descrição; `files` contém os bytes. A duplicação guarda **a mesma instância Python** duas vezes, enquanto outra abertura constrói **nova instância**, mas consulta os mesmos bytes. O menor FD livre é reutilizado.

~~~python
from dataclasses import dataclass

@dataclass
class OpenDescription:
    path: str
    offset: int = 0

class DescriptorModel:
    def __init__(self, files):
        if (not isinstance(files, dict)
                or any(not isinstance(path, str) or not path
                       or type(data) is not bytes
                       for path, data in files.items())):
            raise ValueError("expected a mapping of file names to bytes")
        self.files = {path: bytearray(data) for path, data in files.items()}
        self.descriptors = {}

    def _lowest_fd(self):
        number = 0
        while number in self.descriptors:
            number += 1
        return number

    def _open_description(self, fd):
        if type(fd) is not int or fd not in self.descriptors:
            raise KeyError(fd)
        return self.descriptors[fd]

    def open(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        fd = self._lowest_fd()
        self.descriptors[fd] = OpenDescription(path)
        return fd

    def dup(self, fd):
        description = self._open_description(fd)
        duplicate = self._lowest_fd()
        self.descriptors[duplicate] = description
        return duplicate

    def close(self, fd):
        self._open_description(fd)
        del self.descriptors[fd]

    def seek(self, fd, offset):
        description = self._open_description(fd)
        if type(offset) is not int or offset < 0:
            raise ValueError("nonnegative absolute offset required")
        description.offset = offset

    def tell(self, fd):
        return self._open_description(fd).offset

    def read(self, fd, count):
        description = self._open_description(fd)
        if type(count) is not int or count < 0:
            raise ValueError("nonnegative read count required")
        data = self.files[description.path]
        chunk = bytes(data[description.offset:description.offset + count])
        description.offset += len(chunk)
        return chunk

    def write(self, fd, payload):
        description = self._open_description(fd)
        if type(payload) is not bytes:
            raise ValueError("byte payload required")
        if not payload:
            return 0  # zero-byte writes do not extend the file
        data = self.files[description.path]
        start = description.offset
        if start > len(data):
            data.extend(bytes(start - len(data)))
        end = start + len(payload)
        if end > len(data):
            data.extend(bytes(end - len(data)))
        data[start:end] = payload
        description.offset = end
        return len(payload)

    def snapshot(self, path):
        return bytes(self.files[path])

model = DescriptorModel({"note": b"ABCDE"})
first = model.open("note")
shared = model.dup(first)
assert (first, shared) == (0, 1)
assert model.read(first, 2) == b"AB"
assert model.read(shared, 2) == b"CD"    # same open description
independent = model.open("note")
assert model.read(independent, 2) == b"AB"  # separate offset
model.seek(shared, 1)
assert model.tell(first) == 1
assert model.write(first, b"xy") == 2
assert model.snapshot("note") == b"AxyDE"
assert model.read(shared, 2) == b"DE"
model.close(first)
assert model.read(shared, 1) == b""
model.close(shared)
assert model.open("note") == 0  # lowest unused descriptor
~~~

A questão central é distinguir `shared` de `independent` sem depender dos números dos FDs: `first` e `shared` usam a **mesma descrição**, então uma leitura altera o offset observado pela outra. `independent` começa no offset zero. Os três veem as alterações no mesmo conteúdo subjacente. Fechar `first` não fecha `shared` e um novo FD pode reutilizar o número que foi liberado.

Os **invariantes** são: todo FD ativo aponta para uma descrição; FDs obtidos por `dup` compartilham exatamente aquele objeto; aberturas independentes usam objetos distintos; todo offset é não negativo; leitura avança pelo tamanho realmente retornado; todas as leituras e escritas acessam os mesmos bytes por path. FDs inválidos geram `KeyError`, nomes inexistentes geram `FileNotFoundError` e tamanhos/payloads inválidos são rejeitados antes de modificar o estado. Essas verificações não resolvem corrida de memória em código nativo externo.

A busca de um FD e a consulta ao dicionário custam `O(1)` em média, mais `O(k)` para copiar `k` bytes. Uma escrita depois do EOF também pode alocar `O(lacuna)` zeros. Encontrar o menor FD disponível custa `O(d)` no pior caso, com `d` descritores ativos, porque este modelo simples não mantém estrutura de números livres. Memória usada é proporcional ao total de bytes em arquivos e à quantidade de descritores; não demonstra ocupação física de disco.

## Do buffer da aplicação ao page cache e ao dispositivo

**I/O com buffering não significa um único buffer universal.** Bibliotecas e runtimes podem acumular bytes no espaço do usuário antes de chamar o kernel; o kernel pode manter páginas sujas no page cache após `write`; camada de blocos e dispositivo podem ter filas e caches próprios. `fflush` em fluxo stdio de C, por exemplo, encaminha dados acumulados na aplicação, mas não equivale a `fsync` para durabilidade [4].

Um `write` entregue ao kernel pode ficar visível para leitores e ainda residir em cache volátil. Da mesma forma, um `close` sem erro não serve como prova geral de persistência em mídia não volátil. **Visibilidade**, **ordenação** e **durabilidade** são propriedades distintas. Garantias concretas dependem de filesystem, syscalls, conclusão de I/O e erros observados, não apenas do fato de a chamada ter retornado [4][5].

Buffering também muda latência e vazão: juntar escritas pequenas pode reduzir syscalls, mas consome memória e adia algumas falhas. **I/O direto** possui restrições particulares de alinhamento e cache; não se confunde com enviar payload grande por `write`. Este capítulo prioriza contratos e não realiza benchmark de armazenamento [1][5].

## fsync, fdatasync, diretórios e consistência após falhas

No Linux, `fsync(fd)` solicita a sincronização dos dados modificados e metadados relevantes do arquivo, inclusive caches do dispositivo conforme o armazenamento informa ao sistema. `fdatasync` pode evitar sincronizar metadados dispensáveis para recuperar os dados do arquivo. Ambas podem falhar, e o código precisa checar resultados em vez de presumir uma fronteira de persistência sempre bem-sucedida [4].

Um detalhe frequentemente negligenciado: **fsync no arquivo não assegura necessariamente a persistência da entrada de diretório que lhe dá nome**. Para um arquivo criado ou renomeado sobreviver com o nome esperado a uma falha, frequentemente também é preciso sincronizar o diretório pai, com ordenação adequada ao filesystem. Renomear um arquivo temporário, isoladamente, não prova durabilidade do nome após crash. `fsync` também não corrige defeitos de hardware, sistemas remotos sem as mesmas garantias ou erros de transação na aplicação [4].

Uma falha do processo, do kernel e uma queda de energia são **modelos de falha diferentes**. O processo pode morrer depois que o kernel confirmou o recebimento de bytes ainda não sincronizados; falha geral do sistema pode perder páginas sujas do cache; o disco pode falhar independentemente. Journaling do filesystem e journaling de dados resolvem problemas específicos, diferentes da recuperação transacional do banco. Compare com [WAL e recuperação](/pt/topics/database-storage-wal/) [1][4].

## Modelo executável de snapshots e crash

Para tornar o limite verificável, definimos **dois snapshots de um arquivo já existente**: `visible` é o conteúdo que o programa lê; `synced` é a versão durável mais recente **no modelo**. Uma inserção muda só o estado visível; `crash` perde alterações não sincronizadas; `fsync` copia o visível para o snapshot durável. É um **modelo lógico**, não emulação de disco, journaling, cache real ou garantia de que falhas reais percam exatamente esses bytes [4].

~~~python
class CrashSnapshot:
    def __init__(self, original=b""):
        if type(original) is not bytes:
            raise ValueError("initial content must be bytes")
        self.visible = original
        self.synced = original

    def append(self, payload):
        if type(payload) is not bytes:
            raise ValueError("byte payload required")
        self.visible += payload

    def fsync(self):
        self.synced = self.visible

    def crash(self):
        self.visible = self.synced

    def read(self):
        return self.visible

    def durable_read(self):
        return self.synced

store = CrashSnapshot(b"A")
store.append(b"B")
assert store.read() == b"AB"
assert store.durable_read() == b"A"
store.crash()
assert store.read() == b"A"
store.append(b"C")
store.fsync()
store.append(b"D")
store.crash()
assert store.read() == store.durable_read() == b"AC"
~~~

O exemplo demonstra que B está visível, mas desaparece no primeiro crash didático; C é sincronizado e continua presente após uma falha posterior, enquanto D se perde. O modelo presume que `fsync` sempre conclui com sucesso e persiste **atomicamente todos os bytes** atuais. Sistemas reais podem executar writeback por páginas, registrar erros, exigir ordenação de metadados e apresentar persistência parcial. Essas possibilidades precisam de modelos próprios antes de alegar consistência real após falha.

O invariante é simples: `synced` muda apenas em `fsync`; `visible` muda em append e é restaurado por crash. É possível enumerar sequências curtas para testar esse contrato. Isso não comprova transações atômicas em disco, resistência a falha elétrica ou substituição segura de arquivo temporário.

## Falhas e implicações de projeto de filesystem

O caminho robusto de escrita precisa distinguir falha na abertura, escrita parcial, erro de sincronização, falha de rename, falha de sincronização do diretório e crash entre essas etapas. Tratamento de erros deve preservar o estado prometido ao usuário. Um sistema que confirma sucesso ao cliente **antes** da etapa de durabilidade exigida tem janela de perda diferente de outro que confirma apenas após sincronização bem-sucedida [4][5].

Interfaces POSIX também possuem implicações de concorrência. Descritores que compartilham uma descrição podem interferir no mesmo offset; `pread` e `pwrite` podem permitir acesso com posição explícita sem alterar o offset, respeitadas suas próprias ressalvas. Descrições abertas separadamente possuem cursores independentes, embora alterem bytes compartilhados. A demonstração Python é sequencial e **não** prova atomicidade de append simultâneo, segurança entre threads, locks, persistência em falhas ou ordenação de I/O.

Um sistema de arquivos ainda precisa implementar resolução de nomes, diretórios, alocação de inodes, mapeamento de blocos, gestão de espaço livre, cache, consistência e recuperação. O modelo deste capítulo para no limite de descritores e sync, deixando extents, journaling, arquivos copy-on-write e filas de dispositivos para estudos separados.

## Exercícios e verificação

1. Trace `open("note")`, `dup`, duas leituras de dois bytes e um segundo `open("note")`; registre **identidade da descrição**, offset e bytes do arquivo.
2. Feche um FD de uma dupla de duplicados e explique por que o outro continua funcionando; reabra para demonstrar **reutilização do número** sem compartilhar posição.
3. Execute `seek` além do EOF e escreva um byte: compare o preenchimento denso por zeros do modelo com buracos esparsos de arquivos reais.
4. Diferencie `fflush`, `write`, `fsync` e `fsync` do diretório quanto às propriedades de persistência, hipóteses e erros.
5. Explique por que `write` bem-sucedido pode transferir menos bytes do que solicitado e não garantir sobrevivência à queda de energia.
6. Enumere sequências de append, sync e crash; identifique os prefixos que sobrevivem no modelo e o que ele não expressa sobre escritas parcialmente persistidas.
7. Desenhe protocolo de substituição com arquivo temporário, sync de dados, rename e sync do diretório, explicitando intervalos de falha e hipóteses de filesystem.
8. Amplie o modelo com `pread`, sem alterar offset compartilhado, e verifique com oráculo independente para descritores válidos.
9. Liste pelo menos quatro características de descrições abertas reais ausentes da classe Python, como flags, identidade após rename, acesso e compartilhamento após fork.

**Continuação:** [inodes, blocos e journaling](/pt/topics/inode-directories-journaling-recovery/) aprofunda os metadados do sistema de arquivos; [processos e memória virtual](/pt/topics/processes-virtual-memory/) estabelece isolamento, e [WAL em bancos](/pt/topics/database-storage-wal/) trata recuperação transacional. Estes modelos de memória ilustram contratos observáveis, não comprovam confiabilidade ou desempenho de filesystems físicos [1][2][3][4][5].
