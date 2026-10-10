---
id: cpp17-concurrency-implementation
title: "Oficina de C++17: token bucket thread-safe e compilação no CI"
description: "Construa token bucket em C++17 com relógio monotônico injetado, mutex, invariantes, validação e testes compilados no CI."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [maintainable-implementation-workshop, concurrency-synchronization]
sources:
  - {title: "C++ reference — steady_clock", url: "https://en.cppreference.com/w/cpp/chrono/steady_clock.html", kind: "language reference"}
  - {title: "C++ reference — mutex", url: "https://en.cppreference.com/w/cpp/thread/mutex.html", kind: "language reference"}
  - {title: "Amazon API Gateway — throttling", url: "https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html", kind: "official product documentation"}
---
Correção e manutenção não se transferem automaticamente de Python para C++. O mesmo requisito de token bucket precisa tratar **tipos, constness, tempos de vida, relógio monotônico, limites de ponto flutuante, mutex e data races reais**. Esta oficina implementa a versão C++17 do limitador publicado anteriormente e compila seus testes num gate específico de CI. O arquivo completo está em [token_bucket.cpp](https://github.com/christianrss/manual/blob/main/examples/cpp/token_bucket.cpp); a suíte do repositório compila com C++17 e suporte a pthread.

## Reescreva o contrato sem depender da linguagem

O bucket possui capacidade C, taxa de reposição r tokens/s e saldo T com invariante **0 ≤ T ≤ C**. Começa cheio. Em uma chamada no tempo monotônico t, calcula segundos transcorridos, repõe até min(C,T+rΔt) e aceita custo positivo finito somente se houver saldo. Rejeição ainda atualiza instante interno e mantém créditos repostos. O contrato descreve comportamento, não exige alguma hierarquia de classes.

A versão Python recebia um relógio como função; C++ também deve aceitar injeção para testar tempo sem `sleep`. Na produção, escolha fonte própria para intervalos, não relógio civil sujeito a correções. `std::chrono::steady_clock` é próprio para medições monotônicas [1]. Seus time points não são datas, e a duração precisa ser convertida explicitamente para segundos.

## Conecte decisões de design aos recursos C++17

O núcleo da implementação fica assim; a [fonte completa](https://github.com/christianrss/manual/blob/main/examples/cpp/token_bucket.cpp) inclui construtor, campos privados e assertions executáveis.

~~~cpp
// Dentro de TokenBucket::allow(double cost):
std::lock_guard<std::mutex> guard(mu_);
const auto next = now_();
const double seconds =
    std::chrono::duration<double>(next - last_).count();
if (seconds < 0) throw std::logic_error("clock moved backwards");
tokens_ = std::min(capacity_, tokens_ + seconds * rate_);
last_ = next;
if (tokens_ < cost) return false;
tokens_ -= cost;
return true;
~~~

O lock engloba **leitura, reposição, comparação e subtração numa região crítica**. Proteger apenas o decremento permitiria corrida entre leitura e escrita. `std::mutex` sincroniza threads usando o mesmo objeto, não processos independentes ou bancos remotos. No modelo de memória C++, acessos conflitantes não atômicos sem sincronização produzem comportamento indefinido, não apenas uma resposta ocasionalmente errada [2].

## Tipos, validação e exceções

Valide capacidade, taxa e custo positivos e finitos com `std::isfinite`, rejeitando NaN e infinito antes dos cálculos. Ao contrário da oficina Python, esta versão C++ aceita custos fracionários positivos. É uma **diferença explícita de contrato**, não equivalência acidental: o exemplo Python exige custos inteiros. Construtor e `allow` podem lançar exceções para entradas inválidas; o adaptador precisa de política para tratá-las. Retornar false fica reservado a operação válida sem créditos suficientes.

A função injetada `Now` deve continuar válida durante a vida do objeto. Lambda que captura relógio manual por referência só é segura quando esse relógio vive mais que o bucket. O exemplo define o relógio antes do bucket, fazendo o bucket ser destruído primeiro. Capturar referência de variável local temporária e chamá-la depois seria erro de lifetime que as semânticas de referência Python não reproduzem da mesma forma.

## Propriedade de estado e cópia de objetos

A classe contém mutex e é propositalmente **não copiável** por seus membros especiais padrão. Copiar saldo sem controle coerente poderia duplicar cota e violar limite global. Cada bucket possui seus próprios `last_` e `tokens_`. Uma coleção pode manter ponteiros/referências, mas a política de identidade e tempo de vida precisa estar definida.

O mutex é privado para expor apenas uma **decisão atômica**, não métodos separados de leitura e decremento. Uma interface `get_tokens` seguida de `spend` induziria a unsafe read-then-act, mesmo que cada chamada isolada usasse lock.

## Testes de relógio e concorrência

O programa usa `steady_clock::time_point` manual. Gasta dois tokens, avança 500 ms duas vezes, confirma que reposição parcial não autoriza custo inteiro e então permite operação após completar reposição. Também avança 24 horas para mostrar saturação da capacidade. Um segundo teste executa doze `std::thread` contra bucket de três tokens iniciais e taxa de reposição desprezível: exatamente três chamadas devem ter sucesso.

O teste com threads **exercita** sincronização, mas não prova todas as intercalações. O escalonador pode executar quase tudo sequencialmente. A justificativa do invariante vem da exclusão mútua e da aritmética, não de um assert que passou uma vez. Quando ambiente suportar, use ThreadSanitizer e interprete relatórios com cuidado [2].

## CI precisa compilar a fonte verdadeira

Um trecho `cpp` no Markdown não é executado pelo testador atual de blocos Python. Esta edição adiciona teste no repositório que compila o **arquivo C++ real** com `g++ -std=c++17 -Wall -Wextra -Werror -pthread`, executa as assertions habilitadas e falha o pipeline se compilação ou execução não der certo. Aprovação significa que passou no compilador e runner presentes, não portabilidade para todos os sistemas.

O programa não usa bibliotecas externas nem credenciais. O compilador é requisito no runner Linux; se faltar, o CI falha em vez de ignorar a validação. Para executar localmente, a partir da raiz:

~~~text
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pthread examples/cpp/token_bucket.cpp -o /tmp/manual-token-bucket
/tmp/manual-token-bucket
~~~

## Complexidade, números e limites operacionais

Uma decisão `allow` usa O(1) operações aritméticas de ponto flutuante fixo e O(1) estado por bucket. Sob contenção, o mutex aumenta fila e latência. Um servidor multitenant com milhões de buckets inativos precisa de descarte, orçamento de memória e chave estável; manter todos indefinidamente consome O(número de tenants observados), não memória constante global.

Esse bucket não sincroniza várias réplicas e perde estado ao reiniciar. Cota global precisa de autoridade com transição atômica (por exemplo banco ou script correto na camada de dados), mais semântica de falha em partições de rede [3]. Mutex local não resolve cota distribuída.

## Contraexemplos e critérios de revisão

| Erro | Efeito | Contrato mais seguro |
| --- | --- | --- |
| Relógio civil para intervalos | Ajustes para trás/frente | `steady_clock` |
| Lock somente no desconto | Corrida em reposição e leitura | Proteger decisão toda |
| Aceitar NaN como custo | Comparações podem ser contornadas | Números positivos finitos |
| Copiar estado em outro bucket | Duplica cota | Autoridade e identidade estáveis |
| Bucket por réplica de API | Limite agregado multiplica | Armazenamento coordenado |
| Não compilar C++ do artigo | Exemplo pode nem compilar | Teste de compilador no CI |

## Exercícios e verificação

1. Por que `std::lock_guard` precisa cobrir reposição e consumo?
2. Modifique a fonte para microtokens inteiros e discuta precisão e overflow.
3. Em ambiente compatível, execute `-fsanitize=thread`; remova mutex propositalmente e analise a corrida detectada.
4. Explique o tempo de vida exigido da lambda que captura relógio manual por referência.
5. Desenhe versão distribuída e diga o que acontece quando a autoridade central fica indisponível.

**Capítulos relacionados:** [Implementação Python](/pt/topics/maintainable-implementation-workshop/), [ordem de memória](/pt/topics/memory-ordering-atomics/), [oficina de concorrência](/pt/topics/concurrency-interview-workshop/) e [rate limiting](/pt/topics/rate-limiting/) oferecem fundamentos.
