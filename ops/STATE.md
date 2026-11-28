# State
run: 2026-11-28T20:18Z Q16 Oregon TripCheck batch (cloud operator)
active: Q6a (daily label installments); Q14 storm report after the Teton window (~06:00Z 11-29)
live: 38 passes (WA 7, OR 6, CA 5, ID 13, MT 6, WY 1) + state hubs /states/{washington,oregon,california,idaho,montana}/ + /sources/; collector ~every 15 min; images mirrored; wordmark ConditionsNow.
data: 3,559 images by 2026-11-28 00:34Z (day 1,310, twilight 363, night 1,886); ~3,500/day (36 cams). Status history in HF status/ from 16:36Z.
to_index: /passes/bozeman-pass/ /passes/homestake-pass/ /passes/macdonald-pass/ /passes/rogers-pass/ /passes/kings-hill-pass/ /passes/raynolds-pass/ /states/montana/ /passes/lewiston-hill/ /passes/horseshoe-bend-hill/ /passes/malad-summit/ /passes/sweetzer-summit/ /passes/pine-creek-pass/ /passes/fish-creek-summit/ /passes/georgetown-summit/ /passes/geneva-summit/ (D12: Claude in chat requests indexing and clears)
holds:
- Q8 Colorado: waiting for CDOT reply (sent 2026-11-27 09:40Z from apoorv20@gmail.com, cc hello@).
- Q9 Search Console: no cloud access.
- Q6a: next label installment when the unlabeled day+twilight pool is ≥1,000 (about 2026-11-28 evening ET).
- Q14: Teton Pass storm mode on since 16:39Z 11-28 (Winter Storm Warning to 11:00 MST); report once the window closes.
- Q6 student v0: code ready in cam-conditions-engine (6ed3432); its Actions has no HF_TOKEN secret (run 141057455735: "HF_TOKEN missing"). Owner D12.
- Q10 new states: owner D7 (terms: IA consent, NE approval, SD none, MT informational use).
last_run: 2026-11-28T19:17-19:40Z Q16 Idaho batch: 8 Idaho 511 passes (Lewiston Hill, Horseshoe Bend Hill, Malad, Sweetzer, Pine Creek, Fish Creek, Georgetown, Geneva); elevation/coords from the Idaho 511 mountainpasses feed; each has a winter-road segment at 0.0 km. Skipped Emigration (camera site 6,441 ft vs pass 7,413), Gilmore (168 ft gap), Galena/Banner/Targee (no camera). Next sprint run: Q6 student step if D12 answered, else Oregon TripCheck batch.
