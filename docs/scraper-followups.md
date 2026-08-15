# Scraper follow-ups

Deferred work from the 2026-08-15 performance/bot-flagging session. Do these later.

## 1. Complete house rules, not just the preview set

The HTTP fast path (`get_listing_details_http` in `api/tools/filter.py`) parses
`PoliciesSection.houseRules` from the embedded `data-deferred-state-0` JSON, but
that array is only the 3–5 preview rules shown on the listing card (e.g. check-in
time, checkout time, max guests). The full rule set lives one level deeper in
`PoliciesSection.houseRulesSections` (grouped `GeneralListContentSection` items),
and any rules Airbnb only loads via the amenities/policies modal's follow-up
GraphQL query still won't be in the SSR blob at all.

To-do:

- Parse `houseRulesSections` (all groups/items) instead of just `houseRules`.
- Verify coverage against real listings (compare with what the "House rules"
  modal shows in a browser) — if custom host rules are missing from the SSR
  blob, replicate the modal's `StaysPdpSections` GraphQL call over HTTP using
  the `x-airbnb-api-key` embedded in the page (`d306zoyjsyarp7ifhu67rjxn52tv0t20`
  as of this writing).

## 2. Amenities are empty on the HTTP fast path

`_extract_pdp_details` never populates `amenities` — the `AmenitiesSection` in
the SSR JSON is lazy-loaded (only `__typename`, no items). But the full amenity
list **is** present under `seeAllAmenitiesGroups` → `AmenityItemsGroup[]` →
`AmenityItem[]` with `title`, `available`, `icon` (verified on a live listing:
"Hair dryer", "Carbon monoxide alarm", etc.).

To-do:

- Parse `seeAllAmenitiesGroups` in `_extract_pdp_details`, keeping the
  `available` flag so unavailable items (e.g. "Carbon monoxide alarm") can be
  excluded or marked.
- This restores keyword matching over amenity names (`filter_by_keywords`
  searches `full_text + amenities`) and the amenity rows on the UI cards.

## 3. Price is always `None` on the HTTP fast path

Nightly price is rendered client-side by React and is not in the SSR JSON (also
note Airbnb shows localized currency — GTQ in Guatemala — not USD). The
`max_price` post-check in `scrape_listings_concurrent` is a no-op for
HTTP-fetched listings, so over-budget listings can slip through if Airbnb's
server-side `price_max` URL filter is loose.

To-do:

- Fetch pricing deliberately: either the `StaysPdpSections`/`BookItSection`
  GraphQL call with `check_in`/`check_out`/`adults` params (returns structured,
  currency-tagged amounts), or Airbnb's calendar/price API.
- Normalize to USD before the `max_price` comparison.
