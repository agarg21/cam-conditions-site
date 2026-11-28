# Bake-off humantest, 2026-11-28

Collected images: **5010** (day 1310, twilight 437, night 3263)

| pass | day | twilight | night |
|---|---:|---:|---:|
| blewett-pass | 33 | 12 | 84 |
| deadman-pass | 62 | 22 | 156 |
| donner-pass | 259 | 63 | 574 |
| echo-summit | 76 | 16 | 164 |
| fourth-of-july-pass | 60 | 24 | 156 |
| government-camp | 62 | 22 | 156 |
| lolo-pass | 62 | 22 | 156 |
| lookout-pass | 60 | 22 | 158 |
| lost-trail-pass | 62 | 22 | 156 |
| loup-loup-pass | 4 | 5 | 32 |
| monida-pass | 64 | 22 | 154 |
| santiam-pass | 64 | 22 | 154 |
| satus-pass | 10 | 10 | 62 |
| sherman-pass | 6 | 12 | 64 |
| siskiyou-summit | 66 | 20 | 154 |
| snoqualmie-pass | 66 | 24 | 167 |
| stevens-pass | 66 | 24 | 168 |
| teton-pass | 66 | 20 | 154 |
| tollgate | 62 | 22 | 156 |
| white-pass | 34 | 11 | 84 |
| willamette-pass | 66 | 20 | 154 |

## Human-check re-test 2026-11-28: sonnet, prompt v2 vs v3 (pass-v3), set 2026-11-28

100 images the owner answered. Cost $0.39 (Message Batches). Failed readings: {'v2': 0, 'v3': 0}.

| light | prompt | agrees (person sure) | says snow, person bare | says bare, person snow | model unknown, person sure |
|---|---|---:|---:|---:|---:|
| day | v2 | 48/59 (81%) | 7 | 1 | 3 |
| day | v3 | 46/59 (78%) | 11 | 1 | 1 |
| twilight | v2 | 10/14 (71%) | 4 | 0 | 0 |
| twilight | v3 | 10/14 (71%) | 4 | 0 | 0 |
| night | v2 | 9/18 (50%) | 8 | 0 | 1 |
| night | v3 | 8/18 (44%) | 8 | 0 | 2 |

Snow beside the road, lanes bare (person), 53 images; model says snow on lanes:
- v2: 17/53 (32%)
- v3: 21/53 (40%)

Day + twilight, person sure: answer only when confidence k >= threshold, else "can't tell":

| prompt | k >= | answered | right when answered | says snow, person bare |
|---|---:|---:|---:|---:|
| v2 | 0.0 | 70/73 | 58/70 (83%) | 11 |
| v2 | 0.6 | 66/73 | 58/66 (88%) | 7 |
| v2 | 0.7 | 46/73 | 45/46 (98%) | 0 |
| v2 | 0.8 | 40/73 | 39/40 (98%) | 0 |
| v2 | 0.9 | 9/73 | 9/9 (100%) | 0 |
| v3 | 0.0 | 72/73 | 56/72 (78%) | 15 |
| v3 | 0.6 | 65/73 | 54/65 (83%) | 10 |
| v3 | 0.7 | 40/73 | 39/40 (98%) | 0 |
| v3 | 0.8 | 34/73 | 33/34 (97%) | 0 |
| v3 | 0.9 | 6/73 | 6/6 (100%) | 0 |
