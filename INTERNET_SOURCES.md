# Live internet lookups and commercial use

The reasoning data audit is in `REASONING_PROGRESS_0_2_4.md` and
`licenses/REASONING_DATA_NOTICES.md`: PrOntoQA (Apache 2.0), publisher-licensed
bAbI (CC BY 3.0), and evaluation-only BIG-bench logical deduction (Apache 2.0).
Only selected repository/download paths were added to the transport. Reasoning
uses no network requests. Required credits/notices are retained; sources with
unclear data permissions were excluded.

The local-first text update is documented in `LOCAL_KNOWLEDGE_0_2_3.md`: 10,025
unique Wikipedia articles / 349,568 indexed passages, trained question/passage
selection, and a bounded persistent store for canonical public reference text.
Stable questions can now avoid the network; current questions and explicit web
search requests still use the reviewed providers below. Snapshot excerpts keep
CC BY-SA 4.0, contributor credit and specific revision links. This does not add
arbitrary-site fetching or change provider commercial-use restrictions.

Reviewed 2026-10-16. This covers the active local source code and the shared
0.2.1 worker. The separate `/workspace/factfetch/` and chat worker on the other
computer were not available to inspect or modify. Earlier research notes about
that machine are not evidence of what this local worker runs.

The shared worker now connects factual questions to Wikimedia, weather to MET
Norway, headlines to GDELT, and unknown emoji words to licensed references.
This is a retrieval layer around the existing models. Portrait and general
picture models still generate from their trained parameters; they do not search
the web for arbitrary photographs or learn arbitrary picture subjects online.

| Active provider | Purpose | Free commercial permission and conditions |
| --- | --- | --- |
| [Wikidata](https://www.wikidata.org/wiki/Wikidata:Copyright) | Structured current officeholders, location coordinates, existing name checks | Structured data CC0. Identifying User-Agent and shared rate limiting. |
| [Wikipedia](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use) | Factual excerpts, spell-check titles, current news digest | Text CC BY-SA 4.0. Article link, contributor credit, licence link and transformation notice accompany excerpts; share-alike retained. |
| [MET Norway](https://api.met.no/doc/License) | Weather forecasts | CC BY 4.0/NLOD 2.0. Credit MET Norway, link licence, label formatted forecast and UTC time. Identifying User-Agent, backend proxy, cached responses, expiry headers and conditional requests. [API terms](https://api.met.no/doc/TermsOfService). |
| [GDELT](https://www.gdeltproject.org/about.html#termsofuse) | Recent indexed headlines and links | Datasets permit commercial use without fee; cite and link GDELT. No publisher article bodies or photographs are downloaded or relicensed. |
| [OpenMoji](https://github.com/hfg-gmuend/openmoji) | Emoji references | CC BY-SA 4.0. Contributor credit, source/licence links, transformation notice and share-alike for derived outputs. |
| [Twemoji graphics](https://github.com/jdecked/twemoji#license) | Emoji references | CC BY 4.0. Twitter/contributor credit, source/licence links and transformation notice. |
| [Emojitwo / EmojiOne 2.2](https://github.com/EmojiTwo/emojitwo#emojione-2x-artwork-license) | Emoji references | CC BY 4.0. Credit Ranks.com and the Emojitwo community; link original/fork, source and licence on the result page. Modern EmojiOne/JoyPixels artwork is not fetched. |
| [Microsoft Fluent Emoji](https://github.com/microsoft/fluentui-emoji/blob/main/LICENSE) | Emoji references | MIT. Copyright and full notice retained in `licenses/LICENSE-Fluent-Emoji-MIT.txt`, exposed through the shared worker's sources page. |
| [Wikimedia Commons](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia) | Icon fallback for new emoji words | Per-file filtering before download: only explicit CC0, public domain and CC BY. Creator/file attribution preserved. Unknown, NC and ND licences rejected. |
| [FrequencyWords](https://github.com/hermitdave/FrequencyWords) | Existing assistant spell-check word frequencies | Content CC BY-SA 4.0 (code MIT). Existing `data/spell/SOURCES.md` records credit. |

The new fetch transport permits only these reviewed provider hosts and selected
GitHub repositories. Redirects must stay within the reviewed list. It verifies
TLS, uses a shared bounded cache, spaces requests per host and observes provider
rate-limit backoff. It never sends private training photos or conversation
history to providers; it sends the lookup subject/location only. Queries can
still contain personal information a visitor types into a lookup.

## Restricted or unverified sources

- [Open-Meteo free API](https://open-meteo.com/en/terms): non-commercial only.
  Weather uses MET Norway instead; geocoding uses Wikidata.
- [Jolpica F1](https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md):
  CC BY-NC-SA 4.0, commercial use requires contact. Not permitted by the local
  transport. No verified equivalent free commercial live F1 feed is installed.
- [TheSportsDB](https://www.thesportsdb.com/docs_terms_of_use.php): free usage
  is described for development projects; app-store publication requires a paid
  subscriber. No unrestricted free commercial deployment assumed. Not used.
- [CoinGecko](https://www.coingecko.com/en/api/pricing): commercial licences
  are listed for paid tiers, not Demo. Not used. Live prices are explicitly
  unavailable instead of being answered from old encyclopedia data.
- BBC RSS and DuckDuckGo Instant Answer: free commercial reuse was not
  established in this review; they are outside the provider list. GDELT and
  licensed Wikimedia text cover news/general lookup instead.
- The unused Openverse function was removed from the active emoji fetcher.
  Mixed-licence general image search is not a fallback.

Historical backup/release files are preserved and are not part of the shared
worker's imports. The external remote worker and its fetch APIs cannot be
audited or changed until their source is available locally. This source review
does not change CAEL's software licence or establish rights to private portrait
training data.

## Runtime and verification

The shared link's `/sources` page retains licences and credits. Responses expose
their actual providers in `sources` and the result details. Internet failures
return an explicit unavailable result. GDELT timed out during live checks;
world news then used Wikipedia's current digest, clearly labelled. Topic news
returns unavailable when its feed fails.

New emoji priors are saved separately under `data/emoji_online_021/` and the
base release bundle remains immutable. The actual live check learned phoenix
from OpenMoji and Twemoji, preserved both licences, and generated a guarded CA
output. No private training photos were viewed.

The 58-test suite passed, including licence rejection before image download,
provider/redirect restrictions, caching, rate-limit backoff, source attribution,
weather routing, incumbent term filtering and shared-session isolation.
