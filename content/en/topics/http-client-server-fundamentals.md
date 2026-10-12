---
id: http-client-server-fundamentals
title: "HTTP fundamentals: requests, responses, methods and client-server boundaries"
description: "Understand web requests, status codes, GET/POST/PUT/DELETE semantics and basic API responsibilities before advanced system design."
category: networking
difficulty: foundational
updated: 2026-10-12
prerequisites: [programming-control-flow-functions]
sources:
  - {title: "RFC 9110 — HTTP Semantics", url: "https://www.rfc-editor.org/rfc/rfc9110.html", kind: "IETF internet standard"}
  - {title: "RFC 9112 — HTTP/1.1", url: "https://www.rfc-editor.org/rfc/rfc9112.html", kind: "IETF internet standard"}
  - {title: "RFC 9111 — HTTP Caching", url: "https://www.rfc-editor.org/rfc/rfc9111.html", kind: "IETF internet standard"}
---
Web systems are easier to design when their basic unit is understood: a **client sends an HTTP request and receives an HTTP response**. A request asks a server to perform an operation on a target resource. The response indicates the result through status and representation metadata. HTTP defines the shared protocol semantics; the application defines its resources, data permissions and business rules [1]. Before discussing gateways, cache clusters or distributed transactions, an engineer should trace one complete request from user action to returned result.

## Client, server, URL and resource

A client may be a browser, mobile application or another service. A server receives requests on an exposed interface. A URL can contain scheme, host, path, query and optional fragment. The fragment is handled by the client and is not sent as part of the HTTP request target. In `https://example.org/notes/7?view=short`, the scheme is HTTPS, the host identifies the destination, the path identifies the target resource and the query modifies how that target is requested. HTTP method and target together specify the request semantics [1].

The server does not need to run one separate process per client. Many requests can share a service instance while maintaining distinct authentication and resource identities. A **stateless request handler** does not rely on a specific previous request arriving on the same process. This does not imply the application lacks state: persistent data, sessions and permissions can exist in storage or signed tokens.

## Anatomy of a request and a response

A conceptual HTTP/1.1 request begins with a method and request target, followed by headers and optionally a message body. For example, `GET /notes/7 HTTP/1.1` requests a resource. A `Host` field identifies the target authority in HTTP/1.1, and fields such as `Accept` describe representation preferences [2]. An HTTP response provides status, headers and possibly content. `Content-Type: application/json` describes the media type of the response body; it is not a guarantee that every declared JSON document is valid.

HTTP/2 and HTTP/3 use different wire framing, but application-level method and status semantics remain recognizable. The semantic contract does not depend on copying the HTTP/1.1 textual request line. Confusing protocol framing with the application operation can lead to misdesigned APIs. The system must also distinguish a transport failure, which may prevent a response, from an application response that successfully reports an error status [1][2].

## Methods: safety and idempotence

GET requests a representation and is a **safe method** in the sense that the caller is not asking for a state-changing effect. Servers may still log the request or update internal metrics. HEAD requests the metadata of a GET response without the response content. POST requests target-defined processing; it is not intrinsically idempotent. PUT requests that the target resource be created or replaced with the provided representation, and its intended effect is idempotent. DELETE removes the resource's association, and the method is also defined as idempotent in HTTP [1].

Idempotence concerns the intended **effect**, not identical response bytes or status codes. Repeating DELETE may produce 204 then 404 while the resource remains absent. Repeating PUT with the same body may generate audit logs each time and still be idempotent as defined. A POST can be made retry-safe through a domain-specific idempotency key, but this is an additional contract, not a property granted by its HTTP method name.

## Status codes and representation contracts

A 2xx status describes successful handling: 200 typically accompanies content, 201 indicates creation and 204 indicates no response content. A 4xx status reports a client-side condition such as malformed input (400), missing authorization credentials (401), forbidden operation (403), missing resource (404) or conflicting request (409). A 5xx status indicates a server-side failure while attempting to fulfill an otherwise potentially valid request [1].

These classes do not replace detailed API contracts. A successful 201 should mean the resource creation defined by the service actually occurred, not merely that work was silently scheduled. If asynchronous acceptance is intended, 202 is more appropriate with a way to track completion. A 404 can be a deliberate choice to avoid exposing the existence of resources inaccessible to a particular user, but authorization must still be checked server-side. Clients should not guess outcome from status alone when the network drops the response.

## Worked model: small CRUD semantics

The following code is a **pure in-memory model**, not a socket listener or HTTP parser. It deliberately omits authentication, concurrency, content negotiation, persistent storage and request size limits. Its purpose is to isolate method behavior from framework syntax. New notes are created by POST, an existing note is read by GET, replaced by PUT and removed by DELETE.

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

Notice that repeating POST creates two distinct resources because the service assigned a new ID each time. Repeating PUT with identical content leaves the resource with the same value. After DELETE, GET returns 404. The error for empty POST body is distinguishable from a missing note. The code is for understanding the protocol contract; a real implementation would separate URI parsing, authentication, authorization, validation, storage and response formatting.

## Trace one request through a simple architecture

A browser invokes GET for a note. Its networking stack resolves a host when needed, establishes a secure connection using the selected transport and TLS, and sends the HTTP request. A gateway or reverse proxy may forward it to an application process. The handler validates the request and actor, reads its storage and constructs the response. The path back may involve caches, proxies and connection reuse; a single exchange does not imply each request repeats every DNS or TLS step.

A cache may store certain responses under HTTP caching rules [3]. **Cache-control** directives help describe allowed reuse but do not authorize a user to read another user's private resource. Personalization, authentication and invalidation matter. Do not introduce a cache until you know whether staleness is acceptable and which responses are safe to share.

## Costs, common mistakes and exercises

Request latency is not simply CPU time. It includes possible name resolution, connection setup, network round trips, queueing, application computation and storage waits. A `GET` that returns quickly can still be wrong if it reads another tenant's record. A `POST` that times out can already have committed: retry behavior must follow the endpoint's specified contract. Avoid state-changing GET routes, which may be invoked by crawlers or prefetchers [1].

In the local model, dictionary access has expected O(1) time under ordinary hashing assumptions and stores O(n) notes for n created resources. This is not a web service throughput model, a storage durability argument or worst-case network latency bound.

## Exercises and verification

1. List method, path, body, status and response content for the entire example. Explain why two POSTs return distinct IDs.
2. Change the resource update to reject strings longer than 50 characters; show the failure without mutating existing data.
3. Explain how a DELETE may return 204 once and 404 later without violating HTTP idempotence.
4. Draw the responsibilities of client, reverse proxy, handler and database for GET /notes/7; identify where authorization belongs.
5. Distinguish missing HTTP response from a received 500 response, and explain why retry safety cannot be inferred from transport alone.
6. Decide whether a cached personal note response could safely be shared between authenticated users. Justify using the cache and authorization contracts [3].

Continue with [network foundations](/en/topics/network-protocols/), [API contracts](/en/topics/api-contracts-pagination/) and [system design process](/en/topics/system-design-process/).