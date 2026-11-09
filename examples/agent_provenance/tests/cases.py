"""CC0 authored integration fixtures; two historical misses are retained."""


def request(
    lines, *, episode="example", entity="Aria", predicate="ready", negated=False
):
    return {
        "episode_id": episode,
        "sources": [
            {"id": f"s{i}", "text": line, "origin": "authored:test"}
            for i, line in enumerate(lines, 1)
        ],
        "entity": entity,
        "predicate": predicate,
        "negated": negated,
    }


CASES = [
    ("direct", request(["Aria is ready"]), "true", "true"),
    ("negative", request(["Aria is not ready"]), "false", "false"),
    ("negative-query", request(["Aria is not ready"], negated=True), "true", "true"),
    (
        "chain",
        request(
            ["Aria is a wren", "Every wren is a bird", "Every bird is visible"],
            predicate="visible",
        ),
        "true",
        "true",
    ),
    (
        "conjunction",
        request(
            [
                "Aria is bright",
                "Aria is calm",
                "Everything that is bright and calm is ready",
            ]
        ),
        "true",
        "true",
    ),
    (
        "missing-conjunct",
        request(["Aria is bright", "Everything that is bright and calm is ready"]),
        "unknown",
        "unknown",
    ),
    ("unknown", request(["Aria is calm"]), "unknown", "unknown"),
    (
        "conflict",
        request(["Aria is ready", "Aria is not ready"]),
        "conflicting",
        "conflicting",
    ),
    (
        "derived-conflict",
        request(["Aria is a wren", "Every wren is not ready", "Aria is ready"]),
        "conflicting",
        "conflicting",
    ),
    (
        "unconnected-cycle",
        request(["Aria is green", "Every amber is violet", "Every violet is amber"]),
        "unknown",
        "unknown",
    ),
    (
        "shorter-proof",
        request(["Aria is calm", "Every calm is ready", "Aria is ready"]),
        "true",
        "true",
    ),
    (
        "distractor",
        request(["Aria is calm", "Bex is blue", "Every calm is ready"]),
        "true",
        "true",
    ),
    (
        "unsupported-condition",
        request(["Aria is calm unless it rains"]),
        "unsupported",
        None,
    ),
    (
        "unsupported-disjunction",
        request(["Aria is either calm or blue"]),
        "unsupported",
        None,
    ),
    (
        "multiple-statements-in-source",
        request(["Aria is calm. Aria is ready."]),
        "unsupported",
        None,
    ),
    (
        "historical-thing-chain-positive",
        request(
            [
                "Nika is glimmering",
                "Every glimmering thing is amber",
                "Every amber thing is visible",
            ],
            entity="Nika",
            predicate="visible",
        ),
        "unknown",
        "true",
    ),
    (
        "historical-thing-chain-negative",
        request(
            [
                "Nika is glimmering",
                "Every glimmering thing is amber",
                "Every amber thing is visible",
            ],
            entity="Nika",
            predicate="visible",
            negated=True,
        ),
        "unknown",
        "false",
    ),
]
