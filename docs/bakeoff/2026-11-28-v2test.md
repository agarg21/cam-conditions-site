# Bake-off v2test, 2026-11-28

Collected images: **3955** (day 1310, twilight 437, night 2208)

| pass | day | twilight | night |
|---|---:|---:|---:|
| blewett-pass | 33 | 12 | 60 |
| deadman-pass | 62 | 22 | 108 |
| donner-pass | 259 | 63 | 406 |
| echo-summit | 76 | 16 | 116 |
| fourth-of-july-pass | 60 | 24 | 108 |
| government-camp | 62 | 22 | 108 |
| lolo-pass | 62 | 22 | 108 |
| lookout-pass | 60 | 22 | 110 |
| lost-trail-pass | 62 | 22 | 108 |
| loup-loup-pass | 4 | 5 | 8 |
| monida-pass | 64 | 22 | 106 |
| santiam-pass | 64 | 22 | 106 |
| satus-pass | 10 | 10 | 14 |
| sherman-pass | 6 | 12 | 16 |
| siskiyou-summit | 66 | 20 | 106 |
| snoqualmie-pass | 66 | 24 | 120 |
| stevens-pass | 66 | 24 | 120 |
| teton-pass | 66 | 20 | 106 |
| tollgate | 62 | 22 | 108 |
| white-pass | 34 | 11 | 60 |
| willamette-pass | 66 | 20 | 106 |

## Prompt v2 test (pass-v2, Message Batches), 187 bake-off images

Reference: v1.1 Opus readings (`labels/bakeoff-2026-11-28/pass-v1.1.jsonl`). Per-image v2 labels: `labels/bakeoff-2026-11-28/pass-v2-test-opus.jsonl` (private).
Batches: `{"opus640": "msgbatch_01Xto8aUcJu7K3z5vh7KsdAW"}`. Spend this test: **$0.96** (cap $1.95; probe $0.051, batches $0.91). Variants from earlier runs (costs shown but not counted here): haiku640, sonnet512, sonnet640.

Sync probe (prompt v2, 640 px):

| model | light | ok | in tok | cache read | out tok | cost | error |
|---|---|---|---:|---:|---:|---:|---|
| opus | day | yes | 411 | 0 | 491 | $0.0177 |  |
| opus | day | yes | 411 | 1,240 | 533 | $0.0126 |  |
| opus | night | yes | 411 | 1,240 | 591 | $0.0137 |  |
| opus | night | yes | 197 | 1,240 | 280 | $0.0066 |  |

### Cost (batch prices, from usage)

| variant | ok | errors | input tok | cache read | output tok | out tok / image | cost | per 1,000 images |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| opus640 | 187 | 0 | 50,237 | 230,640 | 78,559 | 420 | $0.91 | $4.88 |
| haiku640 | 187 | 0 | 50,237 | 230,640 | 117,973 | 631 | $0.03 | $0.18 |
| sonnet512 | 187 | 0 | 45,443 | 231,880 | 58,617 | 313 | $0.35 | $1.87 |
| sonnet640 | 187 | 0 | 50,237 | 230,640 | 58,097 | 311 | $0.35 | $1.89 |

v1.1 sync for comparison: Sonnet $5.98 and Haiku $0.47 per 1,000; Sonnet 529 output tokens per image.

### Road surface, collapsed (bare / snow / unknown), agreement with v1.1 Opus

| reader | all | day | twilight | night | snow on Opus-bare | missed snow (Opus snow -> bare) | unknown rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| opus640 (v2) | 81% (187) | 94% (94) | 81% (27) | 62% (66) | 7/117 | 1/22 | 11% |
| haiku640 (v2) | 78% (187) | 78% (94) | 89% (27) | 74% (66) | 23/117 | 0/22 | 28% |
| sonnet512 (v2) | 82% (187) | 90% (94) | 89% (27) | 68% (66) | 13/117 | 0/22 | 17% |
| sonnet640 (v2) | 82% (187) | 90% (94) | 89% (27) | 68% (66) | 13/117 | 0/22 | 17% |
| sonnet v1.1 sync | 94% (187) | 96% (94) | 93% (27) | 91% (66) | 4/117 | 1/22 | 22% |
| haiku v1.1 sync | 81% (187) | 83% (94) | 93% (27) | 73% (66) | 17/117 | 0/22 | 29% |
| cascade haiku640 bare + sonnet640 | 83% (187) | 90% (94) | 93% (27) | 70% (66) | 11/117 | 0/22 | 17% |

#### Same table with **Opus v2** (opus640) as the reference

| reader | all | day | twilight | night | snow on Opus-bare | missed snow | unknown rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| haiku640 (v2) | 69% (187) | 82% (94) | 85% (27) | 44% (66) | 20/136 | 2/31 | 28% |
| sonnet512 (v2) | 87% (187) | 95% (94) | 93% (27) | 74% (66) | 9/136 | 1/31 | 17% |
| sonnet640 (v2) | 87% (187) | 95% (94) | 93% (27) | 74% (66) | 9/136 | 1/31 | 17% |
| sonnet v1.1 sync | 84% (187) | 96% (94) | 81% (27) | 68% (66) | 2/136 | 5/31 | 22% |
| haiku v1.1 sync | 72% (187) | 87% (94) | 81% (27) | 45% (66) | 13/136 | 3/31 | 29% |
| cascade haiku640 bare + sonnet640 | 88% (187) | 95% (94) | 89% (27) | 77% (66) | 7/136 | 2/31 | 17% |
Opus v2 collapsed: bare 136, snow 31, unknown 20.

Opus v1.1 collapsed: bare 117, unknown 48, snow 22. Cascade sends 95/187 images (51%) to Sonnet.

### Other fields vs v1.1 Opus (exact, mapped to v1 values; day in brackets)

| field | opus640 | haiku640 | sonnet512 | sonnet640 |
|---|---:|---:|---:|---:|
| image_usable (u) | 89% [100%] | 91% [100%] | 89% [100%] | 90% [100%] |
| visibility (v) | 84% [93%] | 81% [89%] | 82% [90%] | 86% [91%] |
| traffic (t) | 92% [96%] | 80% [89%] | 86% [97%] | 86% [97%] |
| roadside_snow (b) | 82% [81%] | 76% [76%] | 79% [83%] | 78% [81%] |
| incident_visible (x) | 98% [100%] | 91% [100%] | 92% [100%] | 93% [100%] |
| plow_or_chainup (p) | 97% [100%] | 91% [98%] | 89% [99%] | 89% [99%] |
| closure_visible (c) | 98% [100%] | 93% [100%] | 91% [100%] | 93% [100%] |
| wet (w) on Opus-bare lanes | 75% (117) | 51% (117) | 77% (117) | 76% (117) |

### Snow falling (f): unknown rate, and vs Opus precip (snow/mixed = y, none/rain = n)

| variant | y | n | u | unknown rate day | agrees where Opus judged |
|---|---:|---:|---:|---:|---:|
| opus640 | 10 | 79 | 98 | 43% | 94% (62) |
| haiku640 | 14 | 103 | 70 | 15% | 94% (62) |
| sonnet512 | 18 | 133 | 36 | 3% | 100% (62) |
| sonnet640 | 16 | 126 | 45 | 7% | 100% (62) |

Opus v1.1 precip_falling was unknown on 67% of images (59% of daytime).

