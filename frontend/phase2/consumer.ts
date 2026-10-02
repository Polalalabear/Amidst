import type { ConsumerEvent, ReplayFrame, Vec3 } from "./contracts.js";

/**
 * Three.js setup before constructing scene objects:
 * THREE.Object3D.DEFAULT_UP.set(0, 0, 1); camera.up.set(0, 0, 1).
 * Copy world_position directly into Vector3; do not swap axes or rescale metres.
 * Rendering and display interpolation never write back into the source Event.
 * OBSERVED, PROJECTED and INFERRED_GAP need visibly distinct presentation styles.
 * Camera navigation anchors are not calibrated camera poses or FOV.
 */
export const WORLD_UP: Vec3 = [0, 0, 1];

type RecordValue = Record<string, unknown>;
const META = {
  contract_version: "phase2.integration.v1",
  data_kind: "SYNTHETIC",
  time_basis: "CONFIGURED_SECONDS",
  time_interval: "CLOSED",
  coordinate_system: "BLENDER_RIGHT_HANDED_Z_UP",
  units: "METRES",
} as const;
const TERMINATIONS = [
  "COMPLETE", "NO_FEASIBLE_PATH", "MAX_PATHS_REACHED",
  "MAX_SEARCH_NODES", "MAX_BRANCH_FACTOR", "SEARCH_TIMEOUT",
];

function requireValue(condition: unknown, path: string): asserts condition {
  if (!condition) throw new TypeError(`Invalid Phase 2 contract: ${path}`);
}

function record(value: unknown, fields: string, path: string): RecordValue {
  requireValue(value !== null && typeof value === "object" && !Array.isArray(value), path);
  const result = value as RecordValue;
  const expected = fields.split(" ");
  requireValue(Object.keys(result).length === expected.length
    && expected.every(key => Object.hasOwn(result, key)), `${path} fields`);
  return result;
}

function array(value: unknown, path: string, minimum = 0): unknown[] {
  requireValue(Array.isArray(value) && value.length >= minimum, path);
  return value;
}

function text(value: unknown, path: string, nonempty = true): string {
  requireValue(typeof value === "string" && (!nonempty || value.length > 0), path);
  return value;
}

function number(value: unknown, path: string, minimum = -Infinity): number {
  requireValue(typeof value === "number" && Number.isFinite(value) && value >= minimum, path);
  return value;
}

function integer(value: unknown, path: string): void {
  requireValue(Number.isSafeInteger(number(value, path, 0)), path);
}

function enumValue(value: unknown, options: readonly string[], path: string): void {
  requireValue(options.includes(text(value, path)), path);
}

function strings(value: unknown, path: string, unique = false, nonempty = false): string[] {
  const values = array(value, path).map(item => text(item, path, nonempty));
  requireValue(!unique || new Set(values).size === values.length, `${path} identities`);
  return values;
}

function vector(value: unknown, dimensions: number, path: string): void {
  const values = array(value, path);
  requireValue(values.length === dimensions, path);
  values.forEach(item => number(item, path));
}

function timeRange(value: unknown, path: string, positive = false): [number, number] {
  const values = array(value, path);
  requireValue(values.length === 2, path);
  const start = number(values[0], path, 0), end = number(values[1], path, 0);
  requireValue(positive ? end > start : end >= start, `${path} order`);
  return [start, end];
}

function quality(value: unknown, path: string): void {
  requireValue(number(value, path, 0) <= 1, path);
}

function nullable(value: unknown, validate: (value: unknown) => void): void {
  if (value !== null) validate(value);
}

function equal(first: unknown, second: unknown): boolean {
  if (Array.isArray(first) && Array.isArray(second)) {
    return first.length === second.length && first.every((item, i) => equal(item, second[i]));
  }
  if (first !== null && second !== null && typeof first === "object" && typeof second === "object") {
    const a = first as RecordValue, b = second as RecordValue;
    return Object.keys(a).length === Object.keys(b).length
      && Object.keys(a).every(key => Object.hasOwn(b, key) && equal(a[key], b[key]));
  }
  return first === second;
}

function near(first: number, second: number): boolean {
  return Math.abs(first - second) <= Math.max(1e-9, 1e-12 * Math.max(Math.abs(first), Math.abs(second)));
}

