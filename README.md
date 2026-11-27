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
