# Line-versus-word semantic review witness

Full review of Qwen3.5 Python-11 found `text.split()` rather than the requested
line splitting. Every sealed primary example happens to contain at most one
word per nonempty line, so the wrong implementation passes those examples.
The original automatic flag and every original call remain unchanged.

After inspecting that reply, two diagnostic inputs with multiword lines were
authored and applied to **all three unchanged programs** in the same bounded
AST VM. This is disclosed post-hoc review evidence, not an amended frozen
grader or newly unseen evaluation. No source was executed natively or repaired.
See code_review_diagnostics_20261028_1355.json for sources' hashes, exact calls,
expected values, full bounded traces and preserved original flags.

For `a b\n c d`, the requested result is `a b :: c d`. CAEL returns it; Qwen3
returns `a b::c d` (already failed the original exact separator); Qwen3.5
returns `a :: b :: c :: d`. The second diagnostic reproduces the distinction.
Thus CAEL and Qwen3 judgments stay unchanged; Qwen3.5's original automatic pass
is a semantic failure. This equally applied witness concerns the frozen
natural-language line/trim/join contract. Do not train on it or alter the
sealed primary questions/cases/source to force the publication condition.

The same diagnostic file separates two VM coverage cases: Qwen3.5 Python-01's
list.sort is unsupported by this VM, but its unchanged filter/triple/sort
implementation is correct by full code inspection and manual traces. It earns
semantic credit with that coverage limitation disclosed. Python-15 is
independently wrong: the unchanged function returns False for valid `()` in
the bounded VM, compares closing brackets directly with opening brackets,
and rejects curly brackets and non-bracket characters. Its failure is based
on behavior/code, not merely its original VM-ungraded flag.
