---
id: api-contracts-pagination
title: "Contratos HTTP: paginação, idempotência e atualizações condicionais"
description: "Projete recursos HTTP, paginação por cursor, ETags, comandos idempotentes, erros padronizados e evolução compatível de APIs."
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites: [network-protocols, api-reliability, transactional-indexing-isolation]
sources:
  - {title: "RFC 9110 — HTTP Semantics", url: "https://www.rfc-editor.org/rfc/rfc9110.html", kind: "IETF standard"}
  - {title: "AWS Builders Library — Timeouts, retries and backoff with jitter", url: "https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/", kind: "engineering source"}
  - {title: "RFC 9457 — Problem Details for HTTP APIs", url: "https://www.rfc-editor.org/rfc/rfc9457.html", kind: "IETF standard"}
---
Contrato de API é o **protocolo compartilhado por clientes e serviço**, não apenas lista de URLs. Define recursos, autenticação, restrições, efeitos bem-sucedidos, erros, cache, paginação, compatibilidade e conduta do cliente quando uma resposta desaparece. HTTP estabelece a semântica de seus métodos e status; a aplicação precisa especificar seu significado de negócio sem contrariar essas regras [1].

## Modele recursos e permissões antes das rotas

Considere API de notas privadas: cada nota possui identificador imutável, proprietário, criação e texto. Um usuário cria, lista e lê somente suas notas. Clientes não podem enviar owner_id para assumir identidade alheia; a propriedade deve vir da identidade autenticada no servidor. A autorização é **por objeto**, mesmo com bearer token válido. Decida se nota inexistente ou proibida deve ter resposta indistinguível para não revelar identificadores.

Uma interface candidata contém GET /v1/notes/{id}, GET /v1/notes?limit=...&cursor=..., POST /v1/notes e PUT /v1/notes/{id} quando substituição integral for suportada. Nome de rota importa menos que contrato coerente. Defina tamanho máximo do texto UTF-8, media types, limite de página, ordenação, deadlines e política de acesso, permitindo clientes independentes.

## GET, POST, PUT e idempotência HTTP

GET recupera recurso e segue semântica de leitura/safety do HTTP. PUT pede criação ou substituição de recurso endereçado diretamente e é um **método idempotente**: repetir a mesma requisição tem o mesmo efeito pretendido que executá-la uma vez. POST pede processamento segundo semântica do recurso de destino e não é genericamente idempotente. Até método idempotente pode gerar logs ou efeitos internos a cada chamada; a propriedade se refere ao efeito pretendido sobre o recurso [1].

Para criação concluída, devolva **201 Created** com identificador/Location. Quando um comando foi apenas aceito para processamento posterior, **202 Accepted** pode fazer sentido, mas exponha status durável e não afirme conclusão. DELETE pode ser idempotente mesmo que repetição retorne 404 após exclusão inicial; idempotência não exige status idêntico em toda resposta.

## Resposta ambígua e chave de idempotência

O servidor pode confirmar uma escrita e perder a conexão antes de enviar resposta. O timeout do cliente **não** demonstra rollback. Se o cliente repetir POST sem identidade de operação estável, surgem duplicatas. Defina cabeçalho `Idempotency-Key` com escopo (por exemplo usuário autenticado e endpoint), validade e fingerprint canônico da requisição. Persista chave, fingerprint e resultado **atomicamente** com o efeito de negócio. Repetição igual recupera o resultado lógico anterior; chave reutilizada com payload diferente é rejeitada conforme o contrato.

Dicionário local de processo não basta com múltiplas réplicas ou reinicialização. Unicidade precisa existir na persistência e comportamento sob corrida precisa ser definido. Se houver cobrança externa, idempotência local é somente parte da solução: garantias e reconciliação do provedor determinam se pode haver cobrança duplicada [2].

## Paginação offset versus keyset

Paginação por offset usa LIMIT e OFFSET. Numa lista mutável, novas inserções deslocam posições e podem produzir duplicatas ou omissões entre páginas. Offsets grandes podem ainda exigir varredura ou descarte de muitas linhas. **Keyset/cursor pagination** guarda a última chave de ordenação estável e consulta itens posteriores naquela ordem. Um cursor é estado de continuação, **não** credencial ou prova de autorização.

![Cursor composto separa páginas numa ordem decrescente estável.](/diagrams/api-keyset-pagination.svg)

Para notas ordenadas por (created_at DESC, id DESC), a página seguinte filtra `(created_at,id) < (:last_time,:last_id)` sob ordem lexicográfica compatível. ID de desempate é necessário porque notas podem compartilhar timestamp. Use índice incluindo proprietário e chaves ordenadas. Toda consulta deve filtrar o proprietário autenticado; decodificar cursor não permite acessar registros de outra pessoa.

Cursor keyset não garante, sozinho, um snapshot perfeitamente congelado entre requisições. Itens inseridos **antes** do cursor podem deixar de aparecer nas páginas seguintes por definição; itens antigos podem sofrer edição ou remoção. Caso o produto exija consistência de snapshot, projete leitura versionada ou snapshot com janela de retenção e custo explícitos.

## Demonstre cursores opacos com integridade

O exemplo Python encapsula proprietário, timestamp e ID num token URL-safe, autenticando o payload com HMAC. Demonstra proteção contra **adulteração**, não subsistema pronto para produção. O segredo de uma implantação deve ser aleatório, guardado e rotacionado com identificação da chave, nunca fixado no código; expiração, tamanho e regras de codificação também precisam ser definidos.

~~~python
import base64
import hashlib
import hmac
import json

