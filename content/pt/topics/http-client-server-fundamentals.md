---
id: http-client-server-fundamentals
title: "Fundamentos de HTTP: cliente, servidor, requisições e respostas"
description: "Entenda métodos, códigos de status, semântica de GET/POST/PUT/DELETE e responsabilidades de APIs antes de system design."
category: networking
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions]
sources:
  - {title: "RFC 9110 — HTTP Semantics", url: "https://www.rfc-editor.org/rfc/rfc9110.html", kind: "IETF internet standard"}
  - {title: "RFC 9112 — HTTP/1.1", url: "https://www.rfc-editor.org/rfc/rfc9112.html", kind: "IETF internet standard"}
  - {title: "RFC 9111 — HTTP Caching", url: "https://www.rfc-editor.org/rfc/rfc9111.html", kind: "IETF internet standard"}
---
Projetar sistemas web fica mais simples quando se compreende a unidade básica: **um cliente envia uma requisição HTTP e recebe uma resposta HTTP**. A requisição solicita uma operação sobre um recurso-alvo. A resposta informa o resultado por status e metadados de representação. O HTTP define as semânticas compartilhadas; a aplicação define recursos, permissões e regras de negócio [1]. Antes de gateways, clusters de cache e transações distribuídas, o engenheiro precisa rastrear uma requisição do clique até o resultado.

## Cliente, servidor, URL e recurso

O cliente pode ser navegador, aplicativo móvel ou outro serviço. O servidor recebe requisições numa interface exposta. A URL pode incluir esquema, host, caminho, query e fragmento opcional. O fragmento é processado pelo cliente e não integra o alvo transmitido na requisição HTTP. Em `https://example.org/notes/7?view=short`, o esquema é HTTPS, o host indica destino, o caminho identifica recurso e a query altera a seleção solicitada. Método e alvo determinam conjuntamente a semântica da operação [1].

O servidor não precisa executar um processo distinto por usuário. Requisições podem compartilhar uma instância e ainda possuir identidades de autenticação e recursos independentes. Um **handler sem estado local entre requisições** não depende de que o mesmo processo receba todas as chamadas de um usuário. Isso não significa aplicação sem dados persistidos: estado, sessões e permissões podem existir em armazenamento ou tokens assinados.

## Estrutura de requisição e resposta

Uma requisição HTTP/1.1 conceitual começa com método e alvo, seguidos de cabeçalhos e eventualmente corpo. Por exemplo, `GET /notes/7 HTTP/1.1` solicita um recurso. O campo `Host` identifica autoridade no HTTP/1.1 e `Accept` expressa preferências de formato [2]. A resposta contém status, cabeçalhos e talvez conteúdo. `Content-Type: application/json` declara o tipo de mídia do corpo; não prova que todo conteúdo declarado JSON seja válido.

HTTP/2 e HTTP/3 utilizam enquadramentos diferentes na rede, mas preservam conceitos de método e status da aplicação. O contrato semântico não exige copiar literalmente a linha textual do HTTP/1.1. Confundir enquadramento do protocolo com operação de aplicação gera APIs equivocadas. Também é preciso distinguir erro de transporte, que pode impedir a resposta, de resposta HTTP recebida com código de erro [1][2].

## Métodos, segurança e idempotência

GET solicita representação e é considerado método **seguro**, pois o cliente não pede alteração de estado. O servidor ainda pode registrar logs e métricas internas. HEAD solicita metadados correspondentes a GET sem transferir seu conteúdo. POST solicita processamento definido pelo recurso e não é idempotente por natureza. PUT solicita criar ou substituir o recurso indicado pela representação fornecida e possui efeito pretendido idempotente. DELETE remove associação do recurso e também possui semântica idempotente [1].

Idempotência descreve o **efeito pretendido**, não igualdade exata de status ou bytes da resposta. Repetir DELETE pode gerar 204 e depois 404, enquanto o recurso continua ausente. Repetir PUT com o mesmo corpo pode produzir novos registros de auditoria e ainda atender à definição de idempotência. POST pode receber contrato adicional de chave idempotente para repetição segura; isso não decorre automaticamente do nome do método.

## Códigos de status e contratos de representação

Status 2xx indica tratamento bem-sucedido: 200 frequentemente inclui conteúdo, 201 informa criação e 204 indica ausência de conteúdo na resposta. Status 4xx comunica condição do cliente, como entrada malformada (400), credenciais ausentes ou inválidas (401), operação proibida (403), recurso ausente (404) ou conflito (409). Status 5xx aponta falha do servidor ao tentar atender uma solicitação potencialmente válida [1].

Essas classes não substituem a especificação da API. Uma resposta 201 deve refletir a criação definida pelo serviço, não trabalho que apenas ficou agendado silenciosamente. Aceitação assíncrona normalmente pode usar 202 e oferecer consulta de acompanhamento. Retornar 404 para ocultar a existência de recurso proibido pode ser política válida, mas a autorização precisa ser verificada no servidor. Um cliente não deve presumir o resultado de uma operação se a rede perdeu a resposta.

## Modelo executável de operações CRUD

