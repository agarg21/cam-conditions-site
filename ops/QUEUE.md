# Queue (top = next). Keep ≤15 items. Status: open | blocked (why) | NOT NOW.

1. **Q1 Labeling bake-off.** Push `ops/bakeoff-request.json` with mode `count`; once day ≥150 and night ≥100, push mode
   `run` n=300 (D2 budget). Read `docs/bakeoff/<date>-run.md`; write `docs/bakeoff/decision.md`: which model labels
   training data (agreement with Opus per field, day vs night, cost per 1,000), which fields are reliable, which to drop or
   reword (prompt v2). Gate: daylight images (first full US day 2026-11-27 15:00–01:00 UTC).
2. **Q3 Pass page answers.** Shipped 2026-11-27 (a1a832a): answers block (Open? / Chains? / Snow on the road?) from official
   wording only, tonight/tomorrow/weekend NWS periods with snow totals, facts block, new titles. Live on all 18 pages
   12:30Z (OR/ID verified). (a) stale reports shipped 2026-11-27 14:35Z: reports ≥12 h old flagged on verdict and board.
   Left: (b) FAQ only where an official source answers; (c) "typical closures" fact only with a source per pass.
3. **Q4 History.** Store each run's official status per pass (compact JSONL in the HF dataset, `status/<date>.jsonl`), and
   show the last 24 h on pass pages (closures, chain changes). No per-image labels in the public repo.
4. **Q5 More passes and states by demand.** First read docs/research/state-cameras-2026-11-27.md: northern-tier states (ND, MN, IA, MT, WY, WI, SD) lead state demand with weak results, and IA/NE/SD/MT feeds are keyless; propose which new states to add, with each feed's terms, as a yes/no question in OWNER.md (D3 covers only WSDOT, Caltrans, ODOT, Idaho 511). Add WA passes from WSDOT reports that have cameras (Sherman, Loup Loup, Satus, Chinook and
   Cayuse when open), Oregon (Sexton Summit, OR 35 near Bennett Pass), Idaho (Malad, Sweetzer, Galena if a camera appears),
   California (US 395 Conway Summit, Big Bear via CWWP2 D8, Mount Rose via NDOT if keyless). Use `discover.yml` and
   CWWP2 JSON; 2 cameras per pass; verify images fetch.
5. **Q6 Student model plan.** After Q1, write the training plan in cam-conditions-engine (CLIP/SigLIP embeddings + heads vs
   small CNN; unseen-camera eval; 81.5% NYSDOT bar, target ≥90% daylight) and a labeling job for ~5,000 images.
6. **Q7 Montana.** Bozeman Pass and Homestake Pass from MDT (public RWIS pages or 511mt); check terms first.
7. **Q8 Colorado.** blocked (waiting for CDOT reply to the 2026-11-27 request; owner reads hello@ mail).
8. **Q9 Search Console.** blocked (no API access from cloud; see OWNER open question once raised).

## NOT NOW
- B2B pilots/outreach (owner only). Paid ads. App.
