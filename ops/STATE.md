# State
run: none
active: Q6a (daily label installments); Q14 storm report after the Teton window (~06:00Z 11-29)
live: 21 passes (WA 7, OR 6, CA 2, ID 5, WY 1) + state hubs /states/{washington,oregon,california,idaho}/ + /sources/; collector ~every 15 min; images mirrored; wordmark ConditionsNow.
data: 3,559 images by 2026-11-28 00:34Z (day 1,310, twilight 363, night 1,886); ~3,500/day (36 cams). Status history in HF status/ from 16:36Z.
holds:
- Q8 Colorado: waiting for CDOT reply (sent 2026-11-27 09:40Z from apoorv20@gmail.com, cc hello@).
- Q9 Search Console: no cloud access.
- Q6a: next label installment when the unlabeled day+twilight pool is ≥1,000 (about 2026-11-28 evening ET).
- Q14: Teton Pass storm mode on since 16:39Z 11-28 (Winter Storm Warning to 11:00 MST); report once the window closes.
- Q10 new states: owner D7 (terms: IA consent, NE approval, SD none, MT informational use).
last_run: 2026-11-28T16:17-17:05Z Q14 part 1 (Q6a pool too small: daylight just started): storm mode in read_cams.py (Opus re-read of every reading during NWS winter storm alerts / >=2 in forecast and 12 h after; ~10% routine audit under pace), 1a34153; 2 cameras per pass as D9 (Donner read 7), e1261a9. Mock test, build 27 pages, Playwright 390/1280 0 problems; live run 46166280732 "storm mode on: teton-pass", run 46167545830 (owner D11 code on top) "opus re-reads 6 (storm: teton-pass), $0.069", audit-2026-11-28.jsonl pushed; live 390/1280 0 problems. Next: Q14 storm_report.py + workflow, run after the window.
