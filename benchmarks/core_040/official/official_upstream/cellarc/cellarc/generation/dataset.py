"""Dataset generation driver with balancing and uniqueness checks."""

from __future__ import annotations

import json
import math
import random
import signal
import threading
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

try:  # pragma: no cover - optional dependency
    from tqdm import tqdm
except ImportError:  # pragma: no cover - fallback when tqdm is absent
    tqdm = None  # type: ignore

from .constants import SCHEMA_VERSION
from .sampling import sample_task


def _signal_timeouts_supported() -> bool:
    """Check if we can rely on SIGALRM for pre-emptive timeouts."""
    return hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread()


@contextmanager
def _time_limit(seconds: float) -> None:
    """
    Enforce a wall-clock timeout using SIGALRM when available.

    Falls back silently when signals are unsupported (e.g. non-main thread).
    """
    if seconds <= 0:
        yield
        return
    if not _signal_timeouts_supported():
        yield
        return

    def _raise_timeout(signum: int, frame) -> None:  # pragma: no cover - depends on signal delivery
        raise TimeoutError(f"Operation exceeded {seconds} seconds")

    previous_handler = signal.getsignal(signal.SIGALRM)
    # setitimer provides sub-second resolution; zero the timer on exit
    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)


def _call_with_timeout(func: Callable[[], Dict[str, object]], timeout: Optional[float]) -> Dict[str, object]:
    """
    Execute callable enforcing timeout where possible.

    Uses SIGALRM for pre-emption; otherwise measures elapsed time and raises
    post-hoc so the caller can discard the result.
    """
    if timeout is None:
        return func()

    if _signal_timeouts_supported():
        with _time_limit(timeout):
            return func()

    start = perf_counter()
    result = func()
    if perf_counter() - start > timeout:
        raise TimeoutError(f"Operation exceeded {timeout} seconds")
    return result


def _warmup_timeout_sensitive_backends() -> None:
    """
    Prime backends that perform global initialisation (e.g. JAX GPU plugins).

    Doing this before activating SIGALRM-based timeouts prevents the timer from
    interrupting one-off startup and forcing a CPU fallback.
    """
    try:
        import jax  # type: ignore
    except ImportError:
        return

    try:  # pragma: no cover - backend-dependent code path
        jax.devices()
    except Exception:
        # Device discovery failures will surface naturally later; we only care
        # about avoiding spurious interrupts here.
        return


