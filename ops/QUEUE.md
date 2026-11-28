# Queue (top = next). Keep ≤15 items. Status: open | blocked (why) | NOT NOW.

1. **Q1 Labeling bake-off.** Done 2026-11-28 01:08Z: docs/bakeoff/decision.md (Sonnet labels; Haiku 18% false snow;
   collapsed road surface Sonnet 93% vs Opus). D2 spent $6.80 of $10. Follow-up lives in Q6.
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
4c. **Q6a Cheaper labels (owner, 2026-11-28), before D8.** Sonnet cost is ~90% output: 529 output tokens per image in the
   bake-off ($5.30 of $5.98 per 1,000). (1) Prompt v2 with short enum codes and no free-text note; record output tokens
   (target ≤150). (2) Message Batches API (50% off input and output; forced tool_choice still returns 400, keep auto + strict).
   (3) Try 448 px and 512 px vs 640 px on the 300 bake-off images: does Sonnet's agreement with Opus hold? (4) Cascade: Haiku
   has 0/36 missed snow; if that holds on v2, accept Haiku "bare" and send only Haiku snow/unknown to Sonnet. Spend from D2's
   remaining $3.20 only. Report cost per 1,000 and agreement per option, then re-ask D8 with the number. Other vendors'
   vision models (Gemini Flash, GPT mini, open-weight Qwen-VL) need a new key and are owner decisions: note, don't sign up.
5. **Q6 Student model plan.** Q1 done. Write prompt `pass-v2` (decision.md item 2) and the training plan in cam-conditions-engine (CLIP/SigLIP embeddings + heads vs
   small CNN; unseen-camera eval; 81.5% NYSDOT bar, target ≥90% daylight) and a labeling job for ~5,000 images.
6. **Q7 Montana.** Folded into Q10.
7. **Q8 Colorado.** blocked (waiting for CDOT reply to the 2026-11-27 request; owner reads hello@ mail).
8. **Q9 Search Console.** blocked (no API access from cloud; see OWNER open question once raised).

## NOT NOW
- B2B pilots/outreach: drafts allowed under D6 once readings work; sending is owner only. Paid ads. App.
