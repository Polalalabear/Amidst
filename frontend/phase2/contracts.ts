/** Phase 2 transport only: synthetic seconds and unchanged Blender XYZ in metres. */
export type Vec3 = readonly [number, number, number];
export type TimeRange = readonly [number, number];
export type EvidenceProvenance = "OBSERVED" | "PROJECTED";
export type MarkerProvenance = "PROJECTED" | "INFERRED_GAP";
export type TerminationReason =
  | "COMPLETE" | "NO_FEASIBLE_PATH" | "MAX_PATHS_REACHED"
  | "MAX_SEARCH_NODES" | "MAX_BRANCH_FACTOR" | "SEARCH_TIMEOUT";

export interface StreamBinding {
  readonly source_id: string;
  readonly spatial_context_id: string;
  readonly source_asset_sha256: string | null;
  readonly data_kind: "SYNTHETIC";
}

export interface ObservationFrame {
  readonly frame_id: number;
  readonly timestamp: number;
  readonly target_id: string;
  readonly camera_id: string;
  readonly status: "OBSERVED";
  readonly point_2d: readonly [number, number];
  readonly provenance: "OBSERVED";
  readonly gap_reason: null;
  readonly occluder_id: null;
  readonly data_kind: "SYNTHETIC";
}

export interface ProjectedPoint {
  readonly point_id: string;
  readonly camera_id: string;
  readonly plane_id: string;
  readonly timestamp: number;
  readonly world_position: Vec3;
  readonly projection_quality: number;
  readonly floor_id: string | null;
  readonly zone_id: string | null;
  readonly observation_id: string | null;
  readonly provenance: "PROJECTED";
}

export interface Observation {
  readonly observation_id: string;
  readonly target_id: string;
  readonly camera_id: string;
  readonly start_time: number;
  readonly end_time: number;
  readonly floor_id: string | null;
  readonly zone_id: string | null;
  readonly frames: readonly ObservationFrame[];
  readonly projected_path: readonly ProjectedPoint[];
  readonly provenance: EvidenceProvenance;
  readonly track_ids: readonly string[] | null;
  readonly stitching_count: number | null;
  readonly fragment_count: number | null;
  readonly appearance_embedding: readonly number[] | null;
  readonly appearance_labels: readonly string[] | null;
  readonly appearance_quality: number | null;
  readonly tracking_quality: number | null;
  readonly source_video_reference: string | null;
  readonly entry_direction: Vec3 | null;
  readonly exit_direction: Vec3 | null;
  readonly projection_quality: number | null;
  readonly occlusion_quality: number | null;
  readonly observation_quality: number | null;
}

export interface BoundObservation {
  readonly binding: StreamBinding;
  readonly observation: Observation;
  readonly sample_ids: readonly string[];
}

export interface CandidateTrajectory {
  readonly candidate_id: string;
  readonly start_observation_id: string;
  readonly end_observation_id: string;
  readonly polyline: readonly Vec3[];
  readonly navmesh_corridor: readonly string[];
  readonly path_length: number;
  readonly minimum_travel_time: number;
  readonly estimated_travel_time: number;
  readonly spatial_cost: number;
  readonly temporal_cost: number;
  readonly semantic_regions: readonly string[];
  readonly feasibility_flags: readonly string[];
  readonly path_score: number | null;
  readonly provenance: "INFERRED_GAP";
}

export interface ReconstructionResult {
  readonly candidates: readonly CandidateTrajectory[];
  readonly termination_reason: TerminationReason;
  readonly expanded_nodes: number;
  readonly complete: boolean;
  readonly rejection_reasons: readonly string[];
}

export interface TimedTrajectoryPoint {
  readonly timestamp: number;
  readonly world_position: Vec3;
  readonly provenance: MarkerProvenance;
}

export interface TrajectorySegment {
  readonly time_range: TimeRange;
  readonly kind: "MOVEMENT" | "DWELL";
  readonly provenance: "INFERRED_GAP";
}

export interface TrajectoryHypothesis {
  readonly hypothesis_id: string;
  readonly candidate_id: string;
  readonly kind: "DIRECT_PATH" | "SLOWER_MOVEMENT" | "DWELL" | "DETOUR";
  readonly timed_points: readonly TimedTrajectoryPoint[];
  readonly segments: readonly TrajectorySegment[];
  readonly minimum_travel_time: number;
  readonly temporal_slack: number;
  readonly movement_duration: number;
  readonly dwell_duration: number;
  readonly uncertainty: string;
  readonly provenance: "INFERRED_GAP";
}

export interface Event {
  readonly event_id: string;
  readonly target_id: string;
  readonly time_range: TimeRange;
  readonly observation_ids: readonly string[];
  readonly candidates: readonly CandidateTrajectory[];
  readonly termination_reason: TerminationReason;
  readonly trajectories: readonly TrajectoryHypothesis[];
}

export interface BoundGapEvent {
  readonly binding: StreamBinding;
  readonly start: BoundObservation;
  readonly end: BoundObservation;
  readonly search_result: ReconstructionResult;
  readonly event: Event;
}

export interface ConsumerMetadata {
  readonly contract_version: "phase2.integration.v1";
  readonly data_kind: "SYNTHETIC";
  readonly time_basis: "CONFIGURED_SECONDS";
  readonly time_interval: "CLOSED";
  readonly coordinate_system: "BLENDER_RIGHT_HANDED_Z_UP";
  readonly units: "METRES";
}

export interface ConsumerEvent extends ConsumerMetadata {
  readonly gap: BoundGapEvent;
}

export interface ReplaySeek {
  readonly event_id: string;
  readonly timestamp: number;
}

export interface ReplayMarker {
  readonly hypothesis_id: string;
  readonly candidate_id: string;
  readonly world_position: Vec3;
  readonly provenance: MarkerProvenance;
  readonly interpolated: boolean;
}

export interface ReplayFrame extends ConsumerMetadata {
  readonly event_id: string;
  readonly timestamp: number;
  readonly markers: readonly ReplayMarker[];
}
