# Source-backed short answers — local worker update

This updates the local shared worker without changing the published 0.2.1 archive or tag. The newer remote chat brain on the other computer remains unavailable here.

## Training and behavior

- News routing: 584 authored request paraphrases. Held-out intent 132/132 and topic extraction 36/36; separate authored confirmation 20/20. These are controlled paraphrase tests, not independent user evaluations.
- News relevance: integer token-count Naive Bayes trained on 3,669 Wikipedia current-events entries from April–August 2026. September development labels: 478/641 (74.6%); October confirmation labels: 194/266 (72.9%). Labels are Wikipedia section headings. The model cannot establish the truth of an article.
- Weather, sports and factual-request routing: 752 authored examples, with classical averaged linear classifiers and location/topic slot taggers. Combined intent-and-slot holdout: 24/25. One unseen rugby-headline request missed the sports-specific class; the separate news router handles that request correctly. No large chat language model was retrained.
- News responses use up to three matching headlines or dated summaries, usually within 75 words. Topic filtering, deduplication, requested dates and source links prevent unrelated world-news digests from filling an empty topic result.
- Weather requests accept locations before/after weather terms and rain/snow/wind questions. MET forecasts include an explicit UTC forecast time; precipitation quantities refer only to the stated next one/six hours, not the entire day. Missing locations prompt for a city. A forecast is not an observed measurement.
- Sports news uses the same topic and source controls. Live scores, fixtures and standings are explicitly unavailable because no verified free commercial feed is connected. Empty topic coverage remains an empty result rather than an invented score or unrelated story.
- Common factual questions have direct Wikidata answers for capitals, countries, birth dates and dated population figures. Dates respect source precision; old population figures are dated rather than called current. Other encyclopedic queries use at most two extractive sentences / 55 words. This does not provide arbitrary multi-step reasoning or a complete product-support FAQ system.
- Links appear separately from the short reply; licence and attribution details remain available in the UI. Each user's result ownership and conversation context remain isolated.

## Sources and evidence

Weather: MET Norway (CC BY 4.0); locations and structured facts: Wikidata (CC0); encyclopedic excerpts and classifier training text: Wikipedia (CC BY-SA 4.0); headline discovery: GDELT terms. Publisher bodies/images are not fetched. See `INTERNET_SOURCES.md` for the provider audit and scope limits.

Training reports: `models/cael-news-policy-v1/report.json`, `relevance_report.json`, and `models/cael-request-policy-v1/report.json`. Frozen training examples and live verification logs are under `research/news_policy_022/` and `research/request_policy_022/`.

Validation: 74 automated tests pass, and the public client JavaScript parses. Live text-source checks exercised Paris weather, Tel Aviv precipitation, Norway's capital, Marie Curie's birth date, a dated Canadian population, an encyclopedic definition, unavailable Liverpool fixtures and empty rugby news coverage. Public worker checks are recorded separately after activation.

No private training pictures were viewed or used in this text-routing work. All new image training in this update uses the separate synthetic dataset described in `IMAGE_PROGRESS_0_2_2.md`.
