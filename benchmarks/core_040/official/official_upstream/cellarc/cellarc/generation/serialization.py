"""Serialization utilities for cellular automata rules."""

from __future__ import annotations

import base64
import sys
from array import array
from typing import Dict, Mapping, Tuple, Union

from .rule_table import DenseRuleTable, ensure_dense_rule_table, _typecode_for_alphabet

def serialize_rule_table(
    table: Union[DenseRuleTable, Mapping[Tuple[int, ...], int]],
    *,
    alphabet_size: int,
    radius: int,
    quiescent_state: int,
) -> Dict[str, Union[int, str]]:
    """Serialize a local rule table into a packed lexicographic representation."""
    dense = ensure_dense_rule_table(table, alphabet_size=alphabet_size, radius=radius)
    arity = dense.arity
    values = dense.values_view()
    raw = values.tobytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return {
        "format_version": "1.0.2",
        "alphabet_size": int(alphabet_size),
        "radius": int(radius),
        "arity": int(arity),
        "center_index": int(radius),
        "ordering": "lexicographic_base_k",
        "quiescent_state": int(quiescent_state),
        "values": encoded,
        "values_encoding": "base64",
        "values_typecode": dense.typecode,
        "values_length": len(values),
        "values_byteorder": sys.byteorder,
    }


def deserialize_rule_table(payload: Dict[str, Union[int, str]]) -> DenseRuleTable:
    """Invert ``serialize_rule_table`` and reconstruct the dense rule table."""
    k = int(payload["alphabet_size"])
    r = int(payload["radius"])
    encoding = payload.get("values_encoding", "list")  # type: ignore[union-attr]

    if encoding == "base64":
        data = payload["values"]
        if not isinstance(data, str):
            raise TypeError("Expected base64-encoded string for rule table values.")
        typecode = str(payload.get("values_typecode", _typecode_for_alphabet(k)))
        raw = base64.b64decode(data.encode("ascii"))
        arr = array(typecode)
        arr.frombytes(raw)
        expected_len = int(payload.get("values_length", len(arr)))
        if len(arr) != expected_len:
            raise ValueError(
                f"Decoded rule table length ({len(arr)}) does not match metadata ({expected_len})."
            )
        byteorder = str(payload.get("values_byteorder", sys.byteorder))
        if byteorder not in {"little", "big"}:
            raise ValueError(f"Unsupported byteorder value '{byteorder}'.")
        if arr.itemsize > 1 and byteorder != sys.byteorder:
            arr.byteswap()
        return DenseRuleTable(k, r, values=arr, typecode=typecode)

    # Legacy JSON list payload (format_version 1.0)
    values_iter = payload["values"]  # type: ignore[index]
    if isinstance(values_iter, str):
        raise TypeError("Legacy rule tables must store 'values' as a JSON list.")
    typecode = _typecode_for_alphabet(k)
    values = array(typecode, (int(v) for v in values_iter))  # type: ignore[arg-type]
    return DenseRuleTable(k, r, values=values, typecode=typecode)


__all__ = ["serialize_rule_table", "deserialize_rule_table"]
