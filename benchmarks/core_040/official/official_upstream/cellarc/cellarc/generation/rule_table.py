"""Dense rule-table representation with dictionary semantics."""

from __future__ import annotations

from array import array
from collections.abc import Iterator, MutableMapping
from typing import Iterable, Mapping, Sequence, Tuple, Union

from .helpers import enumerate_neighborhoods, neighborhood_index


def _typecode_for_alphabet(alphabet_size: int) -> str:
    """Pick the smallest unsigned array typecode that can hold the alphabet."""
    if alphabet_size <= 0:
        raise ValueError("alphabet_size must be positive.")
    if alphabet_size <= 256:
        return "B"
    if alphabet_size <= 65536:
        return "H"
    return "I"


RuleTableLike = Union["DenseRuleTable", Mapping[Tuple[int, ...], int]]


class DenseRuleTable(MutableMapping[Tuple[int, ...], int]):
    """
    Dense storage for local CA rules with Tuple[int, ...] keys.

    Values are stored in a contiguous array indexed by the base-k encoding of
    the neighbourhood, but the mapping interface remains compatible with the
    previous ``Dict[Tuple[int, ...], int]`` usage.
    """

    __slots__ = (
        "alphabet_size",
        "radius",
        "_arity",
        "_typecode",
        "_values",
    )

    def __init__(
        self,
        alphabet_size: int,
        radius: int,
        values: Sequence[int] | array | None = None,
        *,
        typecode: str | None = None,
    ) -> None:
        self.alphabet_size = int(alphabet_size)
        self.radius = int(radius)
        if self.alphabet_size <= 0:
            raise ValueError("alphabet_size must be positive.")
        if self.radius < 0:
            raise ValueError("radius must be non-negative.")
        self._arity = 2 * self.radius + 1
        self._typecode = typecode or _typecode_for_alphabet(self.alphabet_size)
        expected_len = self.alphabet_size ** self._arity
        if values is None:
            self._values = array(self._typecode, [0] * expected_len)
            return

        if isinstance(values, array):
            arr = values
            if len(arr) != expected_len:
                raise ValueError(
                    f"Provided values length ({len(arr)}) does not match expected table size ({expected_len})."
                )
            if arr.typecode != self._typecode:
                arr = array(self._typecode, arr.tolist())
            self._values = arr
            return

        arr = array(self._typecode, values)
        if len(arr) != expected_len:
            raise ValueError(
                f"Provided values length ({len(arr)}) does not match expected table size ({expected_len})."
            )
        self._values = arr

    @property
    def arity(self) -> int:
        """Return the neighbourhood arity (2 * radius + 1)."""
        return self._arity

    @property
    def typecode(self) -> str:
        """Return the underlying array typecode."""
        return self._typecode

    def values_view(self) -> array:
        """Return the internal value buffer (copy-on-write by callers if needed)."""
        return self._values

    def copy_values(self) -> array:
        """Return a shallow copy of the internal value buffer."""
        return array(self._values.typecode, self._values)

    def to_sequence(self) -> Sequence[int]:
        """Expose the rule table as an immutable sequence of ints."""
        return tuple(int(v) for v in self._values)

    # --- MutableMapping interface -------------------------------------------------
    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[Tuple[int, ...]]:
        neighborhoods, _, _ = neighborhood_index(self.alphabet_size, self.radius)
        return iter(neighborhoods)

    def __getitem__(self, key: Tuple[int, ...]) -> int:
        idx = self._index_of(key)
        return int(self._values[idx])

    def __setitem__(self, key: Tuple[int, ...], value: int) -> None:
        idx = self._index_of(key)
        self._values[idx] = int(value)

    def __delitem__(self, key: Tuple[int, ...]) -> None:  # pragma: no cover - API guard
        raise TypeError("DenseRuleTable does not support item deletion.")

    # --- Helpers ------------------------------------------------------------------
    def _index_of(self, neighborhood: Tuple[int, ...]) -> int:
        if len(neighborhood) != self._arity:
            raise ValueError(
                f"Neighbourhood length {len(neighborhood)} does not match rule arity {self._arity}."
            )
        idx = 0
        base = self.alphabet_size
        for digit in neighborhood:
            d = int(digit)
            if d < 0 or d >= base:
                raise ValueError(f"Neighbourhood digit {d} outside alphabet range [0, {base}).")
            idx = idx * base + d
        return idx

    def apply_dense(self, code: int) -> int:
        """Return the output associated with the encoded neighbourhood index."""
        return int(self._values[code])

    def update_from_pairs(self, pairs: Iterable[Tuple[Tuple[int, ...], int]]) -> None:
        """Bulk update values from (neighbourhood, value) pairs."""
        for nb, val in pairs:
            self[nb] = val


def ensure_dense_rule_table(
    table: RuleTableLike,
    *,
    alphabet_size: int,
    radius: int,
) -> DenseRuleTable:
    """Convert legacy mappings to DenseRuleTable with cached ordering."""
    if isinstance(table, DenseRuleTable):
        if table.alphabet_size != alphabet_size or table.radius != radius:
            raise ValueError(
                "DenseRuleTable metadata does not match the provided alphabet_size/radius."
            )
        return table

    neighborhoods, _, _ = neighborhood_index(alphabet_size, radius)
    typecode = _typecode_for_alphabet(alphabet_size)
    values = array(typecode)
    if neighborhoods:
        values = array(typecode, [0]) * len(neighborhoods)
    for idx, nb in enumerate(neighborhoods):
        try:
            values[idx] = int(table[nb])
        except KeyError as err:
            raise KeyError(f"Missing neighbourhood {nb} in rule table.") from err
    return DenseRuleTable(alphabet_size, radius, values=values, typecode=typecode)


__all__ = ["DenseRuleTable", "ensure_dense_rule_table", "_typecode_for_alphabet"]
