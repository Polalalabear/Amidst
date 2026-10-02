# Observation boundary fixtures

These small fixtures are `SYNTHETIC_TEST_FIXTURE` evidence, unrelated to school geometry.
`observation_pipeline.json` authorizes only A → B → C, with 0.02 m edges and a 1 m/s
speed ceiling. The source hash is a synthetic identity, not a Blender asset digest.

`observation_scenarios.json` declares the input, expected segments, candidate counts,
termination, rejection metadata, provenance, evaluation scope and failure/success state
for each scenario. Frame descriptors expand through the test-only
`observation_fixtures.py`: visible descriptors supply the same pixels plus a projected
point at the declared camera node; explicit GAP descriptors supply no position,
pixels or provenance. No truth file is provided or needed by these tests.

Covered boundaries: exact duplicate evidence, duplicate camera/time and source/frame
identities; all 120 permutations of a five-record stream; reverse or duplicate
Observation time; zero-duration handoff versus a valid one-frame visible segment;
sampling threshold below/equal/above; one/two missing-visibility frames; one/two-frame
recovery between independently reconstructed gaps; and absent camera records.

The existing contract rejects duplicates, canonically sorts streams, splits only when
a sampling gap is strictly greater than a configured threshold, and never merges a
brief visible recovery. With no sampling threshold, absent records alone do not split
a same-camera segment. An absence remains an absence: it does not assert `OCCLUDED` or
`OUTSIDE_FOV`, invent a frame, or change provenance. Explicit camera-dropout markers
would need a separately authorized schema decision; these fixtures preserve the
current schema.
