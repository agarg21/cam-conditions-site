# Queue (top = next). Keep ≤15 items. Status: open | blocked (why) | NOT NOW.

00. **Q16 Expansion sprint (D10, owner 2026-11-28): ~60 pass pages by 2026-11-30.** 30 live after the MT batch (2026-11-28 18:50Z: Bozeman, Homestake, MacDonald, Rogers, Kings Hill, Raynolds + /states/montana/; elevation = USGS 3DEP where the MDT segment crosses the USGS GNIS gap, checked against MDT RWIS station elevation where the station is within 0.6 km). MT left: Big Hole (route name S-278 vs MT 278 unsettled), Elk Park (GNIS gap 6.8 km from I-15), Evaro Hill (no GNIS gap), Marias (no MDT camera).
   Alternate runs: a batch of up to 8 passes (one feed per run), then a Q6 student-v0 step, then a batch again. Order by
   weak official pages and demand: (1) Montana under D7a, then Iowa under D13 (/states/iowa/ with I-80 and I-35 corridor
   pages, CARS 511 cameras and road conditions) (Bozeman, Homestake, MacDonald, Rogers, Marias, Kings Hill, Evaro
   Hill, plus MT side of Lookout/Lost Trail/Monida if not shared) with a /states/montana/ hub; (2) Idaho 511 (Galena,
   Banner, Malad, Pine Creek, Sweetzer, Johnson Creek or others with a camera within 3 km and a winter-road segment);
   (3) Oregon TripCheck (Sexton, Bennett Pass OR 35, Ochoco, Battle Mountain, Dixie, Tombstone, Blue Mountain summit);
   (4) Caltrans (Cajon/I-15 once the summit elevation has one consistent source, Kingvale/Emigrant Gap, Spooner-side SR 28,
   US 395 Sherwin once elevation is settled, Big Bear SR 18/330 as a road page, Mount Shasta I-5 Black Butte Summit);
   (5) WSDOT (Mt. Baker Hwy, Wauconda, Disautel). Per pass: elevation and coordinates from one consistent source (skip and
   note when sources disagree), 2 cameras that fetch, status source checked, page built and Playwright-checked. Skip a pass
   rather than guess. New passes get camera readings automatically (D11).
00b. **Q6 student v0 now, not at 5,000 labels (owner 2026-11-28: "do this sooner").** Train a first student on the labels we
   have (k>=0.7 or Opus-agreed), test on the owner's 100, report; retrain as installments land. See Q6 below for the plan.
   Code shipped 2026-11-28 17:25Z in cam-conditions-engine (6ed3432: train/student_v0.py, .github/workflows/student.yml,
   trigger = push requests/student.json; report -> engine reports/student-v0-<date>.md; CPU, no API spend). BLOCKED: engine
   Actions has no HF_TOKEN secret (OWNER D12). When it exists: bump "requested" in requests/student.json, push, read the report.
0. **Q6a Cheaper labels, then the labeling job (D8).** Test done 2026-11-28 (docs/bakeoff/decision.md "Q6a update"): prompt
   pass-v2 via Message Batches, Sonnet $1.89 per 1,000 (was $5.98); vs Opus v2 95% day / 93% twilight; 512 px saves nothing;
   no Haiku cascade (missed snow 2/31 vs 1/31). D2 closed at $8.97 of $10. Installment 1 done 03:04Z: 1,513 day+twilight
   labels, $3.55, Opus audit 95% (143/151); D8 ledger docs/bakeoff/label-ledger.json $3.55 of $40. Left: one installment per
   day (push ops/bakeoff-request.json mode "label", same settings, bump "requested") until ~5,000 images; next when the
   unlabeled day+twilight pool is ≥1,000 (~1,500/day collected). Label job now defaults to prompt pass-v4 (35eb012; "prompt": "v2" for the old one). Non-JPEG fix done 2026-11-28 04:25Z: the bad file was
   raw/2026-11-28/0002/blewett-pass/0.jpg; collect.py now saves only complete JPEGs (SOI + EOI), else `problem` in manifest.

