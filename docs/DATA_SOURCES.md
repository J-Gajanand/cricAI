# Data-source register

Research reviewed 2026-10-10. No production dataset has been imported or approved.
Public access does not establish redistribution permission. A license for a
database does not confer branding, image or personality rights.

| Source | Fields / use | Terms and redistribution | Refresh / limitations |
| --- | --- | --- | --- |
| [Cricsheet match downloads](https://cricsheet.org/downloads/) | Historical IPL ball-by-ball, derived batting/bowling totals | Non-XML: ODC Attribution 1.0 per [licensing](https://cricsheet.org/licensing/); preserve notices and attribution; check each archive | Periodic files; incomplete coverage possible; not live scores or full rosters |
| [Cricsheet register](https://cricsheet.org/register/) | Stable people/venue IDs, aliases and cross-source IDs | ODC Attribution 1.0; attribution required | Updated with source rebuilds; names not unique; missing external IDs |
| [Official IPL](https://www.iplt20.com/) | Reference candidate for franchise lists, auction values, profiles | [Terms](https://www.iplt20.com/terms-and-conditions) restrict copying/reuse; production redistribution not approved | No verified public API entitlement; visible pages are not a licensed feed |
| Authorized manual CSV | Explicitly sourced identity/season/eligibility/role/price/stat fields | Per-source permission evidence required; importing is not a rights bypass | Manual refresh with source/retrieval timestamps; validation before activation |

Cricsheet's [2026-10-07 announcement](https://cricsheet.org/article/licensing-and-venues-registry/)
documents licensing; XML alone uses CC BY 4.0. Do not conflate it with JSON's
license. Retain artifact hash, schema version, exact license and relevant notices.
Third-party providers are not approved without verified terms, limits and fields.

## Unresolved production requirements

Full latest-season rosters, national/overseas eligibility, primary/secondary roles,
styles, contract costs and permitted photos are not supplied by an identity
register. Historical appearance does not prove present franchise membership.
Do not infer nationality from a name. Injury, venue/pitch/dew data and recent
availability require additional reliable sources. No source for these is approved.
Use original branding and deliberate portrait placeholders. No official logos.

## Import and refresh contract

Provider adapter returns validated records plus a manifest: source URL, applicable
license, permission basis, season, retrieval time, coverage period and quality.
Validate IDs, duplicate mappings, numeric values, dates and mandatory eligibility;
stage before atomically publishing a content-addressed immutable snapshot.
Production rejects synthetic manifests. Unit fixtures are explicitly synthetic.
Unknown optional metrics remain null, never zero. Manual imports do not claim
independent verification of operator-supplied license assertions.

Phase 2 schedules weekly attempts by default, configurable daily; retries respect
provider rate limits and preserve the last good snapshot. Failed refreshes never
overwrite historical records. The UI exposes last success and stale/partial
coverage. New auctions pin a snapshot; existing auctions never refresh in place.

Derived stats must test legal balls, extras, run-outs versus bowler wickets,
super-over inclusion and missing matches. Bowling overs are not decimal numbers.
Insufficient samples produce warnings rather than invented precision.