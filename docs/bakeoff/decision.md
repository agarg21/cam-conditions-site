# Bake-off decision (Q1), 2026-11-28

Source: `docs/bakeoff/2026-11-28-run.md` (300 images: day 150, twilight 50, night 100; prompt `pass-v1.1`; Opus 5.5 as
reference). Agreement with Opus is **not** accuracy: Opus is a stronger reader, not ground truth. No reading is shown on the
site yet; nothing here changes a public page.

## Cost (real API usage)
| model | per 1,000 images | 5,000 images | median secs |
|---|---:|---:|---:|
| Haiku 5.5 | $0.47 | ~$2.40 | 4.3 |
| Sonnet 5.5 | $5.98 | ~$30 | 3.0 |
| Opus 5.5 | $15.68 | ~$78 | 6.7 |

D2 spend so far: $0.08 (first run: Sonnet/Opus rejected forced `tool_choice`, HTTP 400) + $0.08 probe + $6.64 run = **$6.80 of $10**.

## Road surface (the field drivers care about most)
Exact 7-way agreement with Opus: Sonnet 79%, Haiku 68%. Most disagreement is dry vs wet pavement (Sonnet called 34 of 68
Opus-"dry" images "wet"). Collapsed to **bare / snow on lanes (partly or covered) / unknown**:
- Sonnet **93%** (280/300). Snow on bare lanes: 4 of 197. Missed snow (called bare): 3 of 36.
- Haiku **80%** (239/300). Snow on bare lanes: **36 of 197 (18%)**. Missed snow: 0 of 36 (8 went to unknown).
Haiku over-calls snow; Sonnet tracks Opus closely. Night: Opus says "unknown" for 63% of road surfaces, as the prompt asks.

## Field by field (all light; day in brackets)
- Reliable enough to train on: `image_usable` (Sonnet 92% [100%]), `traffic` (88% [95%]), `visibility` by day (93%),
  `roadside_snow` (81% [85%]), road surface collapsed as above.
- Base-rate only, cannot judge yet: `incident_visible`, `plow_or_chainup`, `closure_visible` (272/263/272 of 300 "none";
  3 plows, no crashes, no gates). Keep as rare-event fields; never show on the site until a targeted check finds real cases.
- Reword: `precip_falling`: Opus "unknown" on 67% of images and 59% of daytime ones; a still frame rarely shows falling
  snow. v2: `snow_falling_visible` yes / no / unknown, "no" when the air looks clear and no flakes or streaks show.
- Drop for winter: `smoke_haze` (Opus unknown 41%, no smoke in sample). Bring back for summer.
- Night `visibility`: Sonnet agrees 33%; models disagree on what "reduced" means in the dark. v2: "unknown" unless lights
  show the road ahead.
- Overlay temperature: all three read it on ~76 images; use as a check, not a reading.

## Decision
1. **Labeler for training data: Sonnet 5.5**, with the collapsed road-surface classes, on day and twilight images first.
   Opus re-labels a random 10% as an audit. Haiku is not good enough as a labeler (18% false snow).
2. Prompt v2 (`pass-v2`): collapse road surface to bare / partly_snow / snow_covered / ice_visible / unknown (wet kept as
   a separate yes/no/unknown), reword precip as above, drop smoke in winter, tighten night visibility.
3. Before any reading reaches the site: a human-checked set of ~100 images (owner or operator) to measure Sonnet and Opus
   against people, not against each other.
4. Spend for ~5,000 Sonnet labels + 500 Opus audit (~$38) is beyond D2: asked as D8 in `ops/OWNER.md`.