0b. **Q13 Claude readings on the top 5 passes (D9).** SHIPPED 2026-11-28 ~11:40Z by Claude in chat (scripts/read_cams.py in collect.yml;
   pass page "What the cameras show" + per-camera caption line). "Cameras" row in the 24 h history shipped 2026-11-28 12:40Z (b6c4317;
   shows once readings exist in the window). Readings accruing: Teton read 14:15Z (first light). Left:
   10% Opus audit of live readings (~$1/month); review owner's second-look answers when he finishes. Owner check compared 2026-11-28 08:00Z (review/2026-11-28/report.md):
   Sonnet 88% day (52/59 sure), 86% twilight, 50% night; misses the 90% bar by ~1 image. Main error: snow beside the road
   read as snow on the lanes (Sonnet 10/53, Opus 10/53, Haiku 38/53). Sample oversampled model-snowy images, so real rates
   are lower. Re-test 08:30Z (docs/bakeoff/2026-11-28-humantest.md, $0.39): prompt v3 made it WORSE (day 78%, roadside trap
   40%); v2 day 81%. But v2 with a confidence gate (show only k>=0.7, else "can't tell") was right 45/46 (98%) on day+
   twilight, zero false snow, answering 63%. Gate chosen on the same 73 images: confirm on fresh images via a 10% Opus audit.
   Training labels: use k>=0.7 or Opus-audited only. v4 (owner's method: center line first) 11:00Z, $0.21: day 81%, day+twilight 83%, k>=0.7 39/40; same as v2. Center line
   itself is a strong signal (visible -> person bare 36/39; hidden -> person snow 11/12) but a cl rule adds nothing over s.
   Prompt wording is not the lever. Owner is doing a second look on the disagreements (artifact "you vs the models").
   Waiting on owner: go live with v2 or v4 + k>=0.7 gate (OWNER.md D9).
   Low-confidence rule (owner 2026-11-28 16:53 IST: no carry-forward; searchers are often hours away): the current answer is
   only a confident reading from the latest image (either camera), else "Can't tell from cameras right now" plus a small
   "Last clear look: <time>, <reading>". Add a trend line for drivers arriving later: snow seen falling (since when), lanes
   getting worse/better over the last 3 h (from confident readings only), next to the NWS tonight/tomorrow periods. If Sonnet agrees ≥90% on lane snow in daylight: pick the 5 passes by search
   demand (likely Snoqualmie, Stevens, Donner, Lookout, Santiam; check docs/research), add an hourly reading job (Batch not
   needed at this size), store readings in HF readings/, and show on pass pages: per camera "Our reading: snow on lanes /
   bare / can't tell (too dark)" with time and confidence; a pass-level "Cameras show" line beside the official verdict;
   a third row "Cameras" in the 24 h history; a flag when cameras disagree with an official report ≥2 h old. Label every
   reading "our reading, not an official report". Spend ledger in docs/bakeoff/label-ledger.json, D9 ≤$15/month.

0c. **Q14 Storm check (owner 2026-11-28: "check the quality during / after a storm").** Part (1) SHIPPED 2026-11-28 16:21Z
   (1a34153): read_cams.py storm mode (NWS Winter Storm Warning / Winter Weather Advisory / Blizzard / Ice Storm alert at the
   pass point, or gridpoint snowfall >= 2 in in 24 h; on for 12 h after the last trigger) gives every reading an Opus v4
   re-read in HF readings/audit-<date>.jsonl ("why": "storm"); windows in readings/storms.json; routine ~10% audit ("why":
   "audit", Q13) only while month spend is under pace (D11 $40 cap). Live: run 46167545830 6 Opus re-reads $0.069. FIRST STORM: Teton Pass, Winter Storm Warning until 11:00 MST
   2026-11-28 -> storm mode to ~06:00Z 11-29 (only daylight readings, so ~00:30Z). NEXT: scripts/storm_report.py +
   workflow triggered by pushing ops/storm-request.json (pull storms.json, readings, audit, status/ from HF; write
   docs/bakeoff/storm-<date>.md aggregates) and the 100-image export; run it after the Teton window closes. Original spec:
   Event-triggered: when NWS has a Winter
   Storm Warning/Advisory, or forecasts >= 2 in of snow, for a pass with readings, then during the storm and the 12 h after:
   (1) every reading also gets an Opus re-read (counts in D9 <= $15/month); (2) report per pass: Sonnet vs Opus agreement,
   share answered at k >= 0.7, and lead time = when cameras first showed snow/bare vs when the official report changed (from
   status/ history); (3) export a 100-image storm review set (review_export.py, light-balanced) and tell the owner it is ready;
   Claude in chat builds the owner check page. Write docs/bakeoff/storm-<date>.md (aggregates only).
0d. **Q15 Driver outlook from the forecast (owner 2026-11-28: "incorporate weather predictions").** Pages show the NWS text
   forecast but don't use it. Add a "Next 12 hours" line in the camera block and the verdict area, from NWS gridpoint data
   (snowfallAmount, snowLevel vs pass elevation, temperature crossing 32F, probabilityOfPrecipitation) and active NWS alerts for
   the point: e.g. "Forecast: 3-5 in of snow after 4 PM; below freezing tonight, wet roads may ice." Labeled "NWS forecast", with
   time; never changes the official answer or the camera reading; no invented numbers (show NWS ranges as given). Also feeds Q14.
1. **Q1 Labeling bake-off.** Done 2026-11-28 01:08Z: docs/bakeoff/decision.md (Sonnet labels; Haiku 18% false snow;
   collapsed road surface Sonnet 93% vs Opus). D2 spent $6.80 of $10. Follow-up lives in Q6.
2. **Q3 Pass page answers.** Shipped 2026-11-27 (a1a832a): answers block (Open? / Chains? / Snow on the road?) from official
   wording only, tonight/tomorrow/weekend NWS periods with snow totals, facts block, new titles. Live on all 18 pages
   12:30Z (OR/ID verified). (a) stale reports shipped 2026-11-27 14:35Z: reports ≥12 h old flagged on verdict and board.
   Left: (b) FAQ only where an official source answers; (c) "typical closures" fact only with a source per pass.
2b. **Q11 SEO pass on pass pages (owner asked, 2026-11-28).** Part 1 shipped 2026-11-28 (66007ac): (1) title "<Pass> Road
   Conditions, Webcams & Chain Status", H2 "<Pass> webcams", camera alt "<Pass> webcam: …"; (2) h1 "<Pass> road conditions"
   above the sign; (3) "Is <Pass> open right now?", "Do I need chains?", "<Pass> weather"; (4) WebPage+BreadcrumbList
   (Home › Pass)+Place geo JSON-LD, og/twitter tags with the first camera's stable URL. Part 2 shipped 2026-11-28 (ba7f7f7):
   (5) hubs /states/{washington,oregon,california,idaho}/ (states with ≥2 passes; WY's 1 pass keeps a 2-level crumb), home
   state headings link to them, pass crumbs All passes › State › Pass, "Other passes on <route>" + "Nearby passes" (≤3, ≤300 km)
   with live official status; ODOT disclaimer added wherever ODOT status appears (home board still shows ODOT rows without it:
   check). Part 3 shipped 2026-11-28 (aff9b81, a0a2d5b): ODOT disclaimer on the home board; "<State> chain and traction tire
   rules" on WA/OR/CA/ID pass pages from config/chain-rules.json (official pages only, read 2026-11-28; WY none yet).
   ?t= decided: keep it on visible images (Pages max-age=600 would show an image up to 10 min older than its time label);
   og:image and JSON-LD already use the stable URL. WY rules shipped 2026-11-28 14:25Z (75c8e3f, WYDOT chain law page: Level 1/2, fines). Left: typical closure causes and
   nearest towns only with a source per pass; ski-area links. Original notes: gaps found on /passes/snoqualmie-pass/: (1) the word
   "webcam" is nowhere, though "<pass> webcam" is the biggest search (~98K/mo across 12 passes): title "<Pass> Road
   Conditions, Webcams & Chain Status", H2 "<Pass> webcams"; (2) H1 is the bare name: make it "<Pass> road conditions"
   (the sign stays as the visual); (3) question headings that match searches: "Is <Pass> open right now?", "Do I need
   chains?", "<Pass> weather" (short); (4) JSON-LD: WebPage with dateModified, BreadcrumbList, Place with geo; og:title,
   og:description, og:image (latest summit camera); (5) internal links: breadcrumb Home › <State> › <Pass>, "Nearby passes"
   and "Same highway" blocks, and state hub pages /states/<state>/ (WA, OR, CA, ID first) targeting "<state> mountain
   passes"/"<state> pass conditions"; (6) a sourced evergreen block per pass: state chain/traction rules (link the DOT
   page), typical closure causes, nearest towns; link out to ski areas for ski-intent searches. No FAQ schema (no rich
   results for this site type). Keep stable image URLs per camera for Google Images; cache-bust with headers, not ?t=.
3a. **Q12 Image archive policy (owner asked, 2026-11-28).** Today every 15-min image goes to the private HF dataset
   (~36 cams). Write docs/plan/archive.md: measured MB/day and HF free-tier headroom; policy = keep every frame 30 days,
   then 1 frame/hour per camera plus every frame within ±1 h of an official-status change, forever; per-image metadata
   (time, pass, cam, sun elevation, official status) in a small parquet/JSONL index. Projection for 300 and 1,000 cameras
   and when to move to cheap object storage (owner approval before any paid storage). Implement the thinning job only
   after the plan is written.
3. **Q4 History.** Shipped 2026-11-27: per-run official status rows in HF `status/<UTC date>.jsonl` (baa1f9a); pass pages show
   "Last 24 hours" (verified accruing 18:18Z: 108 rows loaded, section live on all pages); home board notes each pass whose report
   changed in 24 h plus an "N passes changed" line (7422dcc). Left: none; reopen only for a defect.
4. **Q5 More passes and states by demand.** First read docs/research/state-cameras-2026-11-27.md: northern-tier states (ND, MN, IA, MT, WY, WI, SD) lead state demand with weak results, and IA/NE/SD/MT feeds are keyless; propose which new states to add, with each feed's terms, as a yes/no question in OWNER.md (D3 covers only WSDOT, Caltrans, ODOT, Idaho 511). WA Sherman, Loup Loup, Satus shipped 2026-11-27 22:30Z (Chinook, Cayuse when they reopen; Mt. Baker Hwy, Wauconda,
   Disautel have reports too). Left: Oregon (Sexton Summit, OR 35 near Bennett Pass), Idaho (Malad, Sweetzer, Galena if a camera appears),
   California (US 395 Conway Summit, Big Bear via CWWP2 D8, Mount Rose via NDOT if keyless). Use `discover.yml` and
   CWWP2 JSON; 2 cameras per pass; verify images fetch.
