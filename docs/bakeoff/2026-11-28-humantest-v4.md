# Bake-off humantest, 2026-11-28

Collected images: **5493** (day 1310, twilight 437, night 3746)

| pass | day | twilight | night |
|---|---:|---:|---:|
| blewett-pass | 33 | 12 | 95 |
| deadman-pass | 62 | 22 | 178 |
| donner-pass | 259 | 63 | 651 |
| echo-summit | 76 | 16 | 186 |
| fourth-of-july-pass | 60 | 24 | 178 |
| government-camp | 62 | 22 | 178 |
| lolo-pass | 62 | 22 | 178 |
| lookout-pass | 60 | 22 | 180 |
| lost-trail-pass | 62 | 22 | 178 |
| loup-loup-pass | 4 | 5 | 43 |
| monida-pass | 64 | 22 | 176 |
| santiam-pass | 64 | 22 | 176 |
| satus-pass | 10 | 10 | 84 |
| sherman-pass | 6 | 12 | 86 |
| siskiyou-summit | 66 | 20 | 176 |
| snoqualmie-pass | 66 | 24 | 189 |
| stevens-pass | 66 | 24 | 189 |
| teton-pass | 66 | 20 | 176 |
| tollgate | 62 | 22 | 178 |
| white-pass | 34 | 11 | 95 |
| willamette-pass | 66 | 20 | 176 |

## Human-check re-test 2026-11-28: sonnet, prompts v4, set 2026-11-28

100 images the owner answered. Cost $0.21 (Message Batches). Failed readings: {'v4': 0}.

| light | prompt | agrees (person sure) | says snow, person bare | says bare, person snow | model unknown, person sure |
|---|---|---:|---:|---:|---:|
| day | v4 | 48/59 (81%) | 8 | 1 | 2 |
| twilight | v4 | 11/14 (79%) | 3 | 0 | 0 |
| night | v4 | 6/18 (33%) | 7 | 0 | 5 |

Snow beside the road, lanes bare (person), 53 images; model says snow on lanes:
- v4: 16/53 (30%)

Day + twilight, person sure: answer only when confidence k >= threshold, else "can't tell":

| prompt | k >= | answered | right when answered | says snow, person bare |
|---|---:|---:|---:|---:|
| v4 | 0.0 | 71/73 | 59/71 (83%) | 11 |
| v4 | 0.6 | 63/73 | 56/63 (89%) | 6 |
| v4 | 0.7 | 40/73 | 39/40 (98%) | 0 |
| v4 | 0.8 | 32/73 | 31/32 (97%) | 0 |
| v4 | 0.9 | 5/73 | 5/5 (100%) | 0 |

v4 center line (cl) vs the person's lane answer, all lights:

| cl | person bare | person snow | person can't tell |
|---|---:|---:|---:|
| vis | 36 | 3 | 1 |
| part | 5 | 4 | 0 |
| hid | 1 | 11 | 4 |
| none | 22 | 6 | 2 |
| u | 3 | 0 | 2 |
