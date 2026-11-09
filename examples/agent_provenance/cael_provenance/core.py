"""Source-bound CAEL replies and checked Horn derivations, not external truth."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

FORMAT = "cael-provenance-v1"
RELEASE = "49359eae9aa197d5b92631c16efb74085180a27c"
PINS = {
    "cael_unified/reasoning_logic.py": "38e21e399a98ea47d25f2b7e5eec0d6735afb31fa046d67f29bdaf208e17eb95",
    "models/cael-reasoning-v1/model.json": "a7f52da1f5afc6776af91d451a7273a269593642cd5f6d8a2883c4e34fab0bd4",
}
Atom = tuple[str, str, int]


class ProvenanceError(ValueError):
    """A request, citation, certificate or trusted runtime does not match."""


def digest(value: Any) -> str:
    """Hash canonical JSON, including exact source text and its order."""
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: Any, maximum: int) -> str:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise ProvenanceError("Expected bounded, nonempty literal text")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ProvenanceError("Control characters are not accepted")
    return value


def _request(value: dict[str, Any]) -> dict[str, Any]:
    required = {"episode_id", "sources", "entity", "predicate"}
    if type(value) is not dict or not required <= set(value) <= required | {"negated"}:
        raise ProvenanceError("Use episode_id, sources, entity, predicate and negated")
    records = value["sources"]
    if type(records) is not list or not 1 <= len(records) <= 64:
        raise ProvenanceError("Provide 1 to 64 source statements")
    sources, identifiers = [], set()
    for record in records:
        if type(record) is not dict or set(record) not in (
            {"id", "text"},
            {"id", "text", "origin"},
        ):
            raise ProvenanceError("A source has id, text and optional origin")
        identifier = _text(record["id"], 100)
        if identifier in identifiers:
            raise ProvenanceError("Source IDs must be unique within an episode")
        identifiers.add(identifier)
        origin = record.get("origin")
        if origin is not None:
            _text(origin, 1000)
        sources.append(
            {"id": identifier, "text": _text(record["text"], 4000), "origin": origin}
        )
    if sum(len(record["text"]) for record in sources) > 32000:
        raise ProvenanceError("The total premise text exceeds the bridge bound")
    entity, predicate = value["entity"], value["predicate"]
    for phrase in (entity, predicate):
        _text(phrase, 80)
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z -]{0,79}", phrase):
            raise ProvenanceError("Use literal English entity/property phrases")
    if re.search(r"\b(?:not|and|or|either|unless)\b", predicate, re.IGNORECASE):
        raise ProvenanceError("Query one property; specify polarity with negated")
    negated = value.get("negated", False)
    if type(negated) is not bool:
        raise ProvenanceError("negated must be a Boolean, not a numeric flag")
    return {
        "episode_id": _text(value["episode_id"], 100),
        "sources": sources,
        "entity": entity,
        "predicate": predicate,
        "negated": negated,
    }


def _closure(
    facts: list[Any], rules: list[Any], allowed: set[int] | None = None
) -> tuple[dict[Atom, int], list[dict[str, Any]]]:
    """Independent finite Horn closure; no learned table or CAEL.close call."""
    known: dict[Atom, int] = {}
    steps: list[dict[str, Any]] = []

    def add(atom: Atom, source: int, parents: list[int]) -> None:
        if atom not in known:
            if len(steps) >= 4096:
                raise ProvenanceError("Independent proof-node budget exceeded")
            known[atom] = len(steps)
            steps.append(
                {
                    "id": len(steps),
                    "atom": list(atom),
                    "source_index": source,
                    "parents": parents,
                }
            )

    for atom, source in facts:
        if allowed is None or source in allowed:
            add(atom, source, [])
    entities = sorted({atom[0] for atom, _ in facts})
    work, changed = 0, True
    while changed:
        changed = False
        for body, heads, source in rules:
            if allowed is not None and source not in allowed:
                continue
            for entity in entities:
                work += 1
                if work > 250000:
                    raise ProvenanceError(
                        "Independent proof-transition budget exceeded"
                    )
                premises = [(entity, prop, neg) for prop, neg in body]
                if all(atom in known for atom in premises):
                    for prop, neg in heads:
                        atom = (entity, prop, neg)
                        if atom not in known:
                            add(atom, source, [known[parent] for parent in premises])
                            changed = True
    return known, steps


def check_proof(
    steps: list[dict[str, Any]], facts: list[Any], rules: list[Any]
) -> set[int]:
    """Check every cited fact/rule application without calling the reasoner."""
    by_source = {source: (body, heads) for body, heads, source in rules}
    given = {(tuple(atom), source) for atom, source in facts}
    seen: dict[int, Atom] = {}
    support = set()
    if type(steps) is not list or len(steps) > 4096:
        raise ProvenanceError("Malformed proof steps")
    for step in steps:
        if type(step) is not dict or set(step) != {
            "id",
            "atom",
            "source_index",
            "parents",
        }:
            raise ProvenanceError("Malformed proof step")
        identifier, source = step["id"], step["source_index"]
        atom, parents = step["atom"], step["parents"]
        if (
            type(identifier) is not int
            or identifier in seen
            or identifier < 0
            or type(source) is not int
            or source < 1
            or type(atom) is not list
            or len(atom) != 3
            or type(atom[0]) is not str
            or type(atom[1]) is not str
            or type(atom[2]) is not int
            or atom[2] not in (0, 1)
            or type(parents) is not list
            or any(
                type(parent) is not int or parent not in seen or parent >= identifier
                for parent in parents
            )
        ):
            raise ProvenanceError("Invalid atom or nonpreceding proof reference")
        literal = tuple(atom)
        if not parents:
            if (literal, source) not in given:
                raise ProvenanceError("The cited source does not contain that fact")
        else:
            if source not in by_source:
                raise ProvenanceError("The cited source is not a rule")
            body, heads = by_source[source]
            expected = [(atom[0], prop, neg) for prop, neg in body]
            if [seen[parent] for parent in parents] != expected:
                raise ProvenanceError("Rule premises do not match the proof")
            if literal not in [(atom[0], prop, neg) for prop, neg in heads]:
                raise ProvenanceError("The rule does not entail this conclusion")
        seen[identifier] = literal
        support.add(source)
    return support


def _selected(
    steps: list[dict[str, Any]], roots: list[int | None]
) -> list[dict[str, Any]]:
    pending, used = [root for root in roots if root is not None], set()
    while pending:
        current = pending.pop()
        if current not in used:
            used.add(current)
            pending.extend(steps[current]["parents"])
    return [step for step in steps if step["id"] in used]


class CAELRuntime:
    """Load only the two pinned external logical-engine/model files."""

    def __init__(self, root: str | Path):
        root = Path(root).resolve()
        for name, expected in PINS.items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                raise ProvenanceError(
                    "External CAEL file does not match the pin: " + name
                )
        self.identity = {
            "version": "0.4.0",
            "release_commit": RELEASE,
            "files_sha256": dict(PINS),
        }
        self._model = json.loads(
            (root / "models/cael-reasoning-v1/model.json").read_text(encoding="utf-8")
        )
        # A private package avoids importing a dirty/global CAEL checkout or
        # triggering the Assistant, learned stores or unrelated model loaders.
        namespace = "_cael_provenance_" + PINS["cael_unified/reasoning_logic.py"][:16]
        module_name = namespace + ".reasoning_logic"
        if module_name not in sys.modules:
            package = ModuleType(namespace)
            package.__path__ = [str(root / "cael_unified")]
            sys.modules[namespace] = package
            spec = importlib.util.spec_from_file_location(
                module_name, root / "cael_unified/reasoning_logic.py"
            )
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # trusted, hash-pinned engine source
        self._logic = sys.modules[module_name]

    def answer(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return actual CAEL output with a source-bound, checked certificate."""
        inputs = _request(request)
        engine = self._logic.LogicCA(copy.deepcopy(self._model))
        sources = inputs["sources"]
        result: dict[str, Any] = {
            "format": FORMAT,
            "inputs": inputs,
            "input_sha256": digest(inputs),
            "engine": copy.deepcopy(self.identity),
            "evidence": [],
            "parsed": None,
            "proof": None,
        }
        try:
            if any(len(self._logic.sentences(item["text"])) != 1 for item in sources):
                raise self._logic.Unparsed(
                    "Each source must contain exactly one premise"
                )
            context = ". ".join(item["text"].strip(" .\n\r") for item in sources)
            if len(self._logic.sentences(context)) != len(sources):
                raise self._logic.Unparsed(
                    "Source boundaries do not match the engine parse"
                )
            facts, rules = engine.parse(context)
            properties = engine.properties(inputs["predicate"])
            if len(properties) != 1 or properties[0][1]:
                raise self._logic.Unparsed("Query one literal property")
            entity = re.sub(r"(?i)^the\s+", "", inputs["entity"]).lower()
            target = (entity, properties[0][0], int(inputs["negated"]))
            opposite = (target[0], target[1], 1 - target[2])
            question = f"Is {inputs['entity']} {'not ' if inputs['negated'] else ''}{inputs['predicate']}?"
            reply = engine.query(context, question)
            result["reported"] = reply  # no answer/flag replacement
            result["parsed"] = {"facts": facts, "rules": rules, "query": list(target)}
            all_known, _ = _closure(facts, rules)
            positive, negative = target in all_known, opposite in all_known
            status = (
                "conflicting"
                if positive and negative
                else "true"
                if positive
                else "false"
                if negative
                else "unknown"
            )
            indices = reply["support"]
            if type(indices) is not list or any(
                type(i) is not int or not 1 <= i <= len(sources) for i in indices
            ):
                raise ProvenanceError("CAEL returned an invalid source index")
            restricted, steps = _closure(facts, rules, set(indices))
            roots = [restricted.get(target), restricted.get(opposite)]
            selected = _selected(steps, roots)
            used = check_proof(selected, facts, rules)
            if (
                status != reply["answer"]
                or bool(roots[0] is not None) != positive
                or bool(roots[1] is not None) != negative
                or used != set(indices)
            ):
                raise ProvenanceError(
                    "Independent proof does not verify the reported answer/support"
                )
            result["proof"] = {
                "steps": selected,
                "roots": {"positive": roots[0], "negative": roots[1]},
                "checked_status": status,
            }
            for index in indices:
                source = sources[index - 1]
                result["evidence"].append(
                    {
                        "source_id": source["id"],
                        "statement_index": index,
                        "quote": source["text"],
                        "origin": source["origin"],
                        "text_sha256": hashlib.sha256(
                            source["text"].encode("utf-8")
                        ).hexdigest(),
                    }
                )
            result["verification"] = {
                "passed": True,
                "scope": "derivation_relative_to_CAEL_parse",
                "independent_horn_check": True,
                "external_truth_verified": False,
            }
        except self._logic.Unparsed as exc:
            result["reported"] = {
                "status": "unsupported",
                "answer": None,
                "support": [],
                "error": str(exc),
            }
            result["verification"] = {
                "passed": False,
                "reason": "unsupported",
                "detail": str(exc),
            }
        except ProvenanceError as exc:
            result["verification"] = {
                "passed": False,
                "reason": "unverified",
                "detail": str(exc),
            }
        result["certificate_sha256"] = digest(result)
        return json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))


def verify(
    certificate: dict[str, Any], original_request: dict[str, Any], runtime: CAELRuntime
) -> bool:
    """Verify against trusted original input and replay, not a self-asserted flag.

    Hashes detect changes; they do not authenticate an author or sign a source.
    Unsupported/unverifiable outputs never qualify as verified answers.
    """
    if type(certificate) is not dict:
        raise ProvenanceError("A certificate must be a JSON object")
    payload = {
        key: value for key, value in certificate.items() if key != "certificate_sha256"
    }
    if certificate.get("certificate_sha256") != digest(payload):
        raise ProvenanceError("Certificate hash mismatch")
    if certificate.get("input_sha256") != digest(_request(original_request)):
        raise ProvenanceError("The certificate belongs to a different input")
    # This replay also reconstructs the parsed facts and independently checks
    # every rule application. A rehashed forged citation/answer still fails.
    actual = runtime.answer(original_request)
    if digest(certificate) != digest(actual):
        raise ProvenanceError(
            "Certificate, citations or proof do not match pinned replay"
        )
    return bool(actual["verification"]["passed"])
