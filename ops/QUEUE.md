# Queue (top = next). Keep ≤15 items. Status: open | blocked (why) | NOT NOW.

1. **Q1 Labeling bake-off.** Push `ops/bakeoff-request.json` with mode `count`; once day ≥150 and night ≥100, push mode
   `run` n=300 (D2 budget). Read `docs/bakeoff/<date>-run.md`; write `docs/bakeoff/decision.md`: which model labels
   training data (agreement with Opus per field, day vs night, cost per 1,000), which fields are reliable, which to drop or
   reword (prompt v2). Gate: daylight images (first full US day 2026-11-27 15:00–01:00 UTC).
2. **Q2 Search-intent numbers.** Read family-tripwise `docs/research/dataforseo-pass-intent-modifiers-b-2026-11-27.json`
   (public repo; fetch via raw GitHub). Write `docs/research/search-intent-2026-11-27.md`: volume per intent group, per pass,
   SERP features, and the page order it implies. If the receipt is missing, note it and move on.
3. **Q3 Pass page answers.** From Q2: add plain answers at the top of each pass page: "Open?", "Chains?", "Snow on the
   road?", plus a tomorrow/weekend outlook from NWS periods, and a facts block (elevation, between, route). FAQ content only
   where an official source answers it. Design tokens only.
4. **Q4 History.** Store each run's official status per pass (compact JSONL in the HF dataset, `status/<date>.jsonl`), and
   show the last 24 h on pass pages (closures, chain changes). No per-image labels in the public repo.
5. **Q5 More passes by demand.** Add WA passes from WSDOT reports that have cameras (Sherman, Loup Loup, Satus, Chinook and
   Cayuse when open), Oregon (Sexton Summit, OR 35 near Bennett Pass), Idaho (Malad, Sweetzer, Galena if a camera appears),
   California (US 395 Conway Summit, Big Bear via CWWP2 D8, Mount Rose via NDOT if keyless). Use `discover.yml` and
   CWWP2 JSON; 2 cameras per pass; verify images fetch.
6. **Q6 Student model plan.** After Q1, write the training plan in cam-conditions-engine (CLIP/SigLIP embeddings + heads vs
   small CNN; unseen-camera eval; 81.5% NYSDOT bar, target ≥90% daylight) and a labeling job for ~5,000 images.
7. **Q7 Montana.** Bozeman Pass and Homestake Pass from MDT (public RWIS pages or 511mt); check terms first.
8. **Q8 Colorado.** blocked (waiting for CDOT reply to the 2026-11-27 request; owner reads hello@ mail).
9. **Q9 Search Console.** blocked (no API access from cloud; see OWNER open question once raised).

## NOT NOW
- B2B pilots/outreach (owner only). Paid ads. App.