CHAVE_EXEMPLO = b"example-only-key-do-not-use-in-production"

def codificar_b64(dados):
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")

def decodificar_b64(texto):
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))

def criar_cursor(dono, instante, id_nota):
    payload = json.dumps({"v": 1, "owner": dono, "time": instante,
                          "id": id_nota}, sort_keys=True, separators=(",", ":")).encode()
    assinatura = hmac.new(CHAVE_EXEMPLO, payload, hashlib.sha256).digest()
    return codificar_b64(payload) + "." + codificar_b64(assinatura)

def ler_cursor(token, dono_esperado):
    try:
        codificado, assinatura = token.split(".")
        payload = decodificar_b64(codificado)
        esperado = hmac.new(CHAVE_EXEMPLO, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(esperado, decodificar_b64(assinatura)):
            raise ValueError("assinatura invalida")
        dados = json.loads(payload)
        if dados["v"] != 1 or dados["owner"] != dono_esperado:
            raise ValueError("escopo invalido")
        if not isinstance(dados["time"], int) or not isinstance(dados["id"], int):
            raise ValueError("posicao invalida")
        return (dados["time"], dados["id"])
    except (KeyError, ValueError, TypeError, UnicodeError) as erro:
        raise ValueError("cursor invalido") from erro

token = criar_cursor("alice", 1700000100, 42)
assert ler_cursor(token, "alice") == (1700000100, 42)
for dono_ruim in ("bob", ""):
    try:
        ler_cursor(token, dono_ruim)
        assert False
    except ValueError:
        pass
try:
    ler_cursor(token[:-1] + ("A" if token[-1] != "A" else "B"), "alice")
    assert False
except ValueError:
    pass
~~~

O modelo adota timestamps inteiros de época e IDs inteiros; API real precisa de limites de valores e rate limiting. Assinatura de payload base64 não oferece criptografia: clientes podem decodificar os campos, portanto não insira segredos. A autorização deve ser conferida novamente em cada objeto retornado.

## ETags e atualizações concorrentes

Dois editores podem receber a mesma representação, alterar o texto e executar PUT em sequência. Sem precondição, a escrita tardia sobrescreve silenciosamente a anterior. Um **ETag** identifica uma versão da representação. Com `If-Match: "version"`, o servidor só aplica mudança quando o validador atual corresponde; caso contrário responde **412 Precondition Failed** [1]. A comparação e a escrita devem ocorrer atomicamente na autoridade, não como leituras separadas inseguras.

Controle otimista evita *lost update* nas condições definidas, mas não prova compatibilidade semântica entre duas intenções humanas. Em PATCH, defina media type e semântica da modificação, sem presumir que qualquer corpo PATCH significa substituição parcial de JSON.

## Erros, status e política de retry

A RFC 9457 define representação de **problem details** com type, title, status e detail, mais extensões [3]. Use tipo estável e não exponha credenciais, identificadores privados ou stack traces. O status HTTP informa categoria; códigos de domínio permitem decisões de máquina. A resposta precisa indicar condições em que repetir é apropriado.

| Condição | Código exemplo | Ação do cliente |
| --- | --- | --- |
| Entrada inválida | 400 ou 422 conforme contrato | Corrigir dados |
| Autenticação ausente/inválida | 401 | Obter credenciais |
| Identidade válida sem permissão | 403 ou 404 para privacidade | Não repetir sem mudança |
| Criação durável | 201 | Consultar Location/ID |
| Comando aceito assincronamente | 202 | Consultar status |
| Chave de idempotência com corpo conflitante | 409 conforme contrato | Nova operação válida |
| Validador If-Match falhou | 412 | Reconsultar e reconciliar |
| Limite de requisições atingido | 429 | Observar Retry-After se existir |
| Erro temporário de servidor | 503 | Retry limitado sob orçamento |

Erro 5xx não implica que POST deixou de produzir efeitos. Backoff com jitter e tentativas limitadas só é apropriado quando a repetição é segura ou protegida por idempotência durável [2]. Cliente deve respeitar deadline total para não ampliar indefinidamente a sobrecarga.

## Evolução e compatibilidade

Mudanças podem ser **sintáticas**, como nomes de campos, ou **semânticas**, como o momento em que sucesso passa a significar commit. Adicionar campos opcionais na resposta pode preservar compatibilidade em clientes tolerantes; alterar significado de campo obrigatório ou transformar comando síncrono em assíncrono pode não preservar. Verifique contratos entre consumidores e provedores em vez de apenas mudar /v1 para /v2.

Identificador de versão não resolve compatibilidade automaticamente. Mantenha política de depreciação, taxonomia de erros, plano de migração de esquema e testes. Revise autorização e paginação ao adicionar índices, caches ou réplicas, pois melhorias arquiteturais podem alterar frescor e segurança.

## Exercícios e verificação

1. Explique como retry de POST após timeout pode duplicar operações, mesmo sem receber 201.
2. Crie duas notas com timestamps iguais e mostre a ambiguidade de um cursor somente temporal.
3. Explique por que cursor HMAC ainda exige autorização por proprietário a cada chamada.
4. Apresente intercalação de duas escritas sem If-Match e como condição atômica do ETag impede sobrescrita silenciosa.
5. Defina respostas para criação válida, leitura sem permissão, atualização com versão obsoleta e requisição limitada.

**Capítulos relacionados:** [APIs confiáveis](/pt/topics/api-reliability/) aborda retries; [índices transacionais](/pt/topics/transactional-indexing-isolation/) trata concorrência; [método de System Design](/pt/topics/system-design-process/) conecta contrato e arquitetura.
