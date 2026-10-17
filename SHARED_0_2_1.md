# Shared CAEL 0.2.1 worker

Current link: https://cable-round-strange-performing.trycloudflare.com

The installed 0.2.1 bundle is running through `cael_unified.public_worker` on
127.0.0.1:8766. It includes the installed legacy chat fallback, helper, emoji
engine, portrait model and general picture model. The newer worker on the other
computer is not part of this service.

Anyone with the link can open it without signup. There is no application limit
on the number of visitors. Four chat workers and one image worker process jobs,
with a shared capacity of 128 pending or active jobs. When that capacity fills,
the browser retries. Image processing does not occupy the chat worker pool.
These are workload limits, not a fixed number of allowed users.

Each browser has a signed, HttpOnly session cookie. Conversations stay in that
browser tab and are supplied only to its own request. Job results and PNGs
require the owning session. Completed request inputs are discarded; generated
files and job results expire after one hour. Losing the cookie loses access to
those results. The service does not serve arbitrary local files or training data.

The public address is a temporary Cloudflare Quick Tunnel. Keep the PC awake,
connected to the internet, and both background processes running. Restarting a
tunnel changes its address. Cloudflare currently permits 200 simultaneous
in-flight HTTP requests per Quick Tunnel and provides no uptime guarantee:
https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

To start or reuse this service, double-click `START_SHARED_0_2_1.bat`. It prints
the active URL. Runtime process IDs, the latest link, logs and verification are
under `research/shared_021/`; do not publish that directory or its session key.
The existing local UI on port 8765 is left running independently.

Internet lookups were subsequently enabled for facts, weather, news and new
emoji words. See `INTERNET_SOURCES.md` for the reviewed providers, licence
conditions, verification and unavailable live-price/sports feeds.

Verification on 2026-10-16 passed public HTTPS, actual chat/image/emoji jobs,
cross-session denial for results and PNGs, and 32 independent local visitor
sessions exercised by 16 concurrent test clients. Four worker tests cover signed
sessions, job ownership, queue backpressure and chat during image work. No
private training photos were viewed.

These sharing additions are local changes; they do not replace the published
0.2.1 release assets.
