# Camera sources (checked 2026-11-26)

| State | Source | Access | Status |
|---|---|---|---|
| CA | Caltrans CWWP2 JSON per district (`cwwp2.dot.ca.gov/data/dN/cctv/cctvStatusDNN.json`) | Public, no key | Working (D3: 274 cams; Donner, Echo Summit mapped). Images 320x260 JPEG with timestamp in EXIF. |
| WA | WSDOT ArcGIS layer `TravelInfoCamerasWeather` (1,710 cams) | Public, "low volume" use | Working (Snoqualmie, Stevens, White, Blewett, Sherman, Loup Loup, Satus mapped). Move to Traveler API (free Access Code by email) before scaling. |
| MT | MDT RWIS (`app.mdt.mt.gov/atms/public/rwis/<site>`), RWIS XML feed; 511mt.net (Iteris) | Public, no key | Terms 2026-11-27: copy/distribute for "personal or informational use", unmodified; commercial use not addressed. Owner question D7 open. |
| CO | COtrip API (maps.cotrip.org developers) | Developer key | Need key. |
| UT | UDOT Traffic API (`udottraffic.utah.gov/api/v2/get/cameras`) | Developer key, 10 calls/60 s | Need key. |
| ID | Idaho 511 API (`511.idaho.gov/api/v2/get/cameras`) | Developer key, 10 calls/60 s | Need key. |
| OR | TripCheck API (ODOT API portal) | Subscription key | Need key. |
| IA | 511ia.org (CARS `/api/graphql`), data.iowadot.gov traffic cameras | Public, no key | Terms 2026-11-27: incorporating content into another website needs Iowa DOT written consent. Stopped (D7). |
| SD | sd511.org (Iteris GeoJSON) | Public, no key | Terms 2026-11-27: none published. Stopped (D7). |
| NE | 511.nebraska.gov (CARS `/api/graphql`) | Public, no key | Terms 2026-11-27: camera images "for transportation purposes only, unless otherwise approved". Stopped (D7). |
| WY | wyoroad.info camera pages (226 cams, new image every 5 min) | Public pages, no API | Map image URLs per pass. |

Notes
- Night images are hard (headlight glare, infrared). Use a sun-angle "dark" rule like snowcam-feed and show "no clear view" rather than guess.
- Respect each DOT's terms; credit the DOT on every image; cache, don't hotlink at high volume.
