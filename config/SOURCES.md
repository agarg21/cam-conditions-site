# Camera sources (checked 2026-11-26)

| State | Source | Access | Status |
|---|---|---|---|
| CA | Caltrans CWWP2 JSON per district (`cwwp2.dot.ca.gov/data/dN/cctv/cctvStatusDNN.json`) | Public, no key | Working (D3: 274 cams; Donner, Echo Summit mapped). Images 320x260 JPEG with timestamp in EXIF. |
| WA | WSDOT ArcGIS layer `TravelInfoCamerasWeather` (1,710 cams) | Public, "low volume" use | Working (Snoqualmie, Stevens, White, Blewett, Sherman, Loup Loup, Satus mapped). Move to Traveler API (free Access Code by email) before scaling. |
| MT | MDT RWIS cameras in `mt.cdn.iteris-atis.com/geojson/icons/metadata/icons.rwis.geojson` (images `rwis_images/<id>.jpg`, 1280x720); road condition per segment `mt.cdn.iteris-atis.com/mt3/road_conditions.json` + segment names/geometry `.../road_condition_segments.geojson` (what 511mt.net reads) | Public, no key | Working (D7a, 2026-11-28): Bozeman, Homestake, MacDonald, Rogers, Kings Hill, Raynolds. Terms §4: unmodified, credited "Montana Department of Transportation (MDT)". Feed has no per-segment update time (page shows none). |
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
