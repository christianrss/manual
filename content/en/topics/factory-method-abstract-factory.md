---
id: factory-method-abstract-factory
title: "Creational patterns: Factory Method, Abstract Factory and simple factories"
description: "Compare constructor selection, overridable creation hooks and compatible object families with tested export pipelines and explicit failures."
category: engineering
difficulty: intermediate
updated: 2026-10-12
prerequisites: [design-pattern-families, domain-modeling-aggregates-invariants]
sources:
  - {title: "Refactoring.Guru — Factory Method", url: "https://refactoring.guru/design-patterns/factory-method", kind: "technical pattern reference"}
  - {title: "Refactoring.Guru — Abstract Factory", url: "https://refactoring.guru/design-patterns/abstract-factory", kind: "technical pattern reference"}
  - {title: "Python documentation — csv", url: "https://docs.python.org/3/library/csv.html", kind: "official language documentation"}
---
A factory is any construction mechanism that a program names as such; the name alone does not identify a GoF design pattern. A conditional function that returns one of two classes is a **simple factory**. Factory Method changes which product a creator produces by letting subclasses override a method while the creator retains shared workflow logic [1]. Abstract Factory provides a family of related products which must be chosen together [2]. This difference matters when evaluating code in interviews and production reviews.

## Start from actual variation and a contract

A report export application produces JSON or CSV. Both variants accept rows, validate their fields and produce text. A row contains a nonempty name and a nonnegative integer count; boolean counts are not valid. Some callers choose a format from a request parameter, while scheduled export jobs have a fixed format. Another requirement is to return a matching filename extension, so a JSON body accidentally labeled .csv constitutes a compatibility defect.

The two renderers preserve equivalent information, not identical byte representation. The built-in CSV writer handles delimiters, embedded quotation marks and newlines according to the dialect selected; joining strings with commas is not a safe substitute [3]. The example does not write files or send HTTP responses. Therefore it does not establish persistence, authorization or protection from untrusted filesystem paths.

## Simple factory versus Factory Method

A simple factory can map a format string to a constructor and fail on unknown formats. It moves creation decisions to one place, making the caller simpler. But there is no subclass customizing an overridable creation hook, so calling it the classic Factory Method would be imprecise. With two fixed products a simple conditional might be even clearer.

The genuine Factory Method example below has an abstract ExportJob which owns the validation-and-render workflow. Concrete jobs implement make_renderer, replacing only construction. This uses a creator class and a product interface; the product contract is a render method returning text [1]. Its weakness is inheritance and an extra class for each format. Constructor injection of an existing renderer can be better when extension through subclasses is not otherwise useful.

~~~python
import csv
import io
import json
from abc import ABC, abstractmethod

def validated(rows):
    if not isinstance(rows, (tuple, list)):
        raise ValueError("rows must be a sequence")
    result = []
    for row in rows:
        if (not isinstance(row, tuple) or len(row) != 2
                or not isinstance(row[0], str) or not row[0].strip()
                or type(row[1]) is not int or row[1] < 0):
            raise ValueError("invalid row")
        result.append(row)
    return result

class CsvRenderer:
    def render(self, rows):
        target = io.StringIO(newline="")
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(("name", "count"))
        writer.writerows(rows)
        return target.getvalue()

class JsonRenderer:
    def render(self, rows):
        return json.dumps([{"name": name, "count": count}
                           for name, count in rows], ensure_ascii=False)

class ExportJob(ABC):
    @abstractmethod
    def make_renderer(self):
        raise NotImplementedError
    def run(self, rows):
        return self.make_renderer().render(validated(rows))

class CsvExport(ExportJob):
    def make_renderer(self):
        return CsvRenderer()

class JsonExport(ExportJob):
    def make_renderer(self):
        return JsonRenderer()

def simple_factory(kind):
    choices = {"csv": CsvRenderer, "json": JsonRenderer}
    if kind not in choices:
        raise ValueError("unsupported format")
    return choices[kind]()

rows = [("Ada", 2), ("Grace, Hopper", 1)]
assert '"Grace, Hopper",1' in CsvExport().run(rows)
assert json.loads(JsonExport().run(rows))[1]["name"] == "Grace, Hopper"
assert simple_factory("csv").render(validated(rows)) == CsvExport().run(rows)
try:
    CsvExport().run([("invalid", True)])
except ValueError:
    pass
else:
    raise AssertionError("bool count accepted")
~~~