function binding(value: unknown, path: string): void {
  const item = record(value, "source_id spatial_context_id source_asset_sha256 data_kind", path);
  text(item.source_id, path); text(item.spatial_context_id, path);
  requireValue(item.data_kind === "SYNTHETIC", `${path} data_kind`);
  nullable(item.source_asset_sha256, hash =>
    requireValue(/^[0-9a-f]{64}$/.test(text(hash, path)), `${path} sha256`));
}

function observation(value: unknown, path: string): RecordValue {
  const item = record(value,
    "observation_id target_id camera_id start_time end_time floor_id zone_id frames projected_path "
    + "provenance track_ids stitching_count fragment_count appearance_embedding appearance_labels "
    + "appearance_quality tracking_quality source_video_reference entry_direction exit_direction "
    + "projection_quality occlusion_quality observation_quality", path);
  for (const key of ["observation_id", "target_id", "camera_id"]) text(item[key], `${path}.${key}`);
  const start = number(item.start_time, path, 0), end = number(item.end_time, path, 0);
  requireValue(start <= end, `${path} range`);
  for (const key of ["floor_id", "zone_id", "source_video_reference"])
    nullable(item[key], value => { text(value, path, false); });
  for (const key of ["stitching_count", "fragment_count"])
    nullable(item[key], value => integer(value, path));
  for (const key of ["track_ids", "appearance_labels"])
    nullable(item[key], value => { strings(value, path); });
  nullable(item.appearance_embedding, value => array(value, path).forEach(v => number(v, path)));
  for (const key of ["entry_direction", "exit_direction"])
    nullable(item[key], value => vector(value, 3, path));
  for (const key of ["appearance_quality", "tracking_quality", "projection_quality",
    "occlusion_quality", "observation_quality"])
    nullable(item[key], value => quality(value, path));
  let lastFrame = -Infinity;
  for (const value of array(item.frames, `${path}.frames`)) {
    const frame = record(value,
      "frame_id timestamp target_id camera_id status point_2d provenance gap_reason occluder_id data_kind",
      `${path}.frame`);
    integer(frame.frame_id, path);
    const timestamp = number(frame.timestamp, path, 0);
    requireValue(timestamp > lastFrame && start <= timestamp && timestamp <= end, `${path} frame order`);
    lastFrame = timestamp;
    vector(frame.point_2d, 2, path);
    requireValue(frame.camera_id === item.camera_id && frame.target_id === item.target_id
      && frame.status === "OBSERVED" && frame.provenance === "OBSERVED"
      && frame.gap_reason === null && frame.occluder_id === null && frame.data_kind === "SYNTHETIC",
      `${path} frame evidence`);
  }
  const projections = array(item.projected_path, `${path}.projected_path`);
  const pointIds: string[] = [];
  let lastPoint = -Infinity;
  for (const value of projections) {
    const point = record(value,
      "point_id camera_id plane_id timestamp world_position projection_quality floor_id zone_id "
      + "observation_id provenance", `${path}.point`);
    pointIds.push(text(point.point_id, path)); text(point.plane_id, path);
    vector(point.world_position, 3, path); quality(point.projection_quality, path);
    nullable(point.floor_id, v => { text(v, path, false); });
    nullable(point.zone_id, v => { text(v, path, false); });
    const timestamp = number(point.timestamp, path, 0);
    requireValue(timestamp > lastPoint && start <= timestamp && timestamp <= end
      && point.camera_id === item.camera_id && point.provenance === "PROJECTED"
      && (point.observation_id === null || point.observation_id === item.observation_id),
      `${path} projected evidence`);
    lastPoint = timestamp;
  }
  requireValue(new Set(pointIds).size === pointIds.length, `${path} point identities`);
  enumValue(item.provenance, ["OBSERVED", "PROJECTED"], path);
  requireValue(item.provenance === "PROJECTED" ? projections.length > 0 : projections.length === 0,
    `${path} observation provenance`);
  return item;
}

function boundObservation(value: unknown, path: string): RecordValue {
  const item = record(value, "binding observation sample_ids", path);
  binding(item.binding, path); observation(item.observation, path);
  requireValue(strings(item.sample_ids, path, true, true).length > 0, `${path} sample_ids`);
  return item;
}

