# State
run: none
active: Q6a (daily label installments); Q14 storm report after the Teton window (~06:00Z 11-29)
live: 24 passes (WA 7, OR 6, CA 5, ID 5, WY 1) + state hubs /states/{washington,oregon,california,idaho}/ + /sources/; collector ~every 15 min; images mirrored; wordmark ConditionsNow.
data: 3,559 images by 2026-11-28 00:34Z (day 1,310, twilight 363, night 1,886); ~3,500/day (36 cams). Status history in HF status/ from 16:36Z.
holds:
- Q8 Colorado: waiting for CDOT reply (sent 2026-11-27 09:40Z from apoorv20@gmail.com, cc hello@).
- Q9 Search Console: no cloud access.
- Q6a: next label installment when the unlabeled day+twilight pool is ≥1,000 (about 2026-11-28 evening ET).
- Q14: Teton Pass storm mode on since 16:39Z 11-28 (Winter Storm Warning to 11:00 MST); report once the window closes.
- Q6 student v0: code ready in cam-conditions-engine (6ed3432); its Actions has no HF_TOKEN secret (run 141057455735: "HF_TOKEN missing"). Owner D12.
- Q10 new states: owner D7 (terms: IA consent, NE approval, SD none, MT informational use).
last_run: 2026-11-28T17:18-17:40Z Q6 student v0 step: engine train/student_v0.py (frozen SigLIP-base + logistic heads usable/lanes/falling/cl, k>=0.7 or Opus-agreed labels, leave-one-pass-out C pick, tests on owner's 100 + bake-off 300, HF student/ cache) + student.yml (push requests/student.json); local mock test on the owner's 100 OK (200 images embedded in 40 s CPU). Live run: HF_TOKEN missing in the engine repo, nothing trained. Next sprint run: a pass batch (Montana first).
