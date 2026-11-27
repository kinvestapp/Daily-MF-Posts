# Daily-MF-Posts

Automated social content for K-Invest.app (ARN-366802).

## v1 (live): `generate_and_render_illustrated.py` + `publish.py`
Single notebook-style image, daily cron (`daily-post.yml`).

## v2 (in progress): `agent_v2/`
Agent that writes, checks, publishes and (from Phase 2) learns from results.

- `hooks.py`: positive-framed engagement hook library (no lust, no hard fear/anger/greed)
- `content.py`: Claude writes a 3-slide carousel + caption for one hook and topic
- `compliance.py`: linter the agent can never relax (banned phrases, required footer)
- `render.py`: modern fintech theme, HTML to 1440x1800 JPEG, bundled Inter font, layout QA
- `pipeline.py`: hook -> write -> lint -> render -> QA gate -> metadata JSON
- `../publish_v2.py`: Instagram carousel + Facebook multi-photo post; stores media ids for the learner
- `.github/workflows/daily-post-v2.yml`: manual trigger (`publish` input) until approved

Offline preview (no API keys): `python -m agent_v2.pipeline --sample`

Roadmap: Phase 2 insights logging, Phase 3 learner/strategist, Phase 4 Reel + royalty-free audio, Phase 5 trend scan.

## How the agent runs (conservative on API credits)
- **Daily** (`daily-post-v2.yml`): takes the next post from `content_queue/` and publishes it. No API call. Only if the queue is empty does it write one post (max 2 calls).
- **Weekly** (`weekly-planner.yml`): the strategist (plain code) reads `data/metrics.jsonl`, ranks hooks by score per 1,000 reached and plans the next 7 posts (70% best hooks, 30% new tests). One call writes the batch, one cheap call reviews it, one call rewrites only failures. At most 3 calls.
- **Guardrails** (`agent_v2/llm.py`): per-run call cap, monthly budget cap (`MONTHLY_BUDGET_USD`, default $3, estimated from reported tokens), every call logged in `data/api_usage.jsonl`. Check real spend in the Anthropic Console.
- **Models**: writer `WRITER_MODEL` (default Sonnet, falls back to Haiku), reviewer `REVIEW_MODEL` (default Haiku).
- Posts in `content_queue/*.json` are used in filename order; a post counts as used once `public/posts_v2/<date>.json` records its `queue_id`.
