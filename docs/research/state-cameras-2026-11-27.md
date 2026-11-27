# Public DOT cameras and search demand by state (2026-11-27)

Data: `state-cameras-demand-2026-11-27.csv` (one row per state). Dashboard: https://claude.ai/artifact/6RRjtyfVuBG77VBmqNRsNq (owner's).

- Searches: DataForSEO keyword overview, US (family-tripwise receipt `docs/research/dataforseo-state-cameras-demand-2026-11-27.json`,
  USD 0.06). Core = "[state] road conditions" + "[state] traffic cameras" = **~497K/month** across 50 states. "[state] 511" and
  "[state] dot cameras" are navigational (and some are merged with DOT brand terms), so they are kept in the CSV but not in core.
- Top core demand: North Dakota 74.6K, Minnesota 50.8K, Iowa 41.5K, Montana 32.5K, Wyoming 25.1K, Wisconsin 20K, Illinois 20K,
  Colorado 17.2K, Indiana 15.7K, California 13.5K. Peak months are 5–9× the average (ND road conditions peaks at 450K).
- Cameras: **33,340 counted in 28 states** (+363 New England 511 for ME/NH/VT), measured from public 511 maps/feeds or DOT-published
  figures; 19 states not measured yet (incl. TX, MI, IL, VA, NJ, MD, TN, MO, KY). Largest: FL 4,988, GA 4,331, CA 3,615, UT 2,091,
  WA 1,710, PA 1,588, IA 1,249, OR 1,134.
- Open, keyless camera feeds we can use now: Caltrans CWWP2, WSDOT public layer, CARS-platform 511s (IA, IN, KS, MA, NE via
  `/api/graphql`), Iteris 511s (MT, SD, SC via `*.cdn.iteris-atis.com` GeoJSON). IBI-platform 511s (AK, AZ, CT, FL, GA, ID, LA, NC,
  NV, PA, UT, WI, New England) have public map icons and a free developer key API. Check each state's terms before republishing.
- SERPs (10 checked): DOT owns PA and OH; weak/mixed results (Facebook, WeatherBug, app stores, aggregators) on MI, FL, TX, GA,
  MN, ND. AI Overview on all 10.
- Implication for QUEUE Q5: the northern-tier winter states (ND, MN, IA, MT, WY, WI, SD) have the most demand per camera and weak
  results; several have keyless feeds (IA, NE, SD, MT). Rank new coverage by core demand × feed access × result weakness.