def generate_dataset_jsonl(
    path: Path,
    *,
    count: int,
    seed: Optional[int] = None,
    meta_path: Optional[Path] = None,
    k_range=(2, 6),
    max_radius=3,
    max_steps=5,
    train_examples=4,
    target_avg_train_len=48,
    family_mix=None,
    unique_by="tstep",
    balance_by: str = "lambda",
    max_attempts_per_item: int = 200,
    coverage_fraction: Union[
        float,
        Sequence[float],
        Callable[[random.Random], float],
    ] = 1.0,
    coverage_mode: str = "chunked",
    cap_lambda: Optional[float] = None,
    cap_entropy: Optional[float] = None,
    compute_complexity: bool = True,
    annotate_morphology: bool = True,
    query_within_coverage: bool = False,
    construction: str = "cycle",
    unroll_tau_max: int = 24,
    seen_fingerprints: Optional[Set[str]] = None,
    schema_version: str = SCHEMA_VERSION,
    dataset_version: str = "dev",
    show_progress: bool = True,
    progress_desc: Optional[str] = None,
    sample_timeout: Optional[float] = None,
    include_rule_table: bool = True,
):
    """Generate a JSONL dataset and companion metadata file."""
    rng = random.Random(seed)
    shared_seen = seen_fingerprints if seen_fingerprints is not None else set()
    produced = 0
    attempts = 0
    attempt_budget_skips = 0
    accepted_fps: List[str] = []
    accepted_probe_fps: List[str] = []
    lambda_sum = 0.0
    lambda_min = float("inf")
    lambda_max = float("-inf")
    coverage_fraction_sum = 0.0
    coverage_fraction_min = float("inf")
    coverage_fraction_max = float("-inf")
    coverage_windows_sum = 0.0
    coverage_windows_min = float("inf")
    coverage_windows_max = float("-inf")
    family_counts: Counter[str] = Counter()
    coverage_mode_counts: Counter[str] = Counter()
    train_length_sum = 0.0
    train_length_min = float("inf")
    train_length_max = float("-inf")
    train_length_count = 0
    train_length_hist: Counter[int] = Counter()
    query_length_sum = 0.0
    query_length_min = float("inf")
    query_length_max = float("-inf")
    query_length_count = 0
    query_length_hist: Counter[int] = Counter()
    timeout_count = 0

    progress = None
    if show_progress and tqdm is not None and count > 0:
        desc = progress_desc or path.stem
        progress = tqdm(total=count, desc=desc, unit="episode")

    meta_path = meta_path or path.with_name(f"{path.stem}_meta.jsonl")

    if balance_by == "entropy" and not compute_complexity:
        raise ValueError("balance_by='entropy' requires compute_complexity=True.")
    if cap_entropy is not None and not compute_complexity:
        raise ValueError("cap_entropy requires compute_complexity=True.")

    if balance_by == "lambda":
        bins = ["ordered", "edge", "chaotic"]
    elif balance_by == "entropy":
        bins = ["low", "mid", "high"]
    else:
        bins = ["all"]

    per_bin_cap = math.ceil(count / len(bins))
    bin_counts = {b: 0 for b in bins}

    def sample_coverage_fraction() -> float:
        spec = coverage_fraction
        if callable(spec):
            val = float(spec(rng))
        elif isinstance(spec, Sequence) and not isinstance(spec, (str, bytes)):
            if len(spec) == 0:
                raise ValueError("coverage_fraction sequence must be non-empty.")
            if len(spec) == 2 and all(isinstance(x, (int, float)) for x in spec):
                lo, hi = float(spec[0]), float(spec[1])
                if lo > hi:
                    lo, hi = hi, lo
                val = float(lo) if math.isclose(lo, hi) else float(rng.uniform(lo, hi))
            else:
                val = float(rng.choice(list(spec)))
        else:
            val = float(spec)
        if not (0 < val <= 1.0):
            raise ValueError("coverage_fraction values must lie in (0, 1].")
        return val

    timeout_armed = sample_timeout is None

    try:
        if sample_timeout is not None:
            _warmup_timeout_sensitive_backends()

        with path.open("w", encoding="utf-8") as f_core, meta_path.open(
            "w", encoding="utf-8"
        ) as f_meta:
            while produced < count:
                attempts += 1
                if attempts > count * max_attempts_per_item:
                    attempt_budget_skips += 1
                    msg = (
                        "Attempt budget exceeded; stopping early. "
                        "Relax caps or balancing to produce more items."
                    )
                    if progress is not None:
                        progress.write(msg)
                    else:
                        print(msg)
                    break

                coverage_fraction_val = sample_coverage_fraction()

                def _sample() -> Dict[str, object]:
                    return sample_task(
                        rng,
                        k_range=k_range,
                        max_radius=max_radius,
                        max_steps=max_steps,
                        train_examples=train_examples,
                        target_avg_train_len=target_avg_train_len,
                        family_mix=family_mix,
                        unique_by=unique_by,
                        coverage_fraction=coverage_fraction_val,
                        coverage_mode=coverage_mode,
                        compute_complexity=compute_complexity,
                        annotate_morphology=annotate_morphology,
                        query_within_coverage=query_within_coverage,
                        schema_version=schema_version,
                        dataset_version=dataset_version,
                        construction=construction,
                        unroll_tau_max=unroll_tau_max,
                        include_rule_table=include_rule_table,
                    )

                timeout_for_call = sample_timeout if timeout_armed else None

                try:
                    rec = _call_with_timeout(_sample, timeout_for_call)
                except TimeoutError:
                    timeout_count += 1
                    timeout_armed = True
                    continue
                timeout_armed = True

                if cap_lambda is not None and rec["meta"]["lambda"] > cap_lambda:
                    continue
                if cap_entropy is not None and rec["meta"]["avg_cell_entropy"] > cap_entropy:
                    continue

                fp = rec["meta"]["fingerprint"]
                if fp in shared_seen:
                    continue
                probe_fp = rec["meta"]["probe_fingerprint"]

                if balance_by == "lambda":
                    bin_key = rec["meta"]["lambda_bin"]
                elif balance_by == "entropy":
                    bin_key = rec["meta"]["entropy_bin"]
                else:
                    bin_key = "all"

                if bin_counts[bin_key] >= per_bin_cap:
                    continue

                shared_seen.add(fp)
                accepted_fps.append(fp)
                accepted_probe_fps.append(probe_fp)

                full_meta = dict(rec["meta"])
                minimal_meta = {
                    key: full_meta[key]
                    for key in ("fingerprint", "lambda", "lambda_bin")
                    if key in full_meta
                }

                core_record = {
                    "train": rec["train"],
                    "query": rec["query"],
                    "solution": rec["solution"],
                    "meta": minimal_meta,
                }

                extras_payload: Dict[str, object] = {
                    "fingerprint": fp,
                    "meta": full_meta,
                }
                for key, value in rec.items():
                    if key not in {"train", "query", "solution", "meta"}:
                        extras_payload[key] = value

                f_core.write(json.dumps(core_record))
                f_core.write("\n")
                f_meta.write(json.dumps(extras_payload))
                f_meta.write("\n")

                produced += 1
                bin_counts[bin_key] += 1
                if progress is not None:
                    progress.update(1)

                for pair in rec["train"]:
                    seq_len = len(pair["input"])
                    train_length_sum += seq_len
                    train_length_min = min(train_length_min, seq_len)
                    train_length_max = max(train_length_max, seq_len)
                    train_length_count += 1
                    train_length_hist[seq_len] += 1

                query_len = len(rec["query"])
                query_length_sum += query_len
                query_length_min = min(query_length_min, query_len)
                query_length_max = max(query_length_max, query_len)
                query_length_count += 1
                query_length_hist[query_len] += 1

                lam_val = float(rec["meta"]["lambda"])
                lambda_sum += lam_val
                lambda_min = min(lambda_min, lam_val)
                lambda_max = max(lambda_max, lam_val)

                coverage_info = rec["meta"].get("coverage", {})
                cov_frac = float(coverage_info.get("fraction", 0.0))
                cov_windows = float(coverage_info.get("windows", 0))
                coverage_fraction_sum += cov_frac
                coverage_fraction_min = min(coverage_fraction_min, cov_frac)
                coverage_fraction_max = max(coverage_fraction_max, cov_frac)
                coverage_windows_sum += cov_windows
                coverage_windows_min = min(coverage_windows_min, cov_windows)
                coverage_windows_max = max(coverage_windows_max, cov_windows)

                family_counts[rec["meta"].get("family", "unknown")] += 1
                coverage_mode_counts[str(coverage_info.get("mode", "unknown"))] += 1
    finally:
        if progress is not None:
            progress.close()

    return {
        "written": produced,
        "bins": bin_counts,
        "path": str(path),
        "meta_path": str(meta_path),
        "fingerprints": accepted_fps,
        "probe_fingerprints": accepted_probe_fps,
        "stats": {
            "timeouts": timeout_count,
            "attempt_budget_skips": attempt_budget_skips,
            "count": produced,
            "lambda": {
                "sum": lambda_sum,
                "min": None if produced == 0 else lambda_min,
                "max": None if produced == 0 else lambda_max,
            },
            "coverage_fraction": {
                "sum": coverage_fraction_sum,
                "min": None if produced == 0 else coverage_fraction_min,
                "max": None if produced == 0 else coverage_fraction_max,
            },
            "coverage_windows": {
                "sum": coverage_windows_sum,
                "min": None if produced == 0 else coverage_windows_min,
                "max": None if produced == 0 else coverage_windows_max,
            },
            "train_sequence_length": {
                "sum": train_length_sum,
                "min": None if train_length_count == 0 else train_length_min,
                "max": None if train_length_count == 0 else train_length_max,
                "count": train_length_count,
                "hist": dict(train_length_hist),
            },
            "query_length": {
                "sum": query_length_sum,
                "min": None if query_length_count == 0 else query_length_min,
                "max": None if query_length_count == 0 else query_length_max,
                "count": query_length_count,
                "hist": dict(query_length_hist),
            },
            "families": dict(family_counts),
            "coverage_modes": dict(coverage_mode_counts),
        },
    }


__all__ = ["generate_dataset_jsonl"]
