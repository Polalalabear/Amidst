/** Presentation-only helpers and an actual media-time soft-synchronization clock. */
export function sampleCanonicalTrajectory(hypothesis, timestamp) {
  const points = hypothesis.timed_points;
  if (!Array.isArray(points) || points.length < 2 || !Number.isFinite(timestamp)) return null;
  if (timestamp < points[0].timestamp || timestamp > points.at(-1).timestamp) return null;
  const exact = points.find(point => point.timestamp === timestamp);
  if (exact) return {
    hypothesis_id: hypothesis.hypothesis_id, candidate_id: hypothesis.candidate_id,
    timestamp, world_position: [...exact.world_position], provenance: exact.provenance,
    interpolated: false, presentation_only: true,
  };
  const next = points.findIndex(point => point.timestamp > timestamp);
  const a = points[next - 1], b = points[next];
  const fraction = (timestamp - a.timestamp) / (b.timestamp - a.timestamp);
  return {
    hypothesis_id: hypothesis.hypothesis_id, candidate_id: hypothesis.candidate_id,
    timestamp, world_position: a.world_position.map((value, index) =>
      value + fraction * (b.world_position[index] - value)),
    provenance: 'INFERRED_GAP', interpolated: true, presentation_only: true,
  };
}

export function sampleAllAlternatives(hypotheses, timestamp) {
  return hypotheses.map(hypothesis => sampleCanonicalTrajectory(hypothesis, timestamp))
    .filter(marker => marker !== null);
}

export function statistics(samples) {
  const values = samples.filter(Number.isFinite).map(Math.abs).sort((a, b) => a - b);
  if (!values.length) return {count: 0, mean: null, p95: null};
  return {count: values.length, mean: values.reduce((a, b) => a + b, 0) / values.length,
    p95: values[Math.max(0, Math.ceil(values.length * 0.95) - 1)]};
}

export class SoftSyncClock {
  constructor({runRef, masterCameraRef, requestState, applyState, now = () => performance.now(),
    onTelemetry = () => {}, onTime = () => {}, onError = () => {}, requestIntervalMs = 80}) {
    this.runRef = runRef; this.masterCameraRef = masterCameraRef;
    this.requestState = requestState; this.applyState = applyState; this.now = now;
    this.onTelemetry = onTelemetry; this.onTime = onTime; this.onError = onError;
    this.requestIntervalMs = requestIntervalMs; this.epoch = 0; this.serial = 0;
    this.lastRequest = -Infinity; this.renderedTimestamp = null; this.masterTimestamp = null;
    this.closed = false; this.seekPending = null;
    this.skew = []; this.cameraSkew = []; this.seekRecovery = []; this.frameCount = 0;
    this.missingFrameSelections = 0; this.fallbackCallbacks = 0;
  }
  setMaster(cameraRef) {
    this.masterCameraRef = cameraRef; this.epoch++; this.serial++;
    this.masterTimestamp = null; this.lastRequest = -Infinity; this.seekPending = null;
  }
  seek(timestamp) {
    if (!Number.isFinite(timestamp) || timestamp < 0) throw Error('INVALID_SEEK');
    this.epoch++; this.serial++; this.lastRequest = -Infinity;
    this.seekPending = {timestamp, started: this.now(), epoch: this.epoch};
    return this.epoch;
  }
  close() {this.closed = true; this.epoch++; this.serial++;}
  async presented(cameraRef, mediaTime, startTime = 0, {actualFrame = true} = {}) {
    if (this.closed || !Number.isFinite(mediaTime) || !Number.isFinite(startTime)) return false;
    const timestamp = mediaTime + startTime;
    if (actualFrame) {
      this.frameCount++;
      if (cameraRef !== this.masterCameraRef && this.masterTimestamp !== null) {
        this.cameraSkew.push((timestamp - this.masterTimestamp) * 1000);
      }
    } else this.fallbackCallbacks++;
    if (cameraRef !== this.masterCameraRef) {this.emitTelemetry(); return false;}
    this.masterTimestamp = timestamp;
    if (actualFrame && this.renderedTimestamp !== null && this.seekPending === null) {
      this.skew.push((this.renderedTimestamp - timestamp) * 1000);
    }
    if (this.seekPending && Math.abs(timestamp - this.seekPending.timestamp) > 0.25) return false;
    const started = this.now();
    if (!this.seekPending && started - this.lastRequest < this.requestIntervalMs) {
      this.emitTelemetry(); return false;
    }
    this.lastRequest = started;
    const epoch = this.epoch, serial = ++this.serial;
    try {
      const state = await this.requestState(timestamp);
      if (this.closed || epoch !== this.epoch || serial !== this.serial) return false;
      if (state.run_ref !== this.runRef || !Number.isFinite(state.timestamp)
        || state.presentation_only !== true) throw Error('TIMELINE_BINDING_DENIED');
      this.applyState(state);
      this.renderedTimestamp = state.timestamp;
      this.missingFrameSelections += (state.frames || []).filter(frame => frame.status !== 'AVAILABLE').length;
      if (this.seekPending && actualFrame) {
        this.seekRecovery.push(this.now() - this.seekPending.started); this.seekPending = null;
      }
      this.onTime(state.timestamp); this.emitTelemetry(); return true;
    } catch (error) {
      if (!this.closed && epoch === this.epoch && serial === this.serial) this.onError(error);
      return false;
    }
  }
  telemetry() {
    return {synchronization: 'SOFT_SYNCHRONIZATION', actual_frame_callbacks: this.frameCount,
      media_to_3d_skew_ms: statistics(this.skew), camera_media_skew_ms: statistics(this.cameraSkew),
      seek_recovery_ms: statistics(this.seekRecovery), missing_frame_selections: this.missingFrameSelections,
      fallback_media_callbacks: this.fallbackCallbacks, dropped_video_frames: null,
      dropped_video_frames_reason: 'NOT_AVAILABLE_FROM_THIS_CLOCK',
      metric_source: 'ACTUAL_MEDIA_CALLBACKS_AND_APPLIED_PRESENTATION_STATE'};
  }
  emitTelemetry() {this.onTelemetry(this.telemetry());}
}

/** rVFC records presented media time. Fallback drives display but never invents frame metrics. */
export function observeVideo(video, info, clock, onFrame = () => {}) {
  let disposed = false, handle = null;
  if (typeof video.requestVideoFrameCallback === 'function') {
    const frame = (_now, metadata) => {
      if (disposed) return;
      clock.presented(info.camera_ref, metadata.mediaTime, info.start_time).catch(() => {});
      onFrame(metadata.mediaTime + info.start_time, metadata);
      if (!disposed) handle = video.requestVideoFrameCallback(frame);
    };
    handle = video.requestVideoFrameCallback(frame);
    return () => {disposed = true;
      if (handle !== null && typeof video.cancelVideoFrameCallback === 'function')
        video.cancelVideoFrameCallback(handle);};
  }
  const fallback = () => {
    if (disposed) return;
    clock.presented(info.camera_ref, video.currentTime, info.start_time, {actualFrame: false});
    onFrame(video.currentTime + info.start_time, null);
  };
  video.addEventListener('timeupdate', fallback); video.addEventListener('seeked', fallback);
  return () => {disposed = true; video.removeEventListener('timeupdate', fallback);
    video.removeEventListener('seeked', fallback);};
}
