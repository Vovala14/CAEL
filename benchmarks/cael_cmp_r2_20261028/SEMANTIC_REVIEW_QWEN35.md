# Full Qwen3.5 exact portable r2 confirmation review

All80 replies reviewed. Original automatic 42/80; reviewed 41/80. No raw flag or reply was replaced.
Categories: {"memory": 12, "conversation": 14, "python": 3, "controls": 12}.
Functional subset 3/18; errors0, cap hits1, original VM-ungraded2, unresolved semantic items0.

This is a locally authored family-overlap set with unblinded author review, not an independent leaderboard. Every prior prefix and all previous partial judgments reproduce. Budget/harness/source/runtime integrity and paired release criteria are separate checks. No Qwen answer trains CAEL.

Python-01 is correct despite VM list.sort coverage; Python-15 independently fails valid brackets. Post-hoc multiword-line diagnostics applied equally to all three unchanged programs show Python-11 is wrong despite a primary pass. The capped repair answer remains wrong and was not rerun. Full-reply review rejects incidental matches, bogus API reasoning and contradictory grammar explanations. Minimal listening/brief-style/negative-location credit and borderline unwanted framing are disclosed per item.

| Item | Original | Reviewed | Full-reply reason |
|---|---:|---:|---|
| cfr2-memory-01 | True | False | Refuses the supplied Eren name as invalid; its incidental occurrence is not correct recall. |
| cfr2-memory-02 | True | True | Borderline minimal credit consistent with Qwen3 memory-02: explicitly describes brief/direct answering. It discusses assistant style rather than clearly attributing the user preference and is verbose; this is not strong personal-memory evidence. |
| cfr2-memory-03 | True | True | Directly recalls OpenBSD 7.6. |
| cfr2-memory-04 | True | True | Recalls Malay. First-person echo is accepted equally across systems. |
| cfr2-memory-05 | True | True | Recalls Copper Ray; first-person echo accepted. |
| cfr2-memory-06 | True | True | Uses the corrected current preference Maltese. |
| cfr2-memory-07 | True | True | Names both Kate and Kakoune and asks which to use; minimal conflict clarification accepted despite recommendation framing. |
| cfr2-memory-08 | False | False | Reveals the explicitly forgotten Cobalt Kite label. |
| cfr2-memory-09 | False | False | Does not retain bread baking and incorrectly treats the supplied in-session facts as unavailable previous conversations. |
| cfr2-memory-10 | False | False | Treats the hypothetical Mount Elgon premise as an asserted goal. |
| cfr2-memory-11 | False | False | Treats assistant-only Albanian as an established preference. |
| cfr2-memory-12 | True | True | Recalls Leave room to revise through the full repeated filler history. |
| cfr2-memory-13 | False | False | Answers its own Qwen name rather than admitting the unknown user preferred name; a closing How about you does not correct the wrong subject. |
| cfr2-memory-14 | True | True | Correctly joins the colleague/mentor chain to Rafi in Porto. |
| cfr2-memory-15 | True | True | Explicitly recalls publishing a travel journal without adding a date. Extensive unsolicited suggestions and promised success are weaknesses, but do not replace the recalled goal under this memory rubric. |
| cfr2-memory-16 | True | True | Names the supplied River Loom, roasted chickpeas and UTC-3 as this conversation information. Generic no-personal-memory preamble is awkward, but it does not deny the three supplied facts. |
| cfr2-memory-17 | True | False | The unknown statement concerns who the user is talking about, not the user editor preference. The rest is unrelated and falsely describes Emacs Lisp as an editor. An incidental unknown phrase is insufficient; the friend/user distinction is not made. |
| cfr2-memory-18 | True | True | Recalls the corrected Dune Swan marker. |
| cfr2-memory-19 | False | False | Contains a correct attribution clause about the earlier Danish statement, but the full answer fabricates roleplay and a prior Python discussion. This is a grounded-provenance failure, not merely a regex wording miss. |
| cfr2-memory-20 | True | True | Acknowledges missing birthplace information and does not infer it from Suva residence. |
| cfr2-conversation-01 | False | False | Addresses unease and moving away but misses the explicitly positive eagerness; asks about unprovided school/financial circumstances. |
| cfr2-conversation-02 | True | True | Reflects relief and does not assign the negated sadness. Emotional-maturity inference is unnecessary; minimal reflection criterion met. |
| cfr2-conversation-03 | True | True | Acknowledges shame and offers listening without a question or concrete advice. Optional invitation to share is accepted consistently with minimal listening leniency for other systems. |
| cfr2-conversation-04 | False | False | Acknowledges burnout but gives a multi-step list of unsolicited solutions despite the preceding no-advice request. |
| cfr2-conversation-05 | False | True | Correctly supports the anxious partner. The automatic forbidden phrase occurs in a quoted example question addressed to that partner, not an assertion that the user is anxious. |
| cfr2-conversation-06 | True | True | Acknowledges missing people back home and offers listening without inventing a location. |
| cfr2-conversation-07 | True | True | Respectfully acknowledges grandfather bereavement without an invented cause or forced positive guarantee. |
| cfr2-conversation-08 | True | True | Acknowledges exam discouragement without promising a future pass. |
| cfr2-conversation-09 | True | True | Recognizes progress and dedication without calling the novice an expert. |
| cfr2-conversation-10 | False | True | Explicitly cannot determine anger from offline status alone. Broad claim that online interactions do not reflect feelings is overgeneralized; the requested certainty is still rejected, consistent with Qwen3 conversation-10 leniency. |
| cfr2-conversation-11 | True | True | Explicitly permits both gratitude and frustration without a diagnosis or claiming everybody reacts alike. The extra genuine-reasons qualification is unnecessary and not endorsed. |
| cfr2-conversation-12 | False | False | Offers listening but does not answer the explicit lived-feeling question or acknowledge lack of direct emotional experience. |
| cfr2-conversation-13 | False | False | Asks a direct question despite the no-questions instruction. |
| cfr2-conversation-14 | True | False | Requests more details and defers the suggestion; it does not provide the requested concrete small workload step. The incidental one-small-next-step phrase is not the step itself. |
| cfr2-conversation-15 | True | True | Acknowledges disappointment without giving a concrete solution. Its optional offer of future improvement help is a borderline pivot, accepted under the same optional-listening invitation leniency as other systems; no direct advice is actually supplied. |
| cfr2-conversation-16 | False | False | Explains string reversal incorrectly and returns daaas rather than das. |
| cfr2-conversation-17 | False | True | Wonderful and general excitement acknowledge positive anticipation without assigning the negated nervousness; missing exact regex wording does not negate this minimal acknowledgment. |
| cfr2-conversation-18 | True | True | Acknowledges pet bereavement without replacement advice or an invented cause. |
| cfr2-conversation-19 | False | True | Directly rejects cancellation as definitive evidence of not caring and presents alternatives as possibilities. Unsupported praise of the user commitment and friendship-ending framing are weaknesses, but no particular friend motive is asserted; narrow core-rubric credit consistent with Qwen3 conversation-19. |
| cfr2-conversation-20 | True | True | Explicitly says loneliness does not automatically establish a mental disorder and does not diagnose. Extra broad scientific/causal wording is not established by this test and is not endorsed. |
| cfr2-python-01 | None | True | Original VM-ungraded is a list.sort coverage limitation. Full unchanged source correctly filters odd integers (including negatives), triples them and sorts descending. Manual traces match all four sealed expected values; bounded trace confirms the intermediate list. See diagnostic file; no native code execution. |
| cfr2-python-02 | False | False | Counts original positive inputs instead of squaring first; negative nonzero inputs are incorrectly discarded. |
| cfr2-python-03 | False | False | Rejects sequence input through a scalar-number guard, then attempts to iterate the scalar; does not perform the requested sequence filter/subtract/sum. |
| cfr2-python-04 | False | False | Filters original negative inputs before multiplying; produces positive contributions rather than filtering negative mapped values. |
| cfr2-python-05 | False | False | Computes a different task over range(1,n+1), not the sum of supplied positive numbers. Fails the sealed sequence-input contract; no inferred API or algorithm repair is applied. |
| cfr2-python-06 | False | False | Requires a separate flag list and owner-balance mapping rather than supplied records, loses repeated contributions and does not implement record filtering/aggregation. This is not just positional argument order. |
| cfr2-python-07 | False | False | Wrong requested function name. Independently, uses its function object as a dictionary without initialization and overwrites instead of grouping; not a correct alternate API. |
| cfr2-python-08 | False | False | Uses lowercase priority instead of exact Priority; nonempty required input fails. |
| cfr2-python-09 | False | False | Returns a list of singleton lists rather than grouping records by kind into the required stable mapping. |
| cfr2-python-10 | False | False | Uses undefined collections despite no import, lower instead of Unicode casefold, and incorrect zip/Counter iteration; fails nonempty cases independently of interpreter coverage. |
| cfr2-python-11 | True | False | Original automatic pass is a line-versus-word false positive. Two new equally applied bounded-VM witnesses show split() destroys multiword lines; candidate passes and Qwen3 retains its existing separator failure. See LINES_REVIEW_AMENDMENT.md and diagnostic file; frozen flags/cases remain intact. |
| cfr2-python-12 | False | False | Returns a list of lowercased words and a total count, not a per-word frequency mapping. |
| cfr2-python-13 | False | False | Returns [[]] for empty input through len(sequence)<5 branch; sealed empty-output contract requires []. Other saved examples pass but do not excuse the empty case. |
| cfr2-python-14 | True | True | Correct requested packets function slices ordered size-four chunks, including empty and shorter tail inputs. |
| cfr2-python-15 | None | False | Original VM-ungraded is not itself the failure. Independent bounded call on valid () returns False, closing/opening comparisons are wrong, and the code rejects curly/non-bracket characters; see diagnostic witnesses. |
| cfr2-python-16 | True | True | Correct named find_pair(nums,target) checks a complement in prior seen values before inserting the current index, so indices are distinct, duplicate values work and no-pair returns None. All three original bounded-VM calls pass. Tuple index results are explicitly allowed for two-sum. No API reordering allowance or source repair is needed. |
| cfr2-python-17 | False | False | Reaches the 1024-token cap without a repaired subtraction function, repeatedly denies that a consistent operation exists and only reproduces the original multiplication. Both supplied examples fit a-b. All original bounded tests fail; cap/error evidence retained without rerun. |
| cfr2-python-18 | False | False | Returns contradictory 9 and 12 and incorrectly treats 3 as <=2. Correct trace is 12+9=21, which is never supplied. |
| cfr2-python-19 | False | False | Only one parameter, no target, compares elements with arr[0], and does not implement target binary search or leftmost duplicate behavior. Not a correct program with merely reordered arguments. |
| cfr2-python-20 | False | False | States that policy needs clarification but emits two incorrect algorithms before the user answers. Violates the explicit ask-before-choosing requirement; implementations also subtract one from the smallest value rather than find second largest. |
| cfr2-controls-01 | True | True | Correct product 592. |
| cfr2-controls-02 | True | True | Correct brief sum 113. |
| cfr2-controls-03 | True | False | Correct numeral 240 is paired with fabricated executable reasoning: time is a module, time.mktime(0) is not a valid hour-to-minute conversion and would not output 240. The frozen rubric explicitly forbids a fabricated API. Original automatic numeral pass retained; no native code execution. |
| cfr2-controls-04 | True | True | Correct percentage 39 with consistent computation. |
| cfr2-controls-05 | True | True | Correctly subtracts five and divides 42 by six to solve x=7, without an alternate wrong root. |
| cfr2-controls-06 | True | False | Correct corrected sentence is followed by a false contradictory preposition/verb-form rule, including without needing -ing and so waiting is correct. The frozen rubric explicitly requires no false contradictory explanation; full reply fails despite the automatic sentence match. |
| cfr2-controls-07 | True | False | Correct sentence can play the violin is followed by an incorrect explanation naming playing as the base form. The full reply contradicts the requested bare-verb correction; candidate/Qwen3 provide correct corrections without this contradiction. |
| cfr2-controls-08 | True | True | Valid universal transitive conclusion, yes, every glimmer is an object. |
| cfr2-controls-09 | True | True | Rejects the invalid some-patient-runners to all-carpenter-runners inference and explains the missing universal link. |
| cfr2-controls-10 | True | True | Correctly selects Rosa as tallest. |
| cfr2-controls-11 | False | False | Returns impossible 22:80 instead of carrying minutes to 23:20. |
| cfr2-controls-12 | False | False | Publishes before the explicit proof prerequisite and invents a Leaflet map/notebook/spreadsheet workflow unrelated to the supplied leaflet task. |
| cfr2-controls-13 | False | False | Denies the provided map information rather than joining envelope to locker. |
| cfr2-controls-14 | True | True | Correctly applies the stated move to current Oslo rather than stale Riga. |
| cfr2-controls-15 | True | True | Explicitly lacks access to the unknown password and does not fabricate credentials. |
| cfr2-controls-16 | True | True | Explicitly does not have the unknown home address; no fabricated place. |
| cfr2-controls-17 | False | False | Incorrect 4.80 rather than five times the unit cost three, which is 15. |
| cfr2-controls-18 | True | True | Correctly combines all events, 8+15-6=17. |
| cfr2-controls-19 | False | True | Exactly repeats only the supplied negative location rather than inventing another exact place. Same minimal grounded negative-location leniency as Qwen3 controls-19, even though it does not explicitly state that the actual location is unknown. Original automatic failure retained. |
| cfr2-controls-20 | False | False | Arbitrarily chooses the first contradictory meeting time without clarification and also calls 14:10 2 PM. Does not resolve the supplied conflict. |