O código abaixo é um **modelo em memória**, não servidor de sockets nem parser HTTP. Não contempla autenticação, concorrência, negociação de conteúdo, persistência ou limites de tamanho. Sua finalidade é estudar o comportamento dos métodos sem sintaxe de frameworks. POST cria nota, GET consulta, PUT substitui e DELETE remove.

~~~python
class NotesService:
    """An in-memory illustration of HTTP method semantics, not an HTTP server."""
    def __init__(self):
        self.notes = {}
        self.next_id = 1

    def handle(self, method, path, body=None):
        if method == "POST" and path == "/notes":
            if not isinstance(body, str) or not body:
                return (400, None)
            note_id = self.next_id
            self.next_id += 1
            self.notes[note_id] = body
            return (201, {"id": note_id, "text": body})

        if not path.startswith("/notes/"):
            return (404, None)
        suffix = path[len("/notes/"):]
        if not suffix.isdecimal() or int(suffix) < 1:
            return (404, None)
        note_id = int(suffix)

        if method == "GET":
            if note_id not in self.notes:
                return (404, None)
            return (200, {"id": note_id, "text": self.notes[note_id]})

        if method == "PUT":
            if note_id not in self.notes:
                return (404, None)
            if not isinstance(body, str) or not body:
                return (400, None)
            self.notes[note_id] = body
            return (200, {"id": note_id, "text": body})

        if method == "DELETE":
            if note_id not in self.notes:
                return (404, None)
            del self.notes[note_id]
            return (204, None)

        return (405, None)

service = NotesService()
status, first = service.handle("POST", "/notes", "Draft")
assert status == 201 and first["id"] == 1
status, second = service.handle("POST", "/notes", "Draft")
assert status == 201 and second["id"] == 2
assert service.handle("GET", "/notes/1")[1]["text"] == "Draft"
assert service.handle("PUT", "/notes/1", "Final")[0] == 200
assert service.handle("PUT", "/notes/1", "Final")[0] == 200
assert service.handle("GET", "/notes/1")[1]["text"] == "Final"
assert service.handle("DELETE", "/notes/1") == (204, None)
assert service.handle("GET", "/notes/1") == (404, None)
assert service.handle("POST", "/notes", "") == (400, None)
~~~

Repetir POST cria dois recursos diferentes porque o serviço atribui novo identificador em cada chamada. Repetir PUT com conteúdo idêntico mantém o mesmo valor armazenado. Depois de DELETE, GET devolve 404. Corpo vazio de POST é diferente de nota inexistente. Na implementação real, seriam separadas análise de URL, autenticação, autorização, validação, armazenamento e formatação de resposta.

## Rastreie uma requisição pela arquitetura mínima

Um navegador pede GET para uma nota. Sua pilha de rede resolve o host quando necessário, estabelece conexão segura com transporte escolhido e TLS, e transmite a requisição. Um gateway ou proxy reverso pode encaminhá-la ao processo de aplicação. O handler valida requisição e identidade do ator, consulta armazenamento e monta resposta. No caminho podem existir caches e conexões reaproveitadas; não se presume que cada requisição repita todas as etapas DNS e TLS.

Um cache pode guardar certas respostas de acordo com as regras de caching HTTP [3]. Diretivas de **Cache-Control** ajudam a especificar reutilização permitida, mas não autorizam que outro usuário leia recurso privado. Personalização, autenticação e invalidação precisam de projeto próprio. Acrescentar cache só faz sentido depois de definir tolerância a dados defasados e quais respostas podem ser compartilhadas.

## Custos, falhas comuns e verificação

Latência não é somente tempo de CPU. Pode incluir resolução de nome, conexão, viagens de rede, filas, processamento na aplicação e espera por armazenamento. GET rápido também pode estar incorreto se expõe dado de outro tenant. POST pode confirmar efeito e perder a resposta no timeout; retentativas obedecem ao contrato do endpoint. Evite rotas GET que provocam alterações de negócio, pois crawlers e mecanismos de prefetch podem invocá-las [1].

No modelo local, operações do dicionário têm custo esperado O(1) sob hipóteses comuns de hashing, e n notas ocupam O(n) estado. Isso não permite deduzir vazão HTTP, durabilidade do armazenamento ou limite de latência de rede.

## Exercícios e verificação

1. Liste método, caminho, corpo, status e retorno em cada operação do exemplo. Explique os IDs distintos dos dois POSTs.
2. Faça PUT rejeitar textos com mais de 50 caracteres; teste que a rejeição não altera dados existentes.
3. Explique por que um DELETE pode devolver 204 e depois 404 sem violar idempotência.
4. Desenhe responsabilidades de cliente, proxy reverso, handler e banco para GET /notes/7; indique onde ocorre autorização.
5. Diferencie não receber resposta HTTP de receber resposta 500, justificando por que transporte sozinho não define retentativa segura.
6. Avalie se cache de nota privada pode ser compartilhado entre usuários autenticados, considerando autorização e política de caching [3].

Continue com [fundamentos de redes](/pt/topics/network-protocols/), [contratos de API](/pt/topics/api-contracts-pagination/) e [método de system design](/pt/topics/system-design-process/).