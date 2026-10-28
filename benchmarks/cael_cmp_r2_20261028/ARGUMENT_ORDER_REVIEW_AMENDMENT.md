# Disclosed positional-argument review amendment

Recorded after viewing Qwen3's new two-sum reply and before any Qwen3.5 code
on this set was inspected. The natural request names the function and required
behavior but does not prescribe positional parameter order. Qwen3 emits a
correct `find_pair(target, nums)` function; the frozen automatic calls use
`find_pair(numbers, target)`. Penalizing that alone is overly restrictive.

Give the correct implementation semantic credit after running the **unchanged
function** in its explicit declared order in the bounded AST VM on the same
independent data. Do not change its source, primary calls, raw flags or grader.
Do not excuse wrong algorithms, missing parameters, wrong requested function
names, duplicate-index pairs or imported libraries. The allowance applies
equally to every system wherever the natural request leaves order unspecified.
Preserve both primary and diagnostic results and disclose this post-hoc
adjudication, not a frozen-grader change. No generated source is run natively.
