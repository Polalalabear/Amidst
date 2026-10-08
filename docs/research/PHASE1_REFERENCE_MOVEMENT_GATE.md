# Reference movement annotation gate

Status: **APPROVED_LOCKED_BEFORE_FRESH_EXPORT**, recorded 2026-10-07.
This does not reopen HR01–HR04. The proposal bytes remain the original proposal;
the separate [approval receipt](../../data/finalization/reference_movement_approved_v1/approval_receipt.json)
records the user's explicit "核准此新增 reference policy" reply and
[input lock](../../data/finalization/reference_movement_approved_v1/approved_input_lock.json).
Implementation, fresh annotations and metric execution are still separate evidence gates.

The original benchmark protocol requires an independently approved reference movement/dwell
annotation policy for Travel-time Error. HR04 approves inference speed, uniform-first timing
and departure dwell; its immutable payload does not approve reference annotation semantics.
Current formal local results therefore preserve this required metric as N/A.

The concrete proposed extension is
[proposed_reference_movement_policy_v1.json](../../configs/finalization/proposed_reference_movement_policy_v1.json).
Simulation/export would explicitly annotate recipe segments as MOVING or departure DWELL,
using distinct/identical floor-contact endpoints and their exact timestamp extents. Independent
evaluation sums the moving durations intersecting the observed GAP and compares them with
the primary hypothesis's moving duration, excluding explicit dwell. It never substitutes
the full GAP duration as the reference moving time. It introduces no new distance epsilon.

For a 10 s reference with a 4 s explicitly annotated departure dwell and 6 s motion, the
reference moving time is 6 s. A uniform 10 s primary motion has Travel-time Error 4 s;
a 4 s departure dwell plus 6 s motion has error 0 s. These are definition examples,
not the current measured school-case results.

Approval is recorded as a separate versioned receipt. The extension must be locked
before fresh simulation/export/evaluation; original decisions, review hashes, configs,
datasets and measured results stay immutable. The annotations remain exclusively in
simulation/export/evaluation/debug. No inference, Graph, ranking or pruning consumer receives
them. This gate cannot supply the missing Case2 branching scope or Case3 candidate-growth scope.

No further manual data preparation is needed for this policy choice.
