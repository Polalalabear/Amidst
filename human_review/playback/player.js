/* Read-only display of existing, source-bound evidence. No decision mutations. */
(function (root) {
  'use strict';

  function relationText(position) {
    const relation = position?.graph_relation || {};
    if (relation.kind === 'NODE') return `${relation.node_alias} · ${relation.node_id}`;
    if (relation.kind === 'EDGE') return `${relation.edge_alias} · ${relation.from_node} → ${relation.to_node} · ${Math.round(relation.progress * 100)}%`;
    if (relation.kind === 'OUTSIDE_GAP_GRAPH') return relation.scope === 'BEFORE_DEPARTURE' ? 'N1 之前 · GAP graph 範圍外' : 'N2 之後 · GAP graph 範圍外';
    return '目前位置未提供 graph association';
  }

  function project(position, image) {
    const view = image.view;
    const delta = position.map((value, i) => value - view.position_bu[i]);
    const scale = image.width / view.ortho_scale_bu;
    const dot = axis => delta.reduce((sum, value, i) => sum + value * axis[i], 0);
    return [image.width / 2 + dot(view.right) * scale, image.height / 2 - dot(view.up) * scale];
  }

  function resolveAsset(base, relative) {
    if (typeof relative !== 'string' || !relative || /[\\:%?#\u0000]/.test(relative) || relative.startsWith('/') || relative.split('/').includes('..')) throw new Error('影像路徑超出指定資料夾');
    return base + relative;
  }

  class FrameController {
    constructor(options) {
      this.frameCount = options.frameCount;
      this.fps = options.fps;
      this.loadFrame = options.loadFrame;
      this.commitFrame = options.commitFrame;
      this.onState = options.onState || (() => {});
      this.schedule = options.schedule || ((fn, delay) => setTimeout(fn, delay));
      this.unschedule = options.unschedule || (id => clearTimeout(id));
      this.index = -1;
      this.requestedIndex = 0;
      this.playing = false;
      this.loading = false;
      this.speed = 1;
      this.loop = false;
      this.timer = null;
      this.generation = 0;
      this.error = null;
    }

    snapshot() {
      return { index: this.index, requestedIndex: this.requestedIndex, playing: this.playing, loading: this.loading, speed: this.speed, loop: this.loop, error: this.error };
    }

    emit() { this.onState(this.snapshot()); }

    pause() {
      this.playing = false;
      if (this.timer !== null) this.unschedule(this.timer);
      this.timer = null;
      this.emit();
    }

    async seek(value, { pause = true } = {}) {
      if (!Number.isFinite(value)) return false;
      if (pause) this.pause();
      const index = Math.min(this.frameCount - 1, Math.max(0, Math.round(value)));
      const generation = ++this.generation;
      this.requestedIndex = index;
      this.loading = true;
      this.error = null;
      this.emit();
      try {
        const frame = await this.loadFrame(index);
        if (generation !== this.generation) return false;
        this.commitFrame(index, frame);
        this.index = index;
        this.loading = false;
        this.emit();
        return true;
      } catch (error) {
        if (generation !== this.generation) return false;
        this.loading = false;
        this.error = error instanceof Error ? error.message : String(error);
        this.pause();
        return false;
      }
    }

    queueNext() {
      if (!this.playing || this.loading) return;
      if (this.timer !== null) this.unschedule(this.timer);
      this.timer = this.schedule(async () => {
        this.timer = null;
        if (!this.playing) return;
        if (this.index === this.frameCount - 1 && !this.loop) { this.pause(); return; }
        const target = this.index === this.frameCount - 1 ? 0 : this.index + 1;
        if (await this.seek(target, { pause: false })) this.queueNext();
      }, 1000 / this.fps / this.speed);
    }

    async play() {
      if (this.playing) return;
      this.playing = true;
      this.emit();
      if (this.index < 0 || this.index === this.frameCount - 1 || this.loading) {
        const target = this.index === this.frameCount - 1 ? 0 : this.requestedIndex;
        if (!await this.seek(target, { pause: false })) return;
      }
      this.queueNext();
    }

    toggle() { if (this.playing) this.pause(); else void this.play(); }
    step(delta) { return this.seek((this.loading ? this.requestedIndex : Math.max(0, this.index)) + delta); }
    setSpeed(value) { if (![0.5, 1, 2].includes(value)) return; this.speed = value; this.emit(); this.queueNext(); }
    setLoop(value) { this.loop = Boolean(value); this.emit(); }
  }

  const api = { FrameController, relationText, project, resolveAsset };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.Phase1Preview = api;
  if (typeof document === 'undefined') return;

  const $ = id => document.getElementById(id);
  const data = root.PHASE1_PREVIEW_DATA;
  if (!data?.motion?.frames?.length || !data?.topology?.frames || !data?.audit?.frames) {
    $('load-state').textContent = '預覽資料尚未物化。請依播放工作區的重建指令生成 data.js 與既有影格。';
    $('load-state').classList.add('error-message');
    $('phase-status').textContent = '預覽資料未就緒';
    for (const id of ['play', 'timeline', 'previous', 'next', 'camera-stills']) $(id).disabled = true;
    return;
  }

  const { motion, topology, audit } = data;
  const imageCache = new Map();
  const ns = 'http://www.w3.org/2000/svg';
  const colors = { cyan: '#48bee5', amber: '#f6b653', camera: '#28c9ce', red: '#e96875', line: '#132735', graph: '#b8cde1' };
  let stillGeneration = 0;
  let focusedPanel = null;

  function svgElement(tag, attributes = {}, parent) {
    const node = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
    if (parent) parent.append(node);
    return node;
  }
  function text(parent, point, value, { size = 22, color = colors.line, halo = true, weight = 650 } = {}) {
    const attributes = { x: point[0], y: point[1], fill: color, 'font-size': size, 'font-weight': weight };
    if (halo) Object.assign(attributes, { 'paint-order': 'stroke', stroke: '#ffffff', 'stroke-width': size / 6, 'stroke-linejoin': 'round' });
    const node = svgElement('text', attributes, parent);
    node.textContent = value;
    return node;
  }
  function line(parent, a, b, color, width = 3, dash = '') {
    return svgElement('line', { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: color, 'stroke-width': width, 'stroke-dasharray': dash, 'stroke-linecap': 'round' }, parent);
  }
  function circle(parent, point, radius, color, fill = color, width = 2) {
    return svgElement('circle', { cx: point[0], cy: point[1], r: radius, fill, stroke: color, 'stroke-width': width }, parent);
  }
  function path(parent, points, color, width = 3, dash = '') {
    return svgElement('polyline', { points: points.map(point => point.join(',')).join(' '), fill: 'none', stroke: color, 'stroke-width': width, 'stroke-linejoin': 'round', 'stroke-linecap': 'round', 'stroke-dasharray': dash }, parent);
  }
  function fragment() { return document.createDocumentFragment(); }
  function shortCamera(id) { return id.endsWith('_FRONT') ? 'FRONT' : id.endsWith('_REAR') ? 'REAR' : id; }
  function replayLabel(result) { return result?.in_frustum === false ? 'OUT_OF_FOV' : result?.ray_reason || 'N/A'; }
  function format(value, digits = 2) { return Number.isFinite(value) ? value.toFixed(digits) : 'N/A'; }
  function role(frame) { return frame.current_position?.state || (frame.role?.includes('GAP') ? 'GAP' : 'OBSERVED'); }

  function loadImage(source) {
    if (imageCache.has(source)) return imageCache.get(source);
    const promise = new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = async () => {
        try { if (image.decode) await image.decode(); resolve(image); }
        catch (_) { imageCache.delete(source); reject(new Error('影格解碼失敗')); }
      };
      image.onerror = () => { imageCache.delete(source); reject(new Error('影格載入失敗')); };
      image.src = source;
    });
    imageCache.set(source, promise);
    return promise;
  }

  const cameraAsset = path => resolveAsset(data.basePaths.camera, path);
  const motionAsset = index => resolveAsset(data.basePaths.motion, motion.frames[index].path);
  const wideAsset = cameraAsset(audit.images.wide.path);
  const sideAsset = cameraAsset(audit.images.side.path);

  const worldPoints = [...topology.edges.flatMap(edge => edge.raw_polyline_bu), ...topology.frames.map(frame => frame.current_position.schematic_position_bu)];
  const minX = Math.min(...worldPoints.map(point => point[0]));
  const maxX = Math.max(...worldPoints.map(point => point[0]));
  const minY = Math.min(...worldPoints.map(point => point[1]));
  const maxY = Math.max(...worldPoints.map(point => point[1]));
  function graphPoint(point) {
    const spanX = Math.max(maxX - minX, 0.0001), spanY = Math.max(maxY - minY, 0.0001);
    return [122 + (point[0] - minX) / spanX * 335, 340 - (point[1] - minY) / spanY * 285];
  }

  function topologyOverlay(frame) {
    const root = fragment();
    const fixed = svgElement('g', { 'data-role': 'fixed-topology' }, root);
    for (const edge of topology.edges) {
      const points = edge.floor_pixels;
      path(fixed, points, '#ffffff', 6);
      path(fixed, points, colors.line, 2.5);
      points.slice(1, -1).forEach(point => circle(fixed, point, 4.5, colors.line, 'white', 2));
      const middle = points.length > 2 ? [(points[1][0] + points[2][0]) / 2, (points[1][1] + points[2][1]) / 2] : [(points[0][0] + points[1][0]) / 2, (points[0][1] + points[1][1]) / 2];
      text(fixed, [middle[0] + (edge.alias === 'E2' ? -39 : 12), middle[1] - 10], edge.alias, { size: 18 });
    }
    for (const node of topology.nodes) {
      circle(fixed, node.floor_pixel, 8, 'white', colors.line, 2.5);
      text(fixed, [node.floor_pixel[0] - 39, node.floor_pixel[1] + 5], node.alias, { size: 19 });
    }
    const position = frame.current_position;
    const moving = svgElement('g', { 'data-role': 'current-person', 'data-frame-id': frame.frame_id, 'data-node-id': position.graph_relation.node_id || '', 'data-edge-id': position.graph_relation.edge_id || '' }, root);
    const foot = position.floor_pixel, landmark = position.raw_pixel;
    line(moving, foot, landmark, colors.cyan, 2, '5 5');
    circle(moving, landmark, 5, '#ffffff', colors.cyan, 2);
    text(moving, [landmark[0] + 10, landmark[1] + 4], 'L(t)', { size: 15, color: '#086d94' });
    circle(moving, foot, 13, '#ffffff', 'none', 6);
    circle(moving, foot, 13, colors.amber, 'none', 3);
    line(moving, [foot[0] - 5, foot[1]], [foot[0] + 5, foot[1]], '#99520a', 2);
    line(moving, [foot[0], foot[1] - 5], [foot[0], foot[1] + 5], '#99520a', 2);
    text(moving, [foot[0] + 23, foot[1] + 8], 'P(t)', { size: 21, color: '#99520a' });
    return root;
  }

  function graphOverlay(frame) {
    const root = fragment();
    const fixed = svgElement('g', { 'data-role': 'fixed-topology' }, root);
    for (const edge of topology.edges) {
      const points = edge.raw_polyline_bu.map(graphPoint);
      path(fixed, points, colors.graph, 2.3);
      const a = points[points.length - 2], b = points[points.length - 1];
      const angle = Math.atan2(b[1] - a[1], b[0] - a[0]);
      const tip = [b[0] - Math.cos(angle) * 11, b[1] - Math.sin(angle) * 11];
      path(fixed, [[tip[0] - Math.cos(angle - 0.5) * 10, tip[1] - Math.sin(angle - 0.5) * 10], tip, [tip[0] - Math.cos(angle + 0.5) * 10, tip[1] - Math.sin(angle + 0.5) * 10]], colors.graph, 2.3);
      points.slice(1, -1).forEach((point, index) => {
        svgElement('rect', { x: point[0] - 4, y: point[1] - 4, width: 8, height: 8, fill: '#152434', stroke: colors.graph, 'stroke-width': 1.6 }, fixed);
        text(fixed, [point[0] + (edge.alias === 'E2' ? -73 : 13), point[1] + 5], edge.interior_vertices[index].alias, { size: 13, color: '#92abc2', halo: false });
      });
      const center = points.length === 2 ? [(points[0][0] + points[1][0]) / 2, (points[0][1] + points[1][1]) / 2] : [(points[1][0] + points[2][0]) / 2, (points[1][1] + points[2][1]) / 2];
      text(fixed, [center[0] + (edge.alias === 'E2' ? -32 : 14), center[1] - 9], edge.alias, { size: 16, color: '#c6d9e9', halo: false });
    }
    for (const node of topology.nodes) {
      const point = graphPoint(node.raw_position_bu);
      circle(fixed, point, 6, '#e2edf6', '#e2edf6', 1);
      text(fixed, [point[0] - 40, point[1] + 5], node.alias, { size: 16, color: '#e2edf6', halo: false });
    }
    const position = frame.current_position;
    const group = svgElement('g', { 'data-role': 'current-person', 'data-frame-id': frame.frame_id, 'data-node-id': position.graph_relation.node_id || '', 'data-edge-id': position.graph_relation.edge_id || '' }, root);
    const point = graphPoint(position.schematic_position_bu);
    circle(group, point, 13, colors.amber, '#172b3f', 2.4);
    circle(group, [point[0], point[1] - 22], 4, colors.amber);
    path(group, [[point[0], point[1] - 18], [point[0], point[1] - 6]], colors.amber, 2);
    line(group, [point[0] - 7, point[1] - 13], [point[0] + 7, point[1] - 13], colors.amber, 2);
    path(group, [[point[0] - 6, point[1] + 1], [point[0], point[1] - 6], [point[0] + 6, point[1] + 1]], colors.amber, 2);
    text(group, [point[0] + 23, point[1] - 20], `P(t) · ${format(frame.timestamp, 1)} s`, { size: 16, color: colors.amber, halo: false });
    text(group, [point[0] + 23, point[1] + 1], role(frame), { size: 12, color: '#99b2c8', halo: false });
    return root;
  }

  function bodyOverlay(parent, image, foot) {
    const scale = audit.diagnostic_protocol?.scale_m_per_bu || 0.0247;
    const height = audit.binding.body_height_m / scale;
    const radius = audit.binding.body_radius_m / scale;
    const clearance = (audit.binding.body_radius_m + audit.binding.clearance_m) / scale;
    function ring(r, z, dashed = false) {
      const points = Array.from({ length: 25 }, (_, index) => { const angle = index / 24 * 2 * Math.PI; return project([foot[0] + Math.cos(angle) * r, foot[1] + Math.sin(angle) * r, foot[2] + z], image); });
      path(parent, points, '#ce7418', 3, dashed ? '8 6' : '');
    }
    ring(radius, 0); ring(radius, height); ring(clearance, 0, true);
    for (const angle of [0, Math.PI / 2, Math.PI, Math.PI * 1.5]) {
      const base = [foot[0] + Math.cos(angle) * radius, foot[1] + Math.sin(angle) * radius, foot[2]];
      line(parent, project(base, image), project([base[0], base[1], base[2] + height], image), '#ce7418', 2);
    }
    const head = project([foot[0], foot[1], foot[2] + height * 0.9], image);
    line(parent, project(foot, image), head, '#efaa44', 14);
    circle(parent, head, 14, '#8d4c0d', colors.amber, 2);
  }

  function cameraOverlay(image, frame) {
    const root = fragment();
    const group = svgElement('g', { 'data-role': 'current-person', 'data-frame-id': frame.frame_id }, root);
    const foot = project(frame.foot_position_bu, image);
    const landmark = project(frame.landmark_position_bu, image);
    for (const camera of audit.cameras) {
      const origin = project(camera.position_bu, image);
      const replay = frame.cameras.find(item => item.camera_id === camera.camera_id);
      for (const [result, target, isFoot] of [[replay.landmark_replay, landmark, false], [replay.foot_replay, foot, true]]) {
        if (result.hit) {
          const hit = project(result.hit.position_bu, image);
          line(group, origin, hit, colors.red, isFoot ? 3 : 4, isFoot ? '10 8' : '');
          line(group, hit, target, '#9aa9b5', 2.5, '9 9');
          circle(group, hit, 8, '#ffffff', colors.red, 2);
        } else line(group, origin, target, result.in_frustum ? colors.camera : '#899cac', isFoot ? 3 : 4, isFoot ? '10 8' : '');
      }
      circle(group, origin, 16, '#e7fbff', colors.camera, 3);
      text(group, [origin[0] + 24, origin[1] - 18], shortCamera(camera.camera_id), { size: 36, color: '#087e85' });
    }
    bodyOverlay(group, image, frame.foot_position_bu);
    line(group, foot, landmark, colors.cyan, 4, '10 7');
    circle(group, foot, 10, '#ffffff', colors.amber, 3);
    circle(group, landmark, 10, '#ffffff', colors.cyan, 3);
    text(group, [foot[0] + 25, foot[1] + 29], 'P(t) 腳底', { size: 32, color: '#95540f' });
    text(group, [landmark[0] + 25, landmark[1] - 19], 'L(t) landmark', { size: 32, color: '#087ba5' });
    return root;
  }

  function prepareFrame(index) {
    return Promise.all([motionAsset(index), wideAsset, sideAsset].map(loadImage)).then(() => ({
      topology: topologyOverlay(topology.frames[index]),
      graph: graphOverlay(topology.frames[index]),
      wide: cameraOverlay(audit.images.wide, audit.frames[index]),
      side: cameraOverlay(audit.images.side, audit.frames[index])
    }));
  }

  function commitFrame(index, prepared) {
    const frame = motion.frames[index], graphFrame = topology.frames[index], auditFrame = audit.frames[index];
    $('motion-image').src = motionAsset(index);
    $('wide-image').src = wideAsset;
    $('side-image').src = sideAsset;
    for (const [id, children] of [['motion-overlay', prepared.topology], ['graph-overlay', prepared.graph], ['wide-overlay', prepared.wide], ['side-overlay', prepared.side]]) $(id).replaceChildren(children);
    for (const id of ['motion-image', 'motion-overlay', 'graph-overlay', 'wide-image', 'wide-overlay', 'side-image', 'side-overlay']) $(id).setAttribute('data-loaded-frame', frame.frame_id);
    $('workspace').setAttribute('data-loaded-frame', frame.frame_id);
    $('timeline').value = String(index);
    $('timeline').setAttribute('aria-valuetext', `${format(frame.timestamp, 1)} 秒，影格 ${frame.frame_id}，${role(graphFrame)}`);
    $('time-current').textContent = `${format(frame.timestamp, 1)} s`;
    $('frame-counter').textContent = `${String(index + 1).padStart(2, '0')} / ${motion.frames.length}`;
    $('current-node').textContent = relationText(graphFrame.current_position);
    $('node-caption').textContent = relationText(graphFrame.current_position);
    $('state-badge').textContent = role(graphFrame);
    $('state-badge').classList.toggle('is-gap', role(graphFrame) === 'GAP');
    $('motion-caption').textContent = `${format(frame.timestamp, 1)} s · ${role(graphFrame) === 'GAP' ? '既有 inferred candidate' : 'public projected position'}`;
    $('projection-caption').textContent = `${frame.projection_method || '—'} / ${frame.confidence_state || '—'}`;
    $('wide-caption').textContent = auditFrame.cameras.map(camera => `${shortCamera(camera.camera_id)}：${camera.public_record.status}`).join(' · ');
    $('wide-caption').title = auditFrame.cameras.map(camera => `${shortCamera(camera.camera_id)} public ${camera.public_record.status} / landmark replay ${replayLabel(camera.landmark_replay)} / foot replay ${replayLabel(camera.foot_replay)}`).join('\n');
    $('side-caption').textContent = `landmark ↔ floor ${format(audit.binding.offset_m, 2)} m · body ${format(audit.binding.body_height_m, 2)} m`;
    $('sync-status').textContent = `四畫面同步 · frame ${frame.frame_id}`;
    if (index + 1 < motion.frames.length) loadImage(motionAsset(index + 1)).catch(() => {});
  }

  const controller = new FrameController({ frameCount: motion.frames.length, fps: motion.fps || 5, loadFrame: prepareFrame, commitFrame, onState: state => {
    $('play-label').textContent = state.playing ? '暫停' : '播放';
    $('play-icon').textContent = state.playing ? 'Ⅱ' : '▶';
    $('play').setAttribute('aria-label', state.playing ? '暫停' : '播放');
    $('play').setAttribute('aria-pressed', String(state.playing));
    $('loop').setAttribute('aria-pressed', String(state.loop));
    $('load-state').textContent = state.error ? `${state.error}；保留上一組完整畫面。再次拖曳時間軸可重試。` : state.loading ? `載入 ${format(motion.frames[state.requestedIndex].timestamp, 1)} s · 四畫面就緒後一起更新` : '';
    $('load-state').classList.toggle('error-message', Boolean(state.error));
    $('workspace').setAttribute('data-playback-state', state.error ? 'error' : state.loading ? 'loading' : state.playing ? 'playing' : 'paused');
  } });
  api.controller = controller;

  function readable(value) {
    if (value === null || value === undefined || value === '') return 'N/A';
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (Array.isArray(value)) return value.map(readable).join(' · ');
    if (typeof value === 'object') return value.label || value.status || Object.entries(value).map(([key, item]) => `${key}: ${readable(item)}`).join(' · ');
    return String(value);
  }
  function renderStatus() {
    const status = data.status || {};
    $('phase-status').textContent = readable(status.phase1 || status.status || '狀態見專案紀錄');
    const approval = status.human_approvals;
    $('approval-status').textContent = approval && typeof approval === 'object' && !Array.isArray(approval) && 'approved' in approval ? `人工決策 ${approval.approved}/${approval.total}${approval.status === 'APPROVED_AND_APPLIED' ? ' 已套用' : ' 已核准'}` : readable(approval);
    const host = $('status-content');
    host.replaceChildren();
    function section(title) {
      const item = document.createElement('section'); item.className = 'status-section';
      const heading = document.createElement('h3'); heading.textContent = title; item.append(heading); host.append(item); return item;
    }
    function paragraph(parent, value, className = 'status-description') { const node = document.createElement('p'); node.className = className; node.textContent = readable(value); parent.append(node); return node; }
    const date = document.createElement('p'); date.className = 'status-date'; date.textContent = `截至 ${readable(status.as_of)} · 固定 checkpoint 狀態`; host.append(date);
    const phase = section(status.phase1?.label || 'Phase 1');
    paragraph(phase, status.phase1?.detail || status.phase1);
    paragraph(phase, status.phase1?.status || 'N/A', 'status-code');
    const cases = section('Case 1–3 進度');
    for (const item of Array.isArray(status.cases) ? status.cases : []) {
      const card = document.createElement('article'); card.className = 'case-status-card';
      const title = document.createElement('h4'); title.textContent = item.label || item.id; card.append(title);
      const state = item.status || 'N/A';
      const label = state.includes('BLOCKED') ? '尚待完成' : state.includes('TEMPORAL_COMPONENT') ? '時間分量已完成' : state.includes('FORMAL_REVIEWED_LOCAL_RUN') ? '局部正式執行完成' : state;
      const badge = paragraph(card, label, 'case-status-badge'); badge.classList.toggle('is-pending', state.includes('BLOCKED') || state.includes('COMPONENT'));
      paragraph(card, item.detail || state); cases.append(card);
    }
    const authority = section('人工核准與物理範圍');
    paragraph(authority, approval?.label || readable(approval), 'status-emphasis');
    if (approval?.detail) paragraph(authority, approval.detail);
    paragraph(authority, status.physical?.label || 'Physical authority', 'status-emphasis');
    paragraph(authority, status.physical?.detail || readable(status.physical));
    if (status.physical?.status) paragraph(authority, status.physical.status, 'status-code');
    const checks = section('既有驗證紀錄');
    for (const check of Array.isArray(status.checks) ? status.checks : []) {
      const item = document.createElement('details'); item.className = 'check-row';
      const summary = document.createElement('summary');
      const label = document.createElement('span'); label.textContent = check.label || '驗證';
      const badge = document.createElement('span'); badge.className = 'check-state'; badge.textContent = check.status || 'N/A'; badge.classList.toggle('is-pending', !String(check.status).startsWith('PASS'));
      summary.append(label, badge); item.append(summary); paragraph(item, check.detail || check.status); checks.append(item);
    }
    const notes = section('播放素材與限制');
    paragraph(notes, '本頁沿用核准前生成的 public projection／inferred candidate 影格。圖中 pending 標籤記錄產生時狀態；目前核准與驗證進度以上方快照為準。人物姿勢、P(t) 與既有影格仍為 DIAGNOSTIC 顯示。');
    const list = document.createElement('ul'); list.className = 'status-notes';
    for (const note of Array.isArray(status.notes) ? status.notes : []) { const item = document.createElement('li'); item.textContent = readable(note); list.append(item); }
    notes.append(list);
    const provenance = document.createElement('details'); provenance.className = 'provenance-details';
    const summary = document.createElement('summary'); summary.textContent = '來源、完整 hashes 與狀態原始紀錄'; provenance.append(summary);
    const source = document.createElement('pre'); source.textContent = JSON.stringify(status, null, 2); provenance.append(source); host.append(provenance);
  }

  function focusPanel(name) {
    focusedPanel = name === focusedPanel ? null : name;
    $('view-grid').classList.toggle('is-focused', Boolean(focusedPanel));
    for (const panel of document.querySelectorAll('[data-panel]')) panel.classList.toggle('is-focused', panel.dataset.panel === focusedPanel);
    for (const button of document.querySelectorAll('[data-focus]')) button.setAttribute('aria-pressed', String(button.dataset.focus === focusedPanel));
    $('exit-focus').hidden = !focusedPanel;
  }
  function openDialog(id) { controller.pause(); $(id).showModal(); }
  async function showStills(frameId) {
    const token = ++stillGeneration;
    const rows = audit.images.camera_stills.filter(still => still.frame_id === frameId);
    $('still-load-state').textContent = '載入指定代表影格；共同時間軸維持原位置。';
    try {
      await Promise.all(rows.map(still => loadImage(cameraAsset(still.path))));
      if (token !== stillGeneration) return;
      const content = fragment();
      for (const still of rows) {
        const figure = document.createElement('figure'); figure.className = 'still-card'; figure.setAttribute('data-representative-frame', still.frame_id);
        const title = document.createElement('h3'); title.textContent = `${shortCamera(still.camera_id)} · ${format(still.timestamp, 1)} s · frame ${still.frame_id}`;
        const stage = document.createElement('div'); stage.className = 'still-stage';
        const image = document.createElement('img'); image.src = cameraAsset(still.path); image.alt = `${shortCamera(still.camera_id)} 固定代表影格，${format(still.timestamp, 1)} 秒`;
        const overlay = svgElement('svg', { viewBox: `0 0 ${still.width} ${still.height}`, 'aria-label': '指定代表影格的 landmark 與 foot 定位' });
        for (const [key, name, color] of [['landmark_replay', 'L landmark', colors.cyan], ['foot_replay', 'P foot', colors.amber]]) {
          const result = still[key];
          if (Array.isArray(result?.pixel)) { const point = result.pixel.map(value => value * still.pixel_scale); circle(overlay, point, 10, '#ffffff', color, 3); text(overlay, [point[0] + 17, point[1] - 14], name, { size: 29 }); }
        }
        const caption = document.createElement('figcaption'); caption.textContent = `固定代表影格 · landmark: ${replayLabel(still.landmark_replay)} / foot: ${replayLabel(still.foot_replay)}。定位標記可能在遮擋物後方，標記顯示不代表可見。`;
        stage.append(image, overlay); figure.append(title, stage, caption); content.append(figure);
      }
      $('still-grid').replaceChildren(content);
      $('still-load-state').textContent = `顯示 ${format(rows[0]?.timestamp, 1)} s 的 FRONT / REAR 代表影格。它們不是共同時間軸目前的連續影格。`;
    } catch (_) {
      if (token === stillGeneration) $('still-load-state').textContent = '代表影格載入失敗；保留上一組完整代表影格。';
    }
  }

  $('timeline').max = String(motion.frames.length - 1);
  $('time-end').textContent = `${format(motion.frames.at(-1).timestamp, 1)} s`;
  $('play').addEventListener('click', () => controller.toggle());
  $('previous').addEventListener('click', () => void controller.step(-1));
  $('next').addEventListener('click', () => void controller.step(1));
  $('timeline').addEventListener('input', event => void controller.seek(Number(event.target.value)));
  $('speed').addEventListener('change', event => controller.setSpeed(Number(event.target.value)));
  $('loop').addEventListener('click', () => controller.setLoop(!controller.loop));
  $('open-status').addEventListener('click', () => openDialog('status-dialog'));
  $('camera-stills').addEventListener('click', () => { openDialog('stills-dialog'); void showStills(Number($('still-time').value)); });
  $('still-time').addEventListener('change', event => void showStills(Number(event.target.value)));
  for (const close of document.querySelectorAll('.dialog-close')) close.addEventListener('click', () => close.closest('dialog').close());
  for (const button of document.querySelectorAll('[data-focus]')) button.addEventListener('click', () => focusPanel(button.dataset.focus));
  $('exit-focus').addEventListener('click', () => focusPanel(null));
  $('fullscreen').addEventListener('click', async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else if ($('workspace').requestFullscreen) await $('workspace').requestFullscreen(); }
    catch (_) { $('fullscreen').title = '此瀏覽器不支援全螢幕；可使用各視角右上角放大按鈕。'; }
  });
  document.addEventListener('fullscreenchange', () => $('fullscreen').setAttribute('aria-pressed', String(Boolean(document.fullscreenElement))));
  document.addEventListener('visibilitychange', () => { if (document.hidden) controller.pause(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && focusedPanel && !$('status-dialog').open && !$('stills-dialog').open) { focusPanel(null); return; }
    if (event.altKey || event.ctrlKey || event.metaKey || event.target?.isContentEditable || /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(event.target?.tagName || '') || $('status-dialog').open || $('stills-dialog').open) return;
    if (event.key === ' ' || event.code === 'Space') { event.preventDefault(); controller.toggle(); }
    else if (event.key === 'ArrowLeft') { event.preventDefault(); void controller.step(-1); }
    else if (event.key === 'ArrowRight') { event.preventDefault(); void controller.step(1); }
    else if (event.key === 'Home') { event.preventDefault(); void controller.seek(0); }
    else if (event.key === 'End') { event.preventDefault(); void controller.seek(motion.frames.length - 1); }
  });
  renderStatus();
  void controller.seek(0);
})(typeof window !== 'undefined' ? window : globalThis);
