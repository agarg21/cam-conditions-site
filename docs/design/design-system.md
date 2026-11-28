# Conditions Now design system v1 (2026-11-27)

**Who we design for:** drivers checking a mountain pass before they leave or at a gas stop: skiers, commuters, delivery and shuttle drivers. Mostly on phones, often at night or in bad light, in a hurry. They trust what they can see (the camera) and what is official (the DOT), not what sounds clever.

**Design idea: the road's own language.** Each pass page opens with a green highway summit sign (pass name, "Summit", elevation), real route shields, and the road-condition colours drivers already know. Everything else is quiet and plain so the answer and the camera image carry the page.

## Principles
1. **Answer first.** The first phone screen shows the pass, its status in one line, and the official wording. No banner, no promo above it.
2. **Proof beside every claim.** A status is always next to its source and time; cameras always show when they were checked.
3. **Status colour means status.** The five status colours are never used for decoration, links or branding.
4. **Honest unknowns.** Grey "no current report" or "no clear view" rather than a guess. California's chain-control feed says nothing about snow on the road, so it is labelled "No chain controls now", never "Clear road".
5. **One bold thing.** The summit sign is the only loud element on a page. Its uppercase lettering is the sign's own vernacular; uppercase is not used anywhere else.

## Tokens (source of truth: `:root` in `site/styles.css`)

Colour
| Token | Value | Use |
|---|---|---|
| `--c-sign` | #0f5c45 | highway guide-sign green: summit sign, links, focus ring, wordmark |
| `--c-sign-dark` | #0a4433 | hover, pass names in lists |
| `--c-sign-tint` | #e3efe9 | quiet green surface (reserved) |
| `--c-asphalt` | #1e2328 | text |
| `--c-asphalt-muted` | #4a535c | secondary text (≥ 7:1 on snow) |
| `--c-snow` | #f3f6f8 | page background (cool, not cream) |
| `--c-surface` | #ffffff | camera captions, forecast cells, row hover |
| `--c-line` | #d5dce2 | borders, dividers |

Road status (semantic only)
| Level | Class | Colour / tint | Label | Triggered by (official wording) |
|---|---|---|---|---|
| Closed | `.is-closed` | #2b1a3d / #ece6f3 | Closed | "closed", "closure" |
| Snow or ice | `.is-snowice` | #b42318 / #fde7e4 | Snow or ice on the road | snow, ice, slush, chains required, R-1/R-2/R-3, chain control |
| Caution | `.is-caution` | #f5c400 / #fff6cc (ink #5c4500) | Wet road, take care | wet, standing water, traction tires, fog |
| Clear | `.is-clear` | #1f7a4d / #e2f2e9 | Clear road (CA: No chain controls now) | bare, dry, no chain controls |
| Unknown | `.is-unknown` | #6b7280 / #eceef1 | No current report | nothing usable |
Once camera readings ship, the model's read can raise a level (e.g. snow seen on a "bare and wet" report) but never lower an official restriction.

Type
- **Overpass** (Google Fonts, based on Highway Gothic, the US road-sign face) 700/800: headings, the sign, status labels, numbers.
- **Public Sans** (US Web Design System face) 400/600: body text.
| Token | Size | Use |
|---|---|---|
| `--t-xs` | 0.8125rem | sources, footer |
| `--t-sm` | 0.875rem | captions, status marks, notes |
| `--t-base` | 1rem | body |
| `--t-lg` | 1.1875rem | official wording, lead lines, pass names in lists |
| `--t-xl` | clamp(1.375rem, 3.4vw, 1.625rem) | section titles (h2) |
| `--t-status` | clamp(1.625rem, 6vw, 2.25rem) | status label in the verdict |
| `--t-sign` | clamp(1.75rem, 7.5vw, 3rem) | summit sign h1, home h1 |

Space `--s-1`…`--s-7`: 4, 8, 12, 16, 24, 32, 48 px. Radius: `--r-photo` 4px (camera frames, forecast), `--r-sign` 12px (summit sign only). Widths: `--w-page` 64rem, `--w-read` 60ch; sign and verdict cap at 40rem.

