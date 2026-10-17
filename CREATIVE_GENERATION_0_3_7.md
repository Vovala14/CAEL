# Prompt and story generation 0.3.7-r2

Selected on 2026-10-17 in `research/active_models.json` and loaded by the shared unified worker.

Use **Auto**, **Prompt writer** or **Story** on the existing site. Auto recognizes these examples:

- `Write three image prompts for a violet submarine beneath sea ice; no people; 16:9`
- `Write a story prompt about a librarian who finds a city inside a book`
- `Write an assistant prompt for reviewing Python code; return exactly three bullets`
- `Tell a story about an astronaut finding a compass in a space station`
- After that actual story: `Who found the compass?` or `Where is the compass?`

Prompt writer returns reusable text. It accepts arbitrary brief text, preserves constraints and code formatting, and can provide one to five distinct seeded variants. These are sampled from fifteen authored structures (five for each type). It adds general organization and quality instructions; it does not deeply understand or rewrite every brief.

Stories use the existing bounded integer CA planner, world memory and grammar. The vocabulary now contains 22 actors, 23 objects, 15 places and seven skills. The eight plot goals remain finding, sharing, helping, losing, visiting, resting, learning and comforting. Stories are short and formulaic. Long fiction, arbitrary genres, arbitrary names and multiple simultaneous goals are not supported. Requests with multiple supported objects, settings or incompatible goals are rejected instead of silently dropping them.

No neural networks or transformers were added. The current language, image and lookup-policy selections remain unchanged. The thinking animation remains available. No private photos or conversations were used, and image generation was not run.

See `research/creative_037/REPORT.md` for fitting, validation, hashes and operational evidence. This work does not establish a new leaderboard result.
