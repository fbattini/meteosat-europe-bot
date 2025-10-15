## Meteosat Europe Bot – Review Notes

### Findings
- ~~`generate_and_post.py:83` — `tweepy.Client` lacks `media_upload`; current code raises `AttributeError`. Replace with `tweepy.API` upload or switch fully to the v1.1 helper before tweeting.~~ (resolved; see Progress)
- ~~`generate_and_post.py:47` — Extraction/frame folders accumulate old `.nat` and `.png` files. Cleaning the directories (or using a temp dir) avoids polluted GIFs on reruns.~~ (resolved; see Progress)
- ~~`generate_and_post.py:23` — `datetime(...)` is naive; EUMETSAT expects timezone-aware timestamps. Use `datetime(..., tzinfo=timezone.utc)` to avoid off-by-one requests.~~ (resolved; see Progress)
- ~~`generate_and_post.py:27` — `bbox` and `sort="start,time,1"` parameters do not match documented SDK usage; verify against official examples to prevent empty result sets.~~ (validated against prior working script)
- ~~`.github/workflows/post.yml:21` — Bare `pip install` is brittle for heavy deps. Upgrade `pip` and add caching to keep the daily job reliable.~~ (addressed in workflow)

### Questions / Risks
- Keeping all granules maximises fidelity but may impact runtime and disk use; monitor workflow duration (~15–20 min currently) and adjust if the runner approaches its 45-minute timeout or storage limits.
- Current automatic fallback posts a text update after three hourly attempts; confirm if that messaging is sufficient or if we should escalate (e.g., notify maintainers).

### Suggested Improvements
- ~~Add structured logging and wrap major stages with explicit error handling so Action logs stay readable.~~ (implemented; see Progress)
- ~~Implement a fallback window (e.g., step back hour-by-hour or retry later) when no products are returned.~~ (implemented; see Progress)
- ~~Remove the `downloads/` workspace once posting completes to keep runs idempotent.~~ (implemented; see Progress)
- ~~Update the caption to include the agreed credit line (e.g. “Data © EUMETSAT”) alongside hashtags.~~ (caption now includes the credit line)
- ~~In the workflow, add `timeout-minutes`, `concurrency`, and caching (via `actions/setup-python` or `actions/cache`) to improve stability.~~ (implemented; see Progress)

### Progress
- Updated `generate_and_post.py` to upload media via OAuth 1.0a (`tweepy.API`) and then post with the v2 client using the required credit line.
- `extract_and_generate` now wipes the `extracted/` and `rgb_frames/` directories on each run to avoid stale files.
- `download_latest_data` now uses timezone-aware UTC datetimes for the search range passed to EUMETSAT.
- Confirmed the existing `bbox` string and `sort="start,time,1"` parameters align with the known-working reference script.
- Replaced `print` statements with structured logging, added top-level error handling, and removed emoji from console output and captions.
- Added a fallback search that retries with up to two additional one-hour offsets when no products are returned initially.
- On successful runs the `downloads/` directory is now removed to keep the workspace clean.
- The GitHub Actions workflow upgrades `pip`, caches dependencies, enforces a timeout, and prevents overlapping runs.
- Retain all available granules for GIF generation as per current plan, and post a text update when no imagery is available after three hourly attempts.
- Sequentially extract and process each archive in temporary directories, deleting zips/frames as we go to stay within GitHub runner disk limits.

### Notes from X API Docs Review
- Ensure posting uses OAuth 1.0a user context, per X API v2 “manage Posts” guidance; v2 `POST /2/tweets` requires signed requests with API key/secret plus access token/secret.
- Sample flow uses `requests-oauthlib`’s `OAuth1Session`; for automation we can reuse stored user tokens and skip the interactive PIN step.
- Media upload still requires the v1.1 endpoint; after uploading, include the returned `media_id` in the v2 Tweet payload.
- The `/2/tweets` endpoint supports rich payloads (polls, communities, cards) but we only need `text` plus `media.media_ids`; authentication header must carry the OAuth 1.0a user context rather than a simple bearer token from OAuth 2.0 client credentials.
