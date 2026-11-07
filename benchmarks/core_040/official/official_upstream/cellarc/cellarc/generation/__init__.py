"""Cellular automata generation utilities exposed as a package."""

from .cax_runner import AutomatonRunner, evolve_rule_table, random_state
from .constants import SCHEMA_VERSION
from .dataset import generate_dataset_jsonl
from .fingerprints import apply_rule_from_table, induced_tstep_fingerprint, rule_fingerprint
from .helpers import as_init, enumerate_neighborhoods, neighborhood_index, ring_slice
from .metrics import (
    average_cell_entropy,
    average_mutual_information,
    joint_shannon_entropy,
    mutual_information,
    shannon_entropy,
)
from .morphology import quick_morphology_features
from .rule_table import DenseRuleTable
from .rules import (
    rule_table_cyclic_excitable,
    rule_table_linear_mod_k,
    rule_table_outer_inner_totalistic,
    rule_table_outer_totalistic,
    rule_table_permuted_totalistic,
    rule_table_random_lambda,
    rule_table_threshold,
    rule_table_totalistic,
)
from .sampling import entropy_bin, lambda_bin, sample_task
from .serialization import deserialize_rule_table, serialize_rule_table

__all__ = [
    "SCHEMA_VERSION",
    "generate_dataset_jsonl",
    "sample_task",
    "lambda_bin",
    "entropy_bin",
    "AutomatonRunner",
    "evolve_rule_table",
    "random_state",
    "average_cell_entropy",
    "average_mutual_information",
    "shannon_entropy",
    "joint_shannon_entropy",
    "mutual_information",
    "DenseRuleTable",
    "apply_rule_from_table",
    "induced_tstep_fingerprint",
    "rule_fingerprint",
    "quick_morphology_features",
    "serialize_rule_table",
    "deserialize_rule_table",
    "as_init",
    "enumerate_neighborhoods",
    "neighborhood_index",
    "ring_slice",
    "rule_table_random_lambda",
    "rule_table_totalistic",
    "rule_table_outer_totalistic",
    "rule_table_outer_inner_totalistic",
    "rule_table_threshold",
    "rule_table_linear_mod_k",
    "rule_table_cyclic_excitable",
    "rule_table_permuted_totalistic",
]
