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

## Q6a update, 2026-11-28 02:45Z: prompt v2 and the Batch API
Sources: `2026-11-28-v2test-a.md` (300 images: Haiku 640, Sonnet 640 and 512 px, prompt `pass-v2`, Message Batches) and
`2026-11-28-v2test-b-opus.md` (Opus on v2 for a random 187 of them). Spend $1.21 + $0.96; **D2 total $8.97 of $10.**
- **Cost:** Sonnet v2 batch **$1.89 per 1,000** (v1.1 sync $5.98, −68%). Output 311 tokens per image (v1.1 529; the ≤150
  target was missed: the strict tool call itself costs ~280). Opus v2 batch $4.88, Haiku $0.18 per 1,000.
- **Agreement:** against v1.1 Opus, Sonnet v2 fell to 90% by day (v1.1 Sonnet 95%) with more snow-on-bare (13/117).
  Opus v2 moved the same way (94% day, 62% night vs Opus v1.1; it says "unknown" at night far less, 11% vs 26%).
  Against **Opus v2**, Sonnet v2 agrees **95% day, 93% twilight**, 74% night, missed snow 1/31: same level as v1.1.
  The drop was the v2 definitions, not Sonnet. Night under v2 is looser; keep night out of training labels for now.
- **Image size:** 512 px gives identical agreement and saves nothing (input is ~15% of cost). Keep 640.
- **Haiku cascade:** day 95% and half the Sonnet calls (~$1.14 per 1,000), but missed snow 2/31 vs Sonnet's 1/31. The
  owner's condition was "only if it keeps snow recall": not shown, so no cascade. Saving would be under $4 on 5,000.
- **Decision:** D8 labels = Sonnet 5.5, `pass-v2`, 640 px, Message Batches, day + twilight, 10% Opus audit. Before v3:
  re-tighten night "unknown" and check the human set (item 3 above) for the v2 "partly" (wet vs slush) boundary.
