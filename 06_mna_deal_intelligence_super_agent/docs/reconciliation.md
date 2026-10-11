# M3 reconciliation policy

## Ownership

Project 3 owns trading-comps arithmetic, Project 4 owns precedent arithmetic, and Project 5 owns
diligence calculations. Project 6 compares their outputs, records context, and requests future
reruns. It never overwrites a specialist value or silently creates a replacement valuation.

## Safe automatic outcomes

Project 6 automatically aligns exact duplicates, same-period observations within the configured
tolerance, safe same-currency unit conversions, and explicit supersession metadata. It does not
automatically resolve competing EBITDA bases, material value disagreements, mixed currencies,
ambiguous entity identity, or contradictory evidence.

## Metric identity and comparison order

1. Match entity and normalized metric type.
2. Compare exact date ranges, falling back to normalized period labels only when dates are absent.
3. Check actual versus forecast state.
4. Check reported, adjusted, and normalized bases.
5. Require equal currencies; no FX conversion is implicit.
6. Scale supported units to base units.
7. Apply the explicit absolute and relative tolerance.

The default tolerance is `0.01` base units or `0.1%` relative difference. Either condition is
sufficient for alignment. Unsupported units remain not comparable.

## Valuation comparison

Valuation ranges are retained side by side. Comparison records midpoint gap, absolute percentage
gap using the lower absolute midpoint as denominator, range overlap, source warnings, and scenario
staleness. A midpoint gap above `10%` creates a reviewable divergence issue. No mean or blended
valuation is generated.

## Staleness and recomputation

An adjusted metric with the same entity, metric type, and period can make a valuation based on a
reported metric stale for that adjusted scenario. The original valuation remains valid for its
original input basis. M3 creates a typed recomputation request containing the changed input IDs,
target capability, scenario, priority, and approval requirement. M4/5 decides whether and when
to execute it.

Explicit `ArtifactVersion.produced_from` relationships also propagate superseded input status to a
direct dependent output. M3 does not infer dependencies missing from specialist metadata.

## Review priority

Priority follows transparent rules:

1. Critical and blocking issues are critical.
2. Blocking or high-severity issues are high.
3. Medium-severity issues or issues affecting multiple outputs are medium.
4. Remaining reviewable issues are low.

Review items are deduplicated by subject and retain every contributing issue and affected output.

## Failure behavior

Missing specialist outputs, incompatible schema versions, missing evidence, unsupported units,
mixed currencies, and differing periods produce issues or partial views. Available specialist
results remain visible. M3 contains no automatic reruns, graph checkpoints, interactive review,
final narrative recommendation, API, or UI.
