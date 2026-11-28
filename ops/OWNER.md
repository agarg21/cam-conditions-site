# Owner decisions and questions (Conditions Now)

## Approved
- D1 (2026-11-27) Operator runs every 2 hours in a cloud session; one item per run.
- D2 (2026-11-27) Labeling bake-off: Anthropic API spend up to USD 10 total (300 images × Haiku/Sonnet/Opus ≈ USD 4).
- D3 (2026-11-27) Adding passes from sources we already have keys/terms for (WSDOT, Caltrans, ODOT, Idaho 511) is fine.
- D4 (2026-11-26) Keyword research via the family-tripwise DataForSEO workflow under its D8 budget: owner-approved per batch
  in chat only (batches 2026-11-26 and 2026-11-27 done). Further batches: ask here first.

- D5 (2026-11-27) New states Iowa, Montana, South Dakota, Nebraska: a state road-conditions page each (IA I-80/I-35,
  SD I-90/Black Hills, NE I-80, MT statewide) plus Montana passes (Bozeman, Homestake, MacDonald). Use only keyless public
  feeds; read each state's terms/disclaimer first and follow them (credit, mirroring, disclaimer). If terms forbid reuse or
  are unclear, stop that state and ask here.
- D6 (2026-11-27) B2B validation: draft a pitch with sample pass alerts for 5–10 ski shuttles / small fleets once camera
  readings work. Drafts only; the owner sends.

- D7 (2026-11-28, owner "yes to all") (a) Montana: build with unmodified, credited MDT images under MDT terms §4.
  (b) Permission requests sent 2026-11-28 01:30Z from apoorv20@gmail.com, cc hello@: Iowa (511feedback@iowadot.us),
  Nebraska (NDOT.OperationsSOC@nebraska.gov), South Dakota (dot.communications@state.sd.us). Each said the site is free
  and may later show ads. IA/NE/SD stay off until a written yes arrives (owner forwards replies).

- D9 (2026-11-28, owner "yes, lets do this") Claude readings live on the top 5 passes once the owner's 100-image check
  (review/2026-11-28, done in the "Camera check" artifact) shows Sonnet agrees with him on lane snow ≥90% in daylight.
  Sonnet, prompt pass-v2, daylight + twilight only, hourly, 2 cameras per pass; budget up to USD 15/month. Shown as
  "Our reading" with confidence beside the official report, never replacing it.
  Update 2026-11-28 16:55 IST, owner "lets build it": live with prompt pass-v4 (center line first) and the k>=0.7 gate
  (owner check 39/40 right at k>=0.7); no carry-forward of old readings (searchers are hours away): "Can't tell from cameras
  right now" + "Last clear look", plus snow-falling and 3 h trend lines. Passes: Snoqualmie, Stevens, Donner, Teton, Santiam.

- D10 (2026-11-28 16:18Z, owner) Expansion sprint: operator runs hourly until 2026-12-01 (then every 2 hours again), and may add
  up to 8 passes per run from one already-approved feed (D3 sources and Montana under D7a). Goal: many more pass pages within
  2 days so they start indexing before the storms; then debug readings live in storms.
- D11 (2026-11-28 16:18Z, owner) Camera readings budget raised from USD 15 to USD 40/month (replaces D9's cap) until our own
  model takes over: read every pass, every 3 h when calm, hourly when snow is forecast (NWS) or seen falling; Opus audit and
  storm checks (Q14) count inside it.

## Not approved (ask first)
- Any email or outreach (CDOT reply handling, B2B pitches), new sign-ups, Search Console changes, paid spend beyond D2.

## Open questions
- D8 (2026-11-28, owner) Training labels APPROVED with the Q6a optimizations, no second vendor: Batch API, prompt v2
  with short output, Haiku pre-screen only if the test shows it keeps snow recall. Up to USD 40 total (expect ~$8);
  Sonnet labels ~5,000 images, Opus audits ~500. No re-ask needed unless the measured cost would pass $40.

