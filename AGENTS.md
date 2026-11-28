# Agent instructions: Conditions Now (conditionsnow.com)

## Product
Live mountain-pass and road conditions in one place: the official DOT report, the DOT's own camera images (served from our
copies), the NWS forecast, and soon our own reading of each camera image. Free site first; revenue later from search traffic
(affiliate, ads) and small data sales. The moat is a cheap, accurate camera-reading model (labels and training live in the
private repo `agarg21/cam-conditions-engine`; raw images and per-image labels live in the private HF dataset
`agarg20/conditionsnow-cams`). Plan and decisions: Claude project docs `claude/conditionsnow-plan.md` and
`claude/design-ml-costs.md` (summarised in this repo's `ops/STATE.md`).

## What users ask (search intent, 2026-11-27)
Right now / today; open or closed; snow on the road or falling; chains or traction rules; cameras; accidents and traffic;
tomorrow / this weekend; elevation, drive time, map; summer: smoke, fires, construction. Pages answer these in that order,
with "unknown" rather than a guess. Details: `docs/research/` and `docs/bakeoff/`.

## Repo map
- `scripts/collect.py` (every ~15 min via `.github/workflows/collect.yml`, self-chaining), `scripts/build_site.py`,
  `scripts/upload_hf.py`, `scripts/discover.py` (+ discover.yml), `scripts/bakeoff.py` (+ bakeoff.yml; trigger by pushing
  `ops/bakeoff-request.json`).
- `config/passes.json` (ready passes), `config/SOURCES.md`, `docs/design/design-system.md` (tokens; no raw colours or sizes).
- Secrets: ANTHROPIC_API_KEY, WSDOT_ACCESS_CODE, HF_TOKEN, IDAHO511_KEY, ODOT_KEY. Never print, commit or move them.

## Operator cycle (scheduled task: every 2 hours from 2026-11-27; hourly 2026-11-28 to 2026-12-01 for the expansion sprint, D10)
1. Lock: if `ops/STATE.md` `run:` is not `none` and started < 55 min ago, stop. Older = previous run died; take over its item and
   say so. From 2026-12-01 00:00Z the task still fires hourly: on odd UTC hours, stop at once (back to every 2 hours).
2. Claim: set `run:`, commit "ops: claim run", push fast-forward.
3. Pick: continue `active:` or take the first unblocked item in `ops/QUEUE.md`. Live-site defect first. Never invent work.
4. Do one bounded piece (about 45 min). Expansion sprint (D10): adding passes from one already-approved feed counts as one
   piece, up to 8 passes per run (verify every camera image and status source; same QA). Check the live site after any site change (`release` = the collect workflow
   deploys on push; confirm the change on https://conditionsnow.com). Run `python3 -m py_compile scripts/*.py`, a local
   `build_site.py` against a sample run, and Playwright at 390 and 1280 px (no horizontal overflow, no console errors)
   before pushing site changes.
5. Record: update QUEUE (≤15 items), STATE (≤6 KB: active, holds, last run; add new public URLs to `to_index:` (D12); set `run: none` when done), append ≤6 lines to `ops/runs/YYYY-MM.md`,
   real questions to `ops/OWNER.md` as yes/no with a recommendation. Commit, push fast-forward
   (if rejected: `git pull --no-rebase` once; bots also commit docs/discovery and docs/bakeoff).
6. Final message (owner's phone): ≤4 short lines: what shipped (URL), what was learned (one number), any owner question.

## Rules that never relax
- External actions need an Approved row in `ops/OWNER.md`: emails, outreach, posting, accounts, sign-ups, form submissions,
  Search Console changes, purchases, paid API spend beyond approved budgets, new data-source terms.
- Data sources: credit every agency; ODOT terms: mirror images (never hotlink) and keep ODOT's disclaimer on Oregon pages and
  /sources/. Poll keyed APIs within their limits (Idaho 511: 10 calls/60 s). Never bypass blocks, robots.txt or CAPTCHAs.
- Honesty: never present a model reading as an official report; label it "our reading" with its confidence. Never invent
  conditions, closures, elevations or numbers; every figure has a source and date. "Unknown" beats a guess.
- The repo is public: no secrets, no per-image labels, no personal data. Aggregates only in `docs/`.
- Git: never force-push, rebase, reset or rewrite history. Do not create, change or delete scheduled tasks.
- Never use the owner's computer or browsers (no remote-device, Claude in Chrome or built-in browser tools).