function candidate(value: unknown, path: string): RecordValue {
  const item = record(value,
    "candidate_id start_observation_id end_observation_id polyline navmesh_corridor path_length "
    + "minimum_travel_time estimated_travel_time spatial_cost temporal_cost semantic_regions "
    + "feasibility_flags path_score provenance", path);
  for (const key of ["candidate_id", "start_observation_id", "end_observation_id"]) text(item[key], path);
  array(item.polyline, path, 2).forEach(value => vector(value, 3, path));
  for (const key of ["navmesh_corridor", "semantic_regions", "feasibility_flags"]) strings(item[key], path);
  for (const key of ["path_length", "spatial_cost", "temporal_cost"]) number(item[key], path, 0);
  requireValue(number(item.estimated_travel_time, path, 0) >= number(item.minimum_travel_time, path, 0),
    `${path} travel times`);
  nullable(item.path_score, value => { number(value, path); });
  requireValue(item.provenance === "INFERRED_GAP", `${path} provenance`);
  return item;
}

function hypothesis(value: unknown, candidateIds: unknown[], extent: [number, number], path: string): void {
  const item = record(value,
    "hypothesis_id candidate_id kind timed_points segments minimum_travel_time temporal_slack "
    + "movement_duration dwell_duration uncertainty provenance", path);
  text(item.hypothesis_id, path); text(item.uncertainty, path);
  requireValue(candidateIds.includes(item.candidate_id), `${path} candidate reference`);
  enumValue(item.kind, ["DIRECT_PATH", "SLOWER_MOVEMENT", "DWELL", "DETOUR"], path);
  requireValue(item.provenance === "INFERRED_GAP", `${path} provenance`);
  const points = array(item.timed_points, path, 2).map(value =>
    record(value, "timestamp world_position provenance", path));
  let previous = -Infinity;
  for (const point of points) {
    const timestamp = number(point.timestamp, path, 0);
    requireValue(timestamp > previous && extent[0] <= timestamp && timestamp <= extent[1],
      `${path} point order/extents`);
    previous = timestamp; vector(point.world_position, 3, path);
    enumValue(point.provenance, ["PROJECTED", "INFERRED_GAP"], path);
  }
  const start = points[0].timestamp as number, end = points.at(-1)!.timestamp as number;
  const minimum = number(item.minimum_travel_time, path, 0), slack = number(item.temporal_slack, path, 0);
  const movement = number(item.movement_duration, path, 0), dwell = number(item.dwell_duration, path, 0);
  requireValue(near(minimum + slack, end - start) && near(movement + dwell, end - start)
    && movement >= minimum && (item.kind === "DWELL") === (dwell > 0), `${path} duration`);
  let cursor = start, movementSum = 0, dwellSum = 0;
  for (const value of array(item.segments, path, 1)) {
    const segment = record(value, "time_range kind provenance", path);
    const [a, b] = timeRange(segment.time_range, path, true);
    enumValue(segment.kind, ["MOVEMENT", "DWELL"], path);
    requireValue(segment.provenance === "INFERRED_GAP" && a === cursor
      && points.some(point => point.timestamp === a) && points.some(point => point.timestamp === b),
      `${path} segment boundaries`);
    const covered = points.filter(point => a <= (point.timestamp as number) && (point.timestamp as number) <= b);
    for (let i = 1; i < covered.length; i++)
      requireValue(equal(covered[i - 1].world_position, covered[i].world_position) === (segment.kind === "DWELL"),
        `${path} movement/dwell`);
    if (segment.kind === "DWELL") dwellSum += b - a;
    else movementSum += b - a;
    cursor = b;
  }
  requireValue(cursor === end && near(movementSum, movement) && near(dwellSum, dwell), `${path} segments`);
}

function metadata(item: RecordValue): void {
  for (const [key, value] of Object.entries(META)) requireValue(item[key] === value, key);
}

