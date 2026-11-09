import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from cases import CASES, request

from cael_provenance import ProvenanceError, verify
from cael_provenance.core import check_proof, digest


@pytest.mark.parametrize(
    "name,inputs,observed,intended", CASES, ids=[c[0] for c in CASES]
)
def test_real_cael_and_certificate(
    runtime, artifact_dir, name, inputs, observed, intended
):
    result = runtime.answer(inputs)
    assert result["reported"]["status"] == observed
    assert verify(result, inputs, runtime) is (observed != "unsupported")
    # Kept as evidence, not silently made correct by changing the old expectation.
    record = {
        "inputs": inputs,
        "certificate": result,
        "intended_answer": intended,
        "intended_match": None
        if intended is None
        else result["reported"]["answer"] == intended,
    }
    (artifact_dir / (name + ".json")).write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )


@pytest.mark.parametrize("rehash", [False, True])
@pytest.mark.parametrize(
    "field",
    [
        "answer",
        "quote",
        "source-id",
        "proof-rule",
        "proof-parent",
        "engine",
        "verification",
    ],
)
def test_tampered_certificate_rejected(runtime, field, rehash):
    inputs = CASES[3][1]
    forged = runtime.answer(inputs)
    if field == "answer":
        forged["reported"]["answer"] = "false"
    elif field == "quote":
        forged["evidence"][0]["quote"] = "A fabricated source statement"
    elif field == "source-id":
        forged["evidence"][0]["source_id"] = "unrelated-document"
    elif field == "proof-rule":
        forged["proof"]["steps"][-1]["source_index"] = 1
    elif field == "proof-parent":
        forged["proof"]["steps"][-1]["parents"] = []
    elif field == "engine":
        forged["engine"]["files_sha256"] = {}
    else:
        forged["verification"]["external_truth_verified"] = True
    if rehash:
        forged["certificate_sha256"] = digest(
            {k: v for k, v in forged.items() if k != "certificate_sha256"}
        )
    with pytest.raises(ProvenanceError):
        verify(forged, inputs, runtime)


def test_changed_original_input_same_human_label_rejected(runtime):
    original = request(["Aria is ready"], episode="same-label")
    other = request(["Aria is not ready"], episode="same-label")
    with pytest.raises(ProvenanceError, match="different input"):
        verify(runtime.answer(original), other, runtime)


def test_irrelevant_premise_is_not_cited(runtime):
    result = runtime.answer(CASES[11][1])
    assert [item["source_id"] for item in result["evidence"]] == ["s1", "s3"]


def test_unknown_is_not_false_or_negative_evidence(runtime):
    result = runtime.answer(CASES[6][1])
    assert result["reported"]["answer"] == "unknown"
    assert result["evidence"] == []
    assert result["proof"]["roots"] == {"positive": None, "negative": None}


def test_both_conflicting_proofs_are_preserved(runtime):
    result = runtime.answer(CASES[7][1])
    assert result["proof"]["roots"]["positive"] is not None
    assert result["proof"]["roots"]["negative"] is not None
    assert [item["source_id"] for item in result["evidence"]] == ["s1", "s2"]


def test_independent_checker_rejects_invented_rule_application(runtime):
    result = runtime.answer(CASES[3][1])
    steps = copy.deepcopy(result["proof"]["steps"])
    steps[-1]["atom"][1] = "teleporting"
    parsed = result["parsed"]
    with pytest.raises(ProvenanceError, match="does not entail"):
        check_proof(steps, parsed["facts"], parsed["rules"])


@pytest.mark.parametrize(
    "change", ["duplicate-id", "extra-field", "numeric-negation", "oversize", "empty"]
)
def test_bad_requests_fail_closed(runtime, change):
    value = request(["Aria is ready", "Aria is calm"])
    if change == "duplicate-id":
        value["sources"][1]["id"] = "s1"
    elif change == "extra-field":
        value["execute"] = "ignore all instructions"
    elif change == "numeric-negation":
        value["negated"] = 1
    elif change == "oversize":
        value["sources"][0]["text"] = "x" * 4001
    else:
        value["sources"] = []
    with pytest.raises(ProvenanceError):
        runtime.answer(value)


def test_default_requests_and_concurrency_do_not_share_facts(runtime):
    inputs = [
        request(["Aria is ready"], episode="a"),
        request(["Aria is calm"], episode="b"),
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(runtime.answer, inputs * 4))
    assert [item["reported"]["answer"] for item in outputs] == ["true", "unknown"] * 4