## Components
1. **Site header**: white bar, one row: mountain mark + wordmark "Conditions**Now**" + "All passes". The wordmark is one word: "Conditions" in asphalt at 700, "Now" in sign green at 800, so it reads as "Conditions Now" and never as "condition snow". Screen readers get "Conditions Now".
2. **Summit sign** (`.summit-sign`): green panel with an inset white border, uppercase pass name (`.summit-sign__name`), "Summit" and "Elev N ft". One per pass page. Above it (2026-11-28, SEO): a small breadcrumb (`.crumbs`, "All passes › {Pass}") and the h1 in plain text, "{Pass} road conditions" (`.page-title`, `--t-lg` 700), so the sign stays the visual and the h1 matches searches.
3. **Route line** (`.route-line`): route shield SVG + "US 2 between Everett and Leavenworth, Washington".
4. **Route shield** (`shield()` in build_site.py): interstate (red cap, blue body, white number) for I-xx; US shield (white, black outline) for US xx. State routes get a plain circle when added.
5. **Verdict** (`.verdict.is-*`): 10px status-colour rule on the left, tint background; status label (`--t-status`), then plain answers (`dl.answers`, 2026-11-27) under a small h2 "Is {Pass} open right now?" (`.verdict__ask`, 2026-11-28): Open? / Do I need chains? / Snow on the road?, each a bold short answer plus the official wording it came from (quoted, muted, `--t-sm`); anything the feed does not cover says "Not reported" (Caltrans' chain feed: "Not in this feed" for closures and road surface). Then weather, temperature, other restrictions, and "From the latest official {DOT} report, updated {time}". A report older than 12 h gets a bold line under the label ("Old report: {DOT} last updated it N hours ago…", `.verdict__stale`) and the board row says "Old report: N hours old" (`.pass-row__stale`); the colour still follows the official wording. Stacked below 640px.
5b. **Camera reading** (`.camread.is-*`, 2026-11-28): under the verdict, quieter than it: white card, 1px line border, 4px status rule; small h2 "What the cameras show", label at `--t-xl` ("Cameras show bare lanes" / "Can’t tell from cameras right now"), short bullet lines (center line, last clear look, snow falling, trend), then a muted note that it is our reading, not an official report. Status colour follows the reading (clear / snowice / unknown). Each camera caption gets a bold line `.cam__reading` ("Our reading at 2:40 PM: bare lanes").
6. **Status mark** (`.status-mark`): 14px colour square + label; used on the home board and tallies.
7. **Camera** (`.cam`): image at its natural aspect (DOT overlays stay visible), caption with camera name and "checked {time}". Grid: equal columns, min 19rem. Section title "{Pass} webcams"; alt "{Pass} webcam: {camera name}".
8. **Forecast** (`.forecast`): up to 6 NWS periods (now, the next two, tomorrow, Saturday and Sunday daytime) as cells: name, big temperature, short text, and NWS's "New snow accumulation…" sentence when present. 2 columns on phones (an odd last cell spans both), one row of auto-fit cells from 640px. Section title "{Pass} weather"; the note says "Summit forecast from the National Weather Service".
8a. **Last 24 hours** (`.history`, 2026-11-27): after the forecast. A lead line ("N changes in the official report"), a 14px strip of status colours across our checks (blank = no check for 50+ min; decorative, `aria-hidden`), then the changes newest first: time span, status mark with the label, and the chains and snow answers. Built only from the stored official answers (history.py); hidden until there are two checks.
8b. **Facts** (`dl.facts`, "About {pass}"): elevation, highway, between, official reports link.
9. **Pass board** (home): grouped by state; each row = shield, pass name, status mark + official wording, camera thumbnail. A row whose official report changed in the last 24 hours adds "Changed {time}, was “{old label}”" (or "Chains changed…" when only an answer changed; `.pass-row__changed`), from the same history rows as the pass page's "Last 24 hours"; the intro adds "N passes changed their official report in the last 24 hours" (`.board-intro__changed`).
9b. **State hub** (`/states/<state>/`, 2026-11-28, states with ≥2 passes): breadcrumb "All passes › {State}", h1 "{State} mountain pass conditions", the board intro (lead, tally, changed line) and that state's board rows, then "Where this comes from" (DOT, camera credit, NWS); ODOT disclaimer on Oregon. Home board state headings link to the hub; pass-page breadcrumbs become "All passes › {State} › {Pass}".
9c. **Related passes** (`.related`, pass pages, 2026-11-28): "Other passes on {route}" (same highway, nearest first) and "Nearby passes" (up to 3 others within 300 km straight line), each a link, route and state, and the current official status mark on its own line. A page that lists an ODOT pass here also carries the ODOT disclaimer.
10. **Checklist** ("Before you go"): plain bullets, official link first.
11. **Footer**: DOT credit, "always check official closures", contact.

## Writing
- Plain verbs, sentence case, no hype. Name things as drivers do ("chains", "snow on the road"), not as feeds do ("R-2", "RWIS").
- Quote official wording exactly and say whose it is and when.
- Errors give direction: "The official report did not load. Check WSDOT."

## Quality floor
Playwright screenshots at 390 and 1280 px for every changed template, no horizontal overflow, visible focus, alt text on every camera image, AA contrast (yellow status uses dark ink).