For n rows with bounded field lengths, validation inspects O(n) entries. Rendering work is at least proportional to the total emitted characters, which can exceed n by an arbitrary factor when names are long. The validated list and returned output consume memory, so neither operation is constant-space. Direct use of a renderer bypasses ExportJob validation. The renderer is a lower-level component; the public export entry point must enforce its documented input contract.

## Abstract Factory controls a family

Suppose output packaging also chooses an extension policy. This introduces two related products: renderer and naming strategy. If the caller independently creates JsonRenderer and CsvName, a syntactically valid package can mislead the consumer. A family object supplies both from the same variant [2]. The client chooses CsvFamily or JsonFamily, then asks for the two components without knowing concrete implementation names.

~~~python
class CsvName:
    def filename(self, base):
        return base + ".csv"

class JsonName:
    def filename(self, base):
        return base + ".json"

class CsvFamily:
    def renderer(self):
        return CsvRenderer()
    def naming(self):
        return CsvName()

class JsonFamily:
    def renderer(self):
        return JsonRenderer()
    def naming(self):
        return JsonName()

def export_package(family, rows, base):
    if not isinstance(base, str) or not base.isidentifier():
        raise ValueError("invalid base filename")
    data = validated(rows)
    return family.naming().filename(base), family.renderer().render(data)

assert export_package(CsvFamily(), rows, "quarter")[0] == "quarter.csv"
name, data = export_package(JsonFamily(), rows, "quarter")
assert name == "quarter.json"
assert json.loads(data)[0] == {"name": "Ada", "count": 2}
try:
    export_package(CsvFamily(), rows, "../quarter")
except ValueError:
    pass
else:
    raise AssertionError("unsafe filename accepted")
~~~

The package function accepts only identifiers as file bases, deliberately rejecting paths and separators. This is a narrow input contract, **not** a general filename sanitizer. The family still cannot prevent code elsewhere from combining mismatched objects. At an HTTP or storage boundary, validate content type, extension, object key, authorization and download behavior independently.

## Decision table and dependency implications

| Changing requirement | Prefer | Cost to recognize |
| --- | --- | --- |
| A fixed format selected by string | Simple factory or conditional | A registry still needs validation |
| A shared creator workflow with overridable construction | Factory Method | Subclass hierarchy and indirect behavior |
| Two or more related products must be compatible | Abstract Factory | Another layer and family matrix |
| One complex product built through optional validated steps | Builder | Mutable intermediate state |
| Dependency fixed at application startup | Constructor injection | Explicit composition at startup |

Factory Method is driven by a changing creation hook inside a reusable workflow. Abstract Factory is driven by compatible **families** of objects. Builder controls the **stages** that produce a single finished value. A service locator silently constructing arbitrary dependencies is not equivalent to dependency injection: it can conceal the true dependencies of business policies. Choose the smallest abstraction that constrains an actual error [1][2].

## Failure semantics and counterexamples

If an unknown format is silently replaced by CSV, a customer expecting JSON may receive unparsable data. The factory should reject it rather than manufacture success. If a renderer makes a network call, creating it successfully does not prove the call will complete; timeout, retry and resource disposal need separate contracts. If a format requires different input semantics, forcing all products to share one interface may violate behavioral substitutability. A CSV report without a stable schema is not automatically interchangeable with JSON objects.

An Abstract Factory can also become a bottleneck when a product is added: every family may need an implementation. This is justified when family completeness is itself a requirement, but wasteful when variations are independent. A simple factory is not inferior by default; it often expresses the correct amount of coupling.

## Complexity, tests and quality of evidence

The code checks a malformed row, escaped CSV input and both compatible families. It does not test arbitrary Unicode filenames, all CSV dialects, infinite-length records, resource exhaustion or external storage. For production use, enforce size limits and document serialization schema compatibility. Test the same rows through JSON and CSV parsers, then compare semantic records rather than raw bytes. The critical invariant is compatibility of exported body and declared format, not class count.

## Exercises and verification

1. Add TSV. Decide whether only a simple-factory entry, a Factory Method subclass or an entire new family is necessary and justify the choice.
2. Try a name containing a comma, quote and newline; parse the CSV output with csv.reader and show a round-trip test [3].
3. Deliberately combine a JSON renderer and CSV naming strategy outside a family. Identify where the application should reject the mismatch.
4. Replace the subclassed ExportJob with an injected renderer. Compare testability and number of public abstractions.
5. Determine whether returning a default format on error violates the caller's expectations; specify a predictable alternative.

Related chapters: [design-pattern families](/en/topics/design-pattern-families/), [SOLID](/en/topics/solid-dependency-inversion/) and [domain aggregates](/en/topics/domain-modeling-aggregates-invariants/).