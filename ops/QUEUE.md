# Queue (top = next). Keep ≤15 items. Status: open | blocked (why) | NOT NOW.

1. **Q1 Labeling bake-off.** Count 2026-11-27 16:19Z: 2,202 images (day 101, twilight 215, night 1,886). Next: at the first
   run after 00:30Z 2026-11-28 (so the day sample spans morning to dusk; day will be ≫150), push `ops/bakeoff-request.json`
   mode `run` n=300 (D2 budget). Read `docs/bakeoff/<date>-run.md`; write `docs/bakeoff/decision.md`: which model labels
   training data (agreement with Opus per field, day vs night, cost per 1,000), which fields are reliable, which to drop or
   reword (prompt v2).
2. **Q3 Pass page answers.** Shipped 2026-11-27 (a1a832a): answers block (Open? / Chains? / Snow on the road?) from official
   wording only, tonight/tomorrow/weekend NWS periods with snow totals, facts block, new titles. Live on all 18 pages
   12:30Z (OR/ID verified). (a) stale reports shipped 2026-11-27 14:35Z: reports ≥12 h old flagged on verdict and board.
   Left: (b) FAQ only where an official source answers; (c) "typical closures" fact only with a source per pass.
3. **Q4 History.** Shipped 2026-11-27: per-run official status rows in HF `status/<UTC date>.jsonl` (baa1f9a); pass pages show
   "Last 24 hours" (verified accruing 18:18Z: 108 rows loaded, section live on all pages); home board notes each pass whose report
   changed in 24 h plus an "N passes changed" line (7422dcc). Left: none; reopen only for a defect.
4. **Q5 More passes and states by demand.** First read docs/research/state-cameras-2026-11-27.md: northern-tier states (ND, MN, IA, MT, WY, WI, SD) lead state demand with weak results, and IA/NE/SD/MT feeds are keyless; propose which new states to add, with each feed's terms, as a yes/no question in OWNER.md (D3 covers only WSDOT, Caltrans, ODOT, Idaho 511). WA Sherman, Loup Loup, Satus shipped 2026-11-27 22:30Z (Chinook, Cayuse when they reopen; Mt. Baker Hwy, Wauconda,
   Disautel have reports too). Left: Oregon (Sexton Summit, OR 35 near Bennett Pass), Idaho (Malad, Sweetzer, Galena if a camera appears),
   California (US 395 Conway Summit, Big Bear via CWWP2 D8, Mount Rose via NDOT if keyless). Use `discover.yml` and
   CWWP2 JSON; 2 cameras per pass; verify images fetch.
4b. **Q10 New states (D5): Iowa, Montana, South Dakota, Nebraska.** blocked (D7 in OWNER.md). Terms read 2026-11-27
   (docs/research/state-terms-2026-11-27.md, config/SOURCES.md): IA needs written consent; NE cameras need NDOT approval; SD has no
   terms; MT grants copying for "personal or informational use", unmodified, commercial use not addressed. When D7 answers: one state
   per run, `/states/<state>/` page (official condition layer summary, key corridors with 2–4 cameras, credits) linked from home;
   MT also Bozeman, Homestake, MacDonald pass pages. Feeds: IA/NE CARS `/api/graphql`; SD/MT Iteris
   `*.cdn.iteris-atis.com/geojson/icons/metadata/icons.<layer>.geojson`. Targets: IA 40.5K, MT 27.1K, SD 6.6K, NE ~6K/mo.
5. **Q6 Student model plan.** After Q1, write the training plan in cam-conditions-engine (CLIP/SigLIP embeddings + heads vs
   small CNN; unseen-camera eval; 81.5% NYSDOT bar, target ≥90% daylight) and a labeling job for ~5,000 images.
6. **Q7 Montana.** Folded into Q10.
7. **Q8 Colorado.** blocked (waiting for CDOT reply to the 2026-11-27 request; owner reads hello@ mail).
8. **Q9 Search Console.** blocked (no API access from cloud; see OWNER open question once raised).

## NOT NOW
- B2B pilots/outreach: drafts allowed under D6 once readings work; sending is owner only. Paid ads. App.