/** Validate JSON at the consumer boundary, then retain the supplied record/order. */
export function validateConsumerEvent(value: unknown): ConsumerEvent {
  const envelope = record(value, `${Object.keys(META).join(" ")} gap`, "consumer");
  metadata(envelope);
  const gap = record(envelope.gap, "binding start end search_result event", "gap");
  binding(gap.binding, "gap.binding");
  const start = boundObservation(gap.start, "gap.start"), end = boundObservation(gap.end, "gap.end");
  requireValue(equal(start.binding, gap.binding) && equal(end.binding, gap.binding), "gap endpoint bindings");
  const a = start.observation as RecordValue, b = end.observation as RecordValue;
  const event = record(gap.event,
    "event_id target_id time_range observation_ids candidates termination_reason trajectories", "event");
  text(event.event_id, "event_id"); text(event.target_id, "target_id");
  const extent = timeRange(event.time_range, "event.time_range", true);
  requireValue(event.target_id === a.target_id && event.target_id === b.target_id
    && equal(event.observation_ids, [a.observation_id, b.observation_id]), "event endpoint references");
  strings(event.observation_ids, "event.observation_ids", true, true);
  const from = array(a.projected_path, "start projection", 1).at(-1) as RecordValue;
  const to = array(b.projected_path, "end projection", 1)[0] as RecordValue;
  requireValue(extent[0] === from.timestamp && extent[1] === to.timestamp, "gap exact boundaries");
  const candidates = array(event.candidates, "candidates").map(value => candidate(value, "candidate"));
  const ids = candidates.map(item => item.candidate_id);
  requireValue(new Set(ids).size === ids.length, "candidate identities");
  for (const item of candidates)
    requireValue((event.observation_ids as unknown[]).includes(item.start_observation_id)
      && (event.observation_ids as unknown[]).includes(item.end_observation_id), "candidate endpoints");
  enumValue(event.termination_reason, TERMINATIONS, "event termination");
  requireValue(event.termination_reason !== "NO_FEASIBLE_PATH" || candidates.length === 0,
    "NO_FEASIBLE_PATH candidates");
  const trajectories = array(event.trajectories, "trajectories");
  const hypothesisIds: unknown[] = [];
  for (const value of trajectories) {
    hypothesis(value, ids, extent, "hypothesis");
    hypothesisIds.push((value as RecordValue).hypothesis_id);
  }
  requireValue(new Set(hypothesisIds).size === hypothesisIds.length, "hypothesis identities");
  const search = record(gap.search_result,
    "candidates termination_reason expanded_nodes complete rejection_reasons", "search_result");
  integer(search.expanded_nodes, "expanded_nodes"); strings(search.rejection_reasons, "rejection_reasons");
  requireValue(typeof search.complete === "boolean"
    && search.complete === ["COMPLETE", "NO_FEASIBLE_PATH"].includes(event.termination_reason as string)
    && search.termination_reason === event.termination_reason
    && equal(search.candidates, event.candidates), "search/Event parity and completeness");
  return value as ConsumerEvent;
}

/** Validate server replay markers against the Event, without inferring or ranking. */
export function validateReplayFrame(value: unknown, consumer: ConsumerEvent): ReplayFrame {
  const validated = validateConsumerEvent(consumer);
  const item = record(value, `${Object.keys(META).join(" ")} event_id timestamp markers`, "replay");
  metadata(item);
  const event = validated.gap.event, timestamp = number(item.timestamp, "replay timestamp", 0);
  requireValue(item.event_id === event.event_id && event.time_range[0] <= timestamp
    && timestamp <= event.time_range[1], "replay event/time");
  const markers = array(item.markers, "markers");
  requireValue(markers.length === event.trajectories.length, "all hypothesis markers");
  markers.forEach((value, index) => {
    const marker = record(value,
      "hypothesis_id candidate_id world_position provenance interpolated", "marker");
    const hypothesis = event.trajectories[index];
    requireValue(marker.hypothesis_id === hypothesis.hypothesis_id
      && marker.candidate_id === hypothesis.candidate_id, "marker order/references");
    vector(marker.world_position, 3, "marker position");
    enumValue(marker.provenance, ["PROJECTED", "INFERRED_GAP"], "marker provenance");
    requireValue(typeof marker.interpolated === "boolean", "marker interpolated");
    const points = hypothesis.timed_points;
    requireValue(points[0].timestamp <= timestamp && timestamp <= points.at(-1)!.timestamp,
      "marker hypothesis range");
    const exact = points.find(point => point.timestamp === timestamp);
    if (exact) {
      requireValue(!marker.interpolated && marker.provenance === exact.provenance
        && equal(marker.world_position, exact.world_position), "original keyframe marker");
    } else {
      requireValue(marker.interpolated && marker.provenance === "INFERRED_GAP", "display interpolation");
      const index = points.findIndex(point => point.timestamp > timestamp);
      const before = points[index - 1], after = points[index];
      const fraction = (timestamp - before.timestamp) / (after.timestamp - before.timestamp);
      const position = marker.world_position as number[];
      requireValue(position.every((value, axis) => near(value,
        before.world_position[axis] + fraction * (after.world_position[axis] - before.world_position[axis]))),
        "linear display marker");
    }
  });
  return value as ReplayFrame;
}