4b. **Q10 New states (D5): Iowa, Montana, South Dakota, Nebraska.** MONTANA UNBLOCKED (D7a) and IOWA UNBLOCKED (D13: stills only,
   credit "Iowa DOT", direct link https://511ia.org); do them before Q5. NE/SD stay blocked until a written yes (D7b). Terms read 2026-11-27
   (docs/research/state-terms-2026-11-27.md, config/SOURCES.md): IA needs written consent; NE cameras need NDOT approval; SD has no
   terms; MT grants copying for "personal or informational use", unmodified, commercial use not addressed. When D7 answers: one state
   per run, `/states/<state>/` page (official condition layer summary, key corridors with 2–4 cameras, credits) linked from home;
   MT also Bozeman, Homestake, MacDonald pass pages. Feeds: IA/NE CARS `/api/graphql`; SD/MT Iteris
   `*.cdn.iteris-atis.com/geojson/icons/metadata/icons.<layer>.geojson`. Targets: IA 40.5K, MT 27.1K, SD 6.6K, NE ~6K/mo.
5. **Q6 Student model plan.** Q1 done. Write prompt `pass-v2` (decision.md item 2) and the training plan in cam-conditions-engine (CLIP/SigLIP embeddings + heads vs
   small CNN; unseen-camera eval; 81.5% NYSDOT bar, target ≥90% daylight) and a labeling job for ~5,000 images.
   Owner check 2026-11-28 changes the plan: Sonnet labels are ~83% right overall but 98% at k>=0.7, so train only on
   labels with k>=0.7 or Opus agreement; switch remaining label installments to prompt pass-v4 (adds center line, same
   accuracy); test every student model on the owner's 100 (review/2026-11-28) and report day/twilight agreement.
   Timeline (owner asked 2026-11-28): labels reach ~5,000 about Dec 1; first student Dec 1-3 in cam-conditions-engine on
   GitHub Actions CPU (frozen SigLIP-base embeddings + logistic heads for lanes / center line / snow falling; no GPU needed
   at this size); then 7 days shadow mode on the 5 reading passes (student and Sonnet both read, page still shows Sonnet).
   Switch when the student matches Sonnet on the owner's 100 and the Opus audit; then turn readings on for every pass
   (Sonnet for all 21+ passes would be ~$55/month, over D9; the student is ~free).
6. **Q7 Montana.** Folded into Q10.
7. **Q8 Colorado.** blocked (waiting for CDOT reply to the 2026-11-27 request; owner reads hello@ mail).
8. **Q9 Search Console.** blocked (no API access from cloud; see OWNER open question once raised).

## NOT NOW
- B2B pilots/outreach: drafts allowed under D6 once readings work; sending is owner only. Paid ads. App.
