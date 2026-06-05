const $ = (id) => document.getElementById(id);
const imageInput = $('imageInput');
const handAsset = $('handAsset');
const analyzeBtn = $('analyzeBtn');
const renderBtn = $('renderBtn');
const logBox = $('logBox');
const progressWrap = $('progressWrap');
const progressBar = $('progressBar');
const progressText = $('progressText');
const downloadLinks = $('downloadLinks');
const videoOutput = $('videoOutput');
const quickPreviewBtn = $('quickPreviewBtn');
const cleanupOutputsBtn = $('cleanupOutputsBtn');
const cleanupStatus = $('cleanupStatus');
const motionPreviewCanvas = $('motionPreviewCanvas');
const sourcePreview = $('sourcePreview');
const sketchPreview = $('sketchPreview');
const sketchPreviewEmpty = $('sketchPreviewEmpty');
const videoOutputEmpty = $('videoOutputEmpty');
const passSummary = $('passSummary');
const semanticSummary = $('semanticSummary');
const healthBox = $('healthBox');
const handCalibImage = $('handCalibImage');
const handCalibVideo = $('handCalibVideo');
const calibEmpty = $('calibEmpty');
const tipCrosshair = $('tipCrosshair');
const calibrationBox = $('calibrationBox');
const calibrationReadout = $('calibrationReadout');
const playHandPreviewBtn = $('playHandPreviewBtn');
const handPreset = $('hand_preset');
const handSide = $('hand_side');
const handAssetFilename = $('hand_asset_filename');
const refreshAssetsBtn = $('refreshAssetsBtn');
const applyPresetBtn = $('applyPresetBtn');
const autoDetectTipBtn = $('autoDetectTipBtn');
const assetLibraryStatus = $('assetLibraryStatus');
const profileSelect = $('profile_select');
const profileName = $('profile_name');
const profileNotes = $('profile_notes');
const refreshProfilesBtn = $('refreshProfilesBtn');
const loadProfileBtn = $('loadProfileBtn');
const saveProfileBtn = $('saveProfileBtn');
const deleteProfileBtn = $('deleteProfileBtn');
const timelineFiles = $('timelineFiles');
const timelineProjectName = $('timeline_project_name');
const timelineJson = $('timeline_json');
const buildTimelineBtn = $('buildTimelineBtn');
const renderTimelineBtn = $('renderTimelineBtn');
const syncTimelineBtn = $('syncTimelineBtn');
const playTimelinePreviewBtn = $('playTimelinePreviewBtn');
const timelineEditor = $('timelineEditor');
const timelineStats = $('timelineStats');
const storyboardPreview = $('storyboardPreview');
const storyboardPreviewImage = $('storyboardPreviewImage');
const storyboardPreviewCaption = $('storyboardPreviewCaption');
const cameraMovePreset = $('camera_move_preset');
const artDirectorBtn = $('artDirectorBtn');
const timelineArtDirectorBtn = $('timelineArtDirectorBtn');
const applyArtDirectorBtn = $('applyArtDirectorBtn');
const qualitySummary = $('qualitySummary');
const artDirectorRecommendations = $('artDirectorRecommendations');
const sketchierPresetBtn = $('sketchierPresetBtn');
const sketchInputPresetBtn = $('sketchInputPresetBtn');
const portraitSequenceBtn = $('portraitSequenceBtn');

let timelineScenes = [];
let timelinePreviewIndex = 0;
let timelinePreviewTimer = null;
let lastArtDirectorAnalysis = null;
let lastPreviewPlan = null;
let lastSketchPreviewSrc = '';
let quickPreviewAnimation = null;
const filePreviewUrls = new Map();

const fields = [
  'input_type', 'subject_type', 'style_type', 'ratio', 'render_quality', 'sketch_strength', 'stroke_density',
  'human_randomness', 'duration_seconds', 'fps', 'max_strokes', 'paper_texture',
  'construction_pass', 'accent_pass', 'target_reveal', 'target_reveal_strength', 'hand_overlay', 'pencil_audio', 'ambient_track', 'ambient_level', 'drawing_audio_level', 'transition_sfx', 'transition_sfx_level', 'seed', 'trace_mode',
  'stroke_extraction_mode', 'planning_mode', 'art_director_json', 'camera_motion', 'camera_move_preset',
  'camera_zoom_start', 'camera_zoom_end', 'camera_pan_start_x', 'camera_pan_start_y', 'camera_pan_end_x', 'camera_pan_end_y',
  'smudge_pass', 'eraser_pass', 'title_card_text', 'watermark_text', 'hand_mode', 'hand_preset', 'hand_side', 'hand_asset_filename',
  'hand_scale', 'hand_opacity', 'hand_rotation', 'hand_tip_x', 'hand_tip_y', 'hand_video_loop', 'hand_video_playback_rate',
  'hand_video_frame_offset', 'hand_video_chroma_key', 'hand_lift_px', 'hand_shadow_strength', 'contact_correction_strength',
  'contact_position_smoothing', 'reposition_arc_strength', 'graphite_grain', 'charcoal_dust', 'ink_bleed', 'marker_overlap', 'stroke_taper',
  'motion_blur_strength'
];

['sketch_strength','stroke_density','human_randomness','target_reveal_strength','graphite_grain','charcoal_dust','ink_bleed','marker_overlap','stroke_taper','motion_blur_strength','drawing_audio_level','ambient_level','transition_sfx_level','camera_zoom_start','camera_zoom_end','camera_pan_start_x','camera_pan_start_y','camera_pan_end_x','camera_pan_end_y','hand_scale','hand_opacity','hand_shadow_strength','contact_correction_strength','contact_position_smoothing','reposition_arc_strength'].forEach(id => {
  const input = $(id);
  const label = $(`${id}_val`);
  if (input && label) input.addEventListener('input', () => label.textContent = input.value);
});

imageInput.addEventListener('change', () => {
  previewFile(imageInput.files?.[0], sourcePreview);
  resetSketchPreview();
});
handAsset.addEventListener('change', () => {
  handAssetFilename.value='';
  loadHandCalibrationAsset(handAsset.files?.[0]);
  assetLibraryStatus.textContent = 'New hand selected. It will be saved to the library after auto-detect or render.';
});
handAssetFilename.addEventListener('change', () => loadLibraryAssetPreview());
applyPresetBtn.addEventListener('click', () => applyCurrentPreset());
refreshAssetsBtn.addEventListener('click', () => { loadHandAssets(); loadHandPresets(); });
autoDetectTipBtn.addEventListener('click', () => autoDetectTip());
refreshProfilesBtn.addEventListener('click', () => loadProfiles());
loadProfileBtn.addEventListener('click', () => loadSelectedProfile());
saveProfileBtn.addEventListener('click', () => saveCurrentProfile());
deleteProfileBtn.addEventListener('click', () => deleteSelectedProfile());
timelineFiles.addEventListener('change', () => buildTimelineFromSelectedFiles());
buildTimelineBtn.addEventListener('click', () => buildTimelineFromSelectedFiles());
syncTimelineBtn.addEventListener('click', () => syncEditorFromTimelineJson());
playTimelinePreviewBtn.addEventListener('click', () => toggleStoryboardPreview());
renderTimelineBtn.addEventListener('click', () => renderTimelineQueued());
quickPreviewBtn.addEventListener('click', () => toggleQuickMotionPreview());
cleanupOutputsBtn.addEventListener('click', () => cleanupGeneratedOutputs());
cameraMovePreset.addEventListener('change', () => applyCameraPreset());
artDirectorBtn.addEventListener('click', () => analyzeCurrentImageWithArtDirector());
timelineArtDirectorBtn.addEventListener('click', () => analyzeTimelineWithArtDirector());
applyArtDirectorBtn.addEventListener('click', () => applyLastArtDirectorRecommendations());
sketchierPresetBtn.addEventListener('click', () => applySketchierPreset());
sketchInputPresetBtn.addEventListener('click', () => applySketchInputPreset());
portraitSequenceBtn.addEventListener('click', () => applyPortraitArtistSequence());
['hand_tip_x','hand_tip_y','hand_scale','hand_rotation','hand_opacity'].forEach(id => $(id)?.addEventListener('input', updateCalibrationOverlay));

const dropZone = $('dropZone');
['dragenter','dragover'].forEach(evt => dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add('drag'); }));
['dragleave','drop'].forEach(evt => dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.remove('drag'); }));
dropZone.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files?.[0];
  if (!file) return;
  imageInput.files = e.dataTransfer.files;
  previewFile(file, sourcePreview);
  resetSketchPreview();
});

function applyCameraPreset() {
  const preset = cameraMovePreset.value || 'static';
  const updates = {
    static: [100, 100, 0, 0, 0, 0],
    zoom_in: [100, 122, 0, 0, 0, 0],
    zoom_out: [122, 100, 0, 0, 0, 0],
    pan_left_to_right: [100, 100, -55, 0, 55, 0],
    pan_right_to_left: [100, 100, 55, 0, -55, 0],
    pan_top_to_bottom: [100, 100, 0, -55, 0, 55],
    pan_bottom_to_top: [100, 100, 0, 55, 0, -55],
    ken_burns: [108, 126, -18, -10, 18, 12],
    push_in_left: [104, 124, -40, 0, -8, 0],
    push_in_right: [104, 124, 40, 0, 8, 0],
  };
  const values = updates[preset] || updates.static;
  ['camera_zoom_start','camera_zoom_end','camera_pan_start_x','camera_pan_start_y','camera_pan_end_x','camera_pan_end_y'].forEach((id, idx) => {
    const el = $(id);
    if (!el) return;
    el.value = values[idx];
    const label = $(`${id}_val`);
    if (label) label.textContent = String(values[idx]);
  });
}

async function analyzeCurrentImageWithArtDirector() {
  try {
    const file = imageInput.files?.[0];
    if (!file) throw new Error('Choose a current image first.');
    const fd = new FormData();
    fd.append('file', file);
    log('Running Art Director analysis…');
    const res = await fetch('/api/art-director/analyze', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Art Director analysis failed.');
    lastArtDirectorAnalysis = { type: 'single', data };
    renderArtDirectorReport(data);
    log(`Art Director complete: ${data.detected_subject}, quality ${data.quality_score}/100`);
  } catch (err) {
    log(err.message || String(err));
  }
}

async function analyzeTimelineWithArtDirector() {
  try {
    const files = Array.from(timelineFiles.files || []);
    if (!files.length) throw new Error('Select timeline scene images first.');
    const fd = new FormData();
    for (const file of files) fd.append('files', file);
    log('Running timeline Art Director analysis…');
    const res = await fetch('/api/art-director/timeline', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Timeline Art Director analysis failed.');
    lastArtDirectorAnalysis = { type: 'timeline', data };
    renderTimelineArtDirectorReport(data);
    log(`Timeline Art Director complete: ${data.scene_count} scenes, average quality ${data.average_quality_score}/100`);
  } catch (err) {
    log(err.message || String(err));
  }
}

function renderArtDirectorReport(data) {
  const warnings = data.warnings || [];
  const fixes = data.suggested_fixes || [];
  const settings = data.recommended_settings || {};
  qualitySummary.className = `quality-summary score-${data.quality_label || 'good'}`;
  qualitySummary.innerHTML = `
    <strong>Quality ${data.quality_score}/100 · ${data.quality_label}</strong>
    <span>${data.subject_label} · Recommended style: ${data.recommended_style}</span>
  `;
  artDirectorRecommendations.className = 'art-director-report';
  artDirectorRecommendations.innerHTML = `
    <div class="recommend-grid">
      <div><strong>Subject</strong><span>${data.detected_subject}</span></div>
      <div><strong>Style</strong><span>${data.recommended_style}</span></div>
      <div><strong>Render</strong><span>${settings.render_quality || 'standard'}</span></div>
      <div><strong>Strokes</strong><span>${settings.stroke_density || '-'} density · ${settings.max_strokes || '-'} max</span></div>
    </div>
    <h4>Warnings</h4>
    ${warnings.length ? `<ul>${warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>` : '<p>No major quality warnings.</p>'}
    <h4>Suggested fixes</h4>
    ${fixes.length ? `<ul>${fixes.map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul>` : '<p>Input looks ready for rendering.</p>'}
    <h4>Suggested caption</h4>
    <p>${escapeHtml(data.captions?.caption || '')}</p>
  `;
}

function renderTimelineArtDirectorReport(data) {
  qualitySummary.className = 'quality-summary score-good';
  qualitySummary.innerHTML = `<strong>Timeline quality ${data.average_quality_score}/100</strong><span>${data.scene_count} analyzed scene(s)</span>`;
  artDirectorRecommendations.className = 'art-director-report';
  artDirectorRecommendations.innerHTML = `
    <div class="recommend-grid">
      <div><strong>Scenes</strong><span>${data.scene_count}</span></div>
      <div><strong>Global render</strong><span>${data.global_recommendations?.render_quality || 'standard'}</span></div>
      <div><strong>Planning</strong><span>${data.global_recommendations?.planning_mode || 'art_director_json'}</span></div>
      <div><strong>SFX</strong><span>${data.global_recommendations?.transition_sfx ? 'on' : 'off'}</span></div>
    </div>
    ${(data.scenes || []).map((row, idx) => `
      <div class="quality-scene-row">
        <strong>${idx + 1}. ${escapeHtml(row.scene.title)}</strong>
        <span>${row.analysis.quality_score}/100 · ${row.analysis.detected_subject} · ${row.analysis.recommended_style}</span>
      </div>
    `).join('')}
  `;
}

function setIfExists(id, value) {
  const el = $(id);
  if (!el || value === undefined || value === null) return;
  if (el.type === 'checkbox') el.checked = !!value;
  else el.value = value;
  const label = $(`${id}_val`);
  if (label) label.textContent = String(el.value);
}

function applyRecommendedSettings(settings = {}) {
  for (const [key, value] of Object.entries(settings)) setIfExists(key, value);
  updateCalibrationOverlay();
}

function applySketchierPreset() {
  applyRecommendedSettings({
    input_type: 'photo',
    style_type: 'pencil',
    render_quality: 'preview',
    trace_mode: 'opencv',
    stroke_extraction_mode: 'hybrid',
    sketch_strength: 90,
    stroke_density: 88,
    human_randomness: 16,
    max_strokes: 5200,
    graphite_grain: 78,
    stroke_taper: 68,
    motion_blur_strength: 8,
    construction_pass: true,
    accent_pass: true,
    smudge_pass: true,
    eraser_pass: true,
    target_reveal: true,
    target_reveal_strength: 78,
    camera_motion: true,
  });
  log('Applied sketchier render settings. Click Generate sketch preview to inspect the stroke plan before rendering.');
}

function applySketchInputPreset() {
  applyRecommendedSettings({
    input_type: 'sketch',
    style_type: 'pencil',
    render_quality: 'preview',
    trace_mode: 'opencv',
    stroke_extraction_mode: 'hybrid',
    sketch_strength: 68,
    stroke_density: 76,
    human_randomness: 10,
    max_strokes: 6200,
    graphite_grain: 72,
    stroke_taper: 64,
    motion_blur_strength: 6,
    construction_pass: true,
    accent_pass: true,
    smudge_pass: true,
    eraser_pass: false,
    target_reveal: true,
    target_reveal_strength: 92,
  });
  log('Using uploaded sketch directly. Click Generate sketch preview; it should stay close to the uploaded drawing.');
}

function applyPortraitArtistSequence() {
  const plan = {
    subject_type: 'portrait',
    artist_sequence: [
      'eyes',
      'eyebrows',
      'lips',
      'nose',
      'face cut',
      'hair',
      'shading and soft graphite'
    ],
    region_priority: {
      left_eye: -96,
      right_eye: -95,
      left_eyebrow: -88,
      right_eyebrow: -87,
      mouth: -76,
      nose: -66,
      face_outline: -52,
      jaw_cheek: -48,
      hair_top: -20,
      hair_side: -16,
      neck_clothing: 8,
      background: 26
    },
    region_layer_overrides: {
      left_eye: 'key',
      right_eye: 'key',
      left_eyebrow: 'key',
      right_eyebrow: 'key',
      mouth: 'key',
      nose: 'key',
      face_outline: 'contour',
      hair_top: 'secondary',
      hair_side: 'secondary'
    },
    layer_notes: {
      layout: 'Only light guide marks before facial features.',
      key: 'Draw eyes first, then eyebrows, lips, and nose.',
      contour: 'Draw face cut after focal features.',
      secondary: 'Build hair with longer grouped strokes.',
      shading: 'Finish with soft graphite shading where needed.',
      accent: 'Use final accents sparingly for pupils, lash line, lips, and darkest hair.'
    }
  };
  applyRecommendedSettings({
    subject_type: 'portrait',
    planning_mode: 'art_director_json',
    art_director_json: JSON.stringify(plan, null, 2),
    human_randomness: 8,
    stroke_density: 78,
    max_strokes: 6200,
    target_reveal: true,
    target_reveal_strength: 90
  });
  log('Applied portrait artist sequence: eyes, eyebrows, lips, nose, face cut, hair, then shading.');
}

function applyLastArtDirectorRecommendations() {
  if (!lastArtDirectorAnalysis) {
    log('Run Art Director analysis first.');
    return;
  }
  if (lastArtDirectorAnalysis.type === 'single') {
    const data = lastArtDirectorAnalysis.data;
    applyRecommendedSettings(data.recommended_settings || {});
    $('planning_mode').value = 'art_director_json';
    $('art_director_json').value = JSON.stringify(data.art_director_json || {}, null, 2);
    if (data.captions?.title) $('title_card_text').value = data.captions.title;
    log('Applied single-image Art Director recommendations.');
  } else {
    const data = lastArtDirectorAnalysis.data;
    applyRecommendedSettings(data.global_recommendations || {});
    timelineScenes = (data.timeline_json || []).map((scene, idx) => ({ ...scene, scene_id: scene.scene_id || `scene_${String(idx + 1).padStart(2, '0')}` }));
    renderTimelineEditor();
    syncTimelineJson();
    renderStoryboardPreview(0);
    if (data.scenes?.[0]?.analysis?.art_director_json) {
      $('planning_mode').value = 'art_director_json';
      $('art_director_json').value = JSON.stringify(data.scenes[0].analysis.art_director_json, null, 2);
    }
    log('Applied timeline Art Director recommendations.');
  }
}

function getTimelineFileMap() {
  const files = Array.from(timelineFiles.files || []);
  const map = new Map();
  for (const file of files) {
    map.set(file.name, file);
    if (!filePreviewUrls.has(file.name)) filePreviewUrls.set(file.name, URL.createObjectURL(file));
  }
  return map;
}

function defaultSceneForFile(file, idx) {
  return {
    scene_id: `scene_${String(idx + 1).padStart(2, '0')}`,
    source: file.name,
    title: file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '),
    duration_seconds: 6,
    transition: idx === 0 ? 'cut' : (idx % 3 === 1 ? 'zoomfade' : 'fade'),
    transition_duration: idx === 0 ? 0.0 : 0.7,
    camera_move_preset: idx % 2 === 0 ? 'zoom_in' : 'ken_burns',
    ambient_track: idx % 2 === 0 ? 'studio_room' : 'street_busker',
    subject_type: '',
    style_type: '',
    notes: '',
  };
}

function buildTimelineFromSelectedFiles() {
  const files = Array.from(timelineFiles.files || []);
  if (!files.length) {
    log('Select timeline scene images first.');
    return;
  }
  timelineScenes = files.map((file, idx) => defaultSceneForFile(file, idx));
  renderTimelineEditor();
  syncTimelineJson();
  renderStoryboardPreview(0);
  log(`Built visual timeline for ${files.length} scenes.`);
}

function timelineScenePayload(scene, idx) {
  return {
    scene_id: scene.scene_id || `scene_${String(idx + 1).padStart(2, '0')}`,
    source: scene.source,
    title: scene.title || `Scene ${idx + 1}`,
    duration_seconds: Number(scene.duration_seconds || 6),
    transition: scene.transition || (idx === 0 ? 'cut' : 'fade'),
    transition_duration: Number(scene.transition_duration || 0),
    camera_move_preset: scene.camera_move_preset || 'static',
    ambient_track: scene.ambient_track || $('ambient_track')?.value || 'none',
    ...(scene.subject_type ? { subject_type: scene.subject_type } : {}),
    ...(scene.style_type ? { style_type: scene.style_type } : {}),
    ...(scene.notes ? { notes: scene.notes } : {}),
  };
}

function syncTimelineJson() {
  timelineJson.value = JSON.stringify(timelineScenes.map(timelineScenePayload), null, 2);
  updateTimelineStats();
}

function syncEditorFromTimelineJson() {
  try {
    const parsed = JSON.parse(timelineJson.value || '[]');
    if (!Array.isArray(parsed)) throw new Error('Timeline JSON must be an array.');
    const fileMap = getTimelineFileMap();
    timelineScenes = parsed.map((scene, idx) => ({
      ...defaultSceneForFile(fileMap.get(scene.source) || { name: scene.source || `scene${idx + 1}.png` }, idx),
      ...scene,
    }));
    renderTimelineEditor();
    renderStoryboardPreview(0);
    updateTimelineStats();
    log(`Loaded ${timelineScenes.length} scenes from Timeline JSON.`);
  } catch (err) {
    log(err.message || String(err));
  }
}

function updateTimelineStats() {
  const total = timelineScenes.reduce((sum, scene) => sum + Number(scene.duration_seconds || 0) + Number(scene.transition_duration || 0), 0);
  timelineStats.textContent = timelineScenes.length
    ? `${timelineScenes.length} scene(s) · approx ${total.toFixed(1)}s including transitions`
    : 'No timeline scenes yet.';
}

function renderTimelineEditor() {
  if (!timelineScenes.length) {
    timelineEditor.className = 'timeline-editor empty';
    timelineEditor.textContent = 'Build the timeline to edit scenes visually.';
    updateTimelineStats();
    return;
  }
  timelineEditor.className = 'timeline-editor';
  const fileMap = getTimelineFileMap();
  timelineEditor.innerHTML = timelineScenes.map((scene, idx) => {
    const src = filePreviewUrls.get(scene.source) || '';
    const missing = !fileMap.has(scene.source);
    return `
      <article class="scene-card ${missing ? 'missing' : ''}" draggable="true" data-index="${idx}">
        <div class="scene-thumb">${src ? `<img src="${src}" alt="${scene.title || scene.source}" />` : '<span>No preview</span>'}</div>
        <div class="scene-body">
          <div class="scene-head">
            <strong>${idx + 1}. ${scene.source || 'Missing source'}</strong>
            <span>${missing ? 'source not selected' : 'ready'}</span>
          </div>
          <div class="grid two compact">
            <label>Title<input data-scene-field="title" value="${escapeHtml(scene.title || '')}" /></label>
            <label>Duration<input type="number" min="1" max="120" data-scene-field="duration_seconds" value="${scene.duration_seconds || 6}" /></label>
            <label>Transition<select data-scene-field="transition">${options(['cut','fade','dipblack','wipe_left','wipe_right','zoomfade'], scene.transition || 'fade')}</select></label>
            <label>Transition seconds<input type="number" step="0.1" min="0" max="3" data-scene-field="transition_duration" value="${scene.transition_duration || 0}" /></label>
            <label>Camera<select data-scene-field="camera_move_preset">${options(['static','zoom_in','zoom_out','pan_left_to_right','pan_right_to_left','pan_top_to_bottom','pan_bottom_to_top','ken_burns','push_in_left','push_in_right'], scene.camera_move_preset || 'static')}</select></label>
            <label>Ambient<select data-scene-field="ambient_track">${options(['none','studio_room','paper_rustle','street_busker'], scene.ambient_track || 'none')}</select></label>
            <label>Subject override<select data-scene-field="subject_type">${options(['','auto','portrait','architecture','pet','product','landscape','logo'], scene.subject_type || '')}</select></label>
            <label>Style override<select data-scene-field="style_type">${options(['','pencil','charcoal','ink','marker'], scene.style_type || '')}</select></label>
          </div>
          <label>Notes<input data-scene-field="notes" value="${escapeHtml(scene.notes || '')}" /></label>
          <div class="scene-actions">
            <button type="button" data-scene-action="preview">Preview</button>
            <button type="button" data-scene-action="up">↑</button>
            <button type="button" data-scene-action="down">↓</button>
            <button type="button" data-scene-action="duplicate">Duplicate</button>
            <button type="button" data-scene-action="delete">Delete</button>
          </div>
        </div>
      </article>
    `;
  }).join('');
  updateTimelineStats();
}

function options(values, selected) {
  return values.map(value => `<option value="${value}" ${value === selected ? 'selected' : ''}>${value || 'global/default'}</option>`).join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
}

function updateSceneFromControl(control) {
  const card = control.closest('.scene-card');
  if (!card) return;
  const idx = Number(card.dataset.index);
  const field = control.dataset.sceneField;
  if (!timelineScenes[idx] || !field) return;
  const numeric = ['duration_seconds', 'transition_duration'].includes(field);
  timelineScenes[idx][field] = numeric ? Number(control.value || 0) : control.value;
  syncTimelineJson();
}

function moveScene(from, to) {
  if (to < 0 || to >= timelineScenes.length || from === to) return;
  const [scene] = timelineScenes.splice(from, 1);
  timelineScenes.splice(to, 0, scene);
  timelineScenes.forEach((scene, idx) => scene.scene_id = `scene_${String(idx + 1).padStart(2, '0')}`);
  renderTimelineEditor();
  syncTimelineJson();
  renderStoryboardPreview(Math.max(0, Math.min(to, timelineScenes.length - 1)));
}

function handleSceneAction(button) {
  const card = button.closest('.scene-card');
  if (!card) return;
  const idx = Number(card.dataset.index);
  const action = button.dataset.sceneAction;
  if (action === 'preview') renderStoryboardPreview(idx);
  if (action === 'up') moveScene(idx, idx - 1);
  if (action === 'down') moveScene(idx, idx + 1);
  if (action === 'duplicate') {
    const copy = { ...timelineScenes[idx], scene_id: `scene_${String(timelineScenes.length + 1).padStart(2, '0')}`, title: `${timelineScenes[idx].title || 'Scene'} Copy` };
    timelineScenes.splice(idx + 1, 0, copy);
    renderTimelineEditor();
    syncTimelineJson();
  }
  if (action === 'delete') {
    timelineScenes.splice(idx, 1);
    renderTimelineEditor();
    syncTimelineJson();
    renderStoryboardPreview(Math.min(idx, Math.max(0, timelineScenes.length - 1)));
  }
}

function renderStoryboardPreview(idx = 0) {
  if (!timelineScenes.length) {
    storyboardPreview.className = 'storyboard-preview empty';
    storyboardPreviewImage.classList.add('hidden');
    storyboardPreviewCaption.textContent = 'Select images and build the timeline.';
    return;
  }
  timelinePreviewIndex = Math.max(0, Math.min(idx, timelineScenes.length - 1));
  const scene = timelineScenes[timelinePreviewIndex];
  const src = filePreviewUrls.get(scene.source);
  storyboardPreview.className = 'storyboard-preview';
  if (src) {
    storyboardPreviewImage.src = src;
    storyboardPreviewImage.classList.remove('hidden');
  } else {
    storyboardPreviewImage.classList.add('hidden');
  }
  storyboardPreviewCaption.textContent = `${timelinePreviewIndex + 1}/${timelineScenes.length} · ${scene.title || scene.source} · ${scene.duration_seconds || 0}s · ${scene.transition || 'cut'} · ${scene.camera_move_preset || 'static'}`;
}

function toggleStoryboardPreview() {
  if (!timelineScenes.length) {
    log('Build a timeline before playing storyboard preview.');
    return;
  }
  if (timelinePreviewTimer) {
    clearInterval(timelinePreviewTimer);
    timelinePreviewTimer = null;
    playTimelinePreviewBtn.textContent = 'Play storyboard preview';
    return;
  }
  playTimelinePreviewBtn.textContent = 'Stop storyboard preview';
  renderStoryboardPreview(timelinePreviewIndex || 0);
  timelinePreviewTimer = setInterval(() => {
    timelinePreviewIndex = (timelinePreviewIndex + 1) % timelineScenes.length;
    renderStoryboardPreview(timelinePreviewIndex);
  }, 1200);
}

// Timeline card editing and drag/drop.
timelineEditor.addEventListener('input', (event) => {
  if (event.target?.dataset?.sceneField) updateSceneFromControl(event.target);
});
timelineEditor.addEventListener('change', (event) => {
  if (event.target?.dataset?.sceneField) updateSceneFromControl(event.target);
});
timelineEditor.addEventListener('click', (event) => {
  const button = event.target.closest?.('button[data-scene-action]');
  if (button) handleSceneAction(button);
});
timelineEditor.addEventListener('dragstart', (event) => {
  const card = event.target.closest?.('.scene-card');
  if (card) event.dataTransfer.setData('text/plain', card.dataset.index);
});
timelineEditor.addEventListener('dragover', (event) => event.preventDefault());
timelineEditor.addEventListener('drop', (event) => {
  event.preventDefault();
  const from = Number(event.dataTransfer.getData('text/plain'));
  const card = event.target.closest?.('.scene-card');
  if (!card || Number.isNaN(from)) return;
  const to = Number(card.dataset.index);
  moveScene(from, to);
});

function buildTimelineFormData() {
  const files = Array.from(timelineFiles.files || []);
  if (!files.length) throw new Error('Please select one or more timeline scene images.');
  const fd = new FormData();
  for (const file of files) fd.append('files', file);
  for (const id of fields) {
    const el = $(id);
    if (!el) continue;
    if (el.type === 'checkbox') fd.append(id, el.checked ? 'true' : 'false');
    else if (id === 'art_director_json' && $('planning_mode').value !== 'art_director_json') fd.append(id, '');
    else fd.append(id, el.value);
  }
  fd.append('timeline_json', timelineJson.value || '');
  fd.append('project_name', timelineProjectName.value || 'sketch_timeline');
  fd.append('hand_overlay', $('hand_mode').value === 'none' ? 'false' : 'true');
  if (['uploaded','video'].includes($('hand_mode').value) && handAsset.files?.[0]) {
    fd.append('hand_asset', handAsset.files[0]);
  }
  return fd;
}

async function renderTimelineQueued() {
  try {
    const fd = buildTimelineFormData();
    setBusy(true);
    showProgress('Queueing multi-scene timeline…', 8);
    const res = await fetch('/api/timeline/render-queued', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not queue the timeline render.');
    log(`Timeline job queued: ${data.job_id}`);
    await pollJob(data.job_id);
  } catch (err) {
    log(err.message || String(err));
    setBusy(false);
  }
}

function resetSketchPreview() {
  if (sketchPreview) {
    sketchPreview.removeAttribute('src');
    sketchPreview.classList.add('hidden', 'placeholder');
  }
  if (sketchPreviewEmpty) sketchPreviewEmpty.classList.remove('hidden');
  lastPreviewPlan = null;
  lastSketchPreviewSrc = '';
  stopQuickMotionPreview();
  if (quickPreviewBtn) quickPreviewBtn.disabled = true;
}

function showSketchPreview(src) {
  if (!sketchPreview || !src) return;
  sketchPreview.src = src;
  sketchPreview.classList.remove('hidden', 'placeholder');
  if (sketchPreviewEmpty) sketchPreviewEmpty.classList.add('hidden');
}

function resetRenderedVideo() {
  if (videoOutput) {
    videoOutput.removeAttribute('src');
    videoOutput.classList.add('hidden');
  }
  if (motionPreviewCanvas) motionPreviewCanvas.classList.add('hidden');
  if (videoOutputEmpty) videoOutputEmpty.classList.remove('hidden');
}

function showRenderedVideo(src) {
  if (!videoOutput || !src) return;
  if (motionPreviewCanvas) motionPreviewCanvas.classList.add('hidden');
  videoOutput.src = src;
  videoOutput.classList.remove('hidden');
  if (videoOutputEmpty) videoOutputEmpty.classList.add('hidden');
}

function previewFile(file, img) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => { img.src = reader.result; img.classList.remove('hidden'); };
  reader.readAsDataURL(file);
}

function buildFormData(includeHand = false) {
  const file = imageInput.files?.[0];
  if (!file) throw new Error('Please choose an image or sketch first.');
  const fd = new FormData();
  fd.append('file', file);
  for (const id of fields) {
    const el = $(id);
    if (!el) continue;
    if (el.type === 'checkbox') fd.append(id, el.checked ? 'true' : 'false');
    else if (id === 'art_director_json' && $('planning_mode').value !== 'art_director_json') fd.append(id, '');
    else fd.append(id, el.value);
  }
  fd.append('hand_overlay', $('hand_mode').value === 'none' ? 'false' : 'true');
  if (includeHand && ['uploaded','video'].includes($('hand_mode').value) && handAsset.files?.[0]) {
    fd.append('hand_asset', handAsset.files[0]);
  }
  return fd;
}

function loadHandCalibrationAsset(file) {
  if (!file) return;
  const url = URL.createObjectURL(file);
  handCalibImage.classList.add('hidden');
  handCalibVideo.classList.add('hidden');
  calibEmpty.classList.add('hidden');
  if (file.type.startsWith('video/')) {
    $('hand_mode').value = 'video';
    handCalibVideo.src = url;
    handCalibVideo.classList.remove('hidden');
    handCalibVideo.currentTime = 0;
    handCalibVideo.play().catch(() => {});
  } else {
    $('hand_mode').value = 'uploaded';
    handCalibImage.src = url;
    handCalibImage.classList.remove('hidden');
  }
  updateCalibrationOverlay();
}

calibrationBox.addEventListener('click', (event) => {
  const media = handCalibVideo.classList.contains('hidden') ? handCalibImage : handCalibVideo;
  if (!media || media.classList.contains('hidden')) return;
  const rect = media.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;
  const x = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
  const y = Math.max(0, Math.min(100, ((event.clientY - rect.top) / rect.height) * 100));
  $('hand_tip_x').value = x.toFixed(1);
  $('hand_tip_y').value = y.toFixed(1);
  updateCalibrationOverlay();
});

playHandPreviewBtn.addEventListener('click', () => {
  if (handCalibVideo.classList.contains('hidden')) return;
  if (handCalibVideo.paused) handCalibVideo.play().catch(() => {});
  else handCalibVideo.pause();
});

function updateCalibrationOverlay() {
  const media = handCalibVideo.classList.contains('hidden') ? handCalibImage : handCalibVideo;
  const x = Number($('hand_tip_x').value || 18);
  const y = Number($('hand_tip_y').value || 78);
  calibrationReadout.textContent = `Tip anchor: ${x.toFixed(1)}%, ${y.toFixed(1)}%`;
  requestAnimationFrame(() => {
    if (!media || media.classList.contains('hidden')) {
      tipCrosshair.style.display = 'none';
      return;
    }
    const boxRect = calibrationBox.getBoundingClientRect();
    const mediaRect = media.getBoundingClientRect();
    tipCrosshair.style.display = 'block';
    tipCrosshair.style.left = `${mediaRect.left - boxRect.left + mediaRect.width * x / 100}px`;
    tipCrosshair.style.top = `${mediaRect.top - boxRect.top + mediaRect.height * y / 100}px`;
  });
}

async function loadHandPresets() {
  try {
    const res = await fetch('/api/presets/hand');
    const data = await res.json();
    const presets = data.presets || [];
    handPreset.innerHTML = '<option value="">Load preset…</option>' + presets.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
  } catch (err) {
    assetLibraryStatus.textContent = 'Could not load presets.';
  }
}

async function loadHandAssets() {
  try {
    const previous = handAssetFilename.value;
    const res = await fetch('/api/assets/hand');
    const data = await res.json();
    const assets = data.assets || [];
    handAssetFilename.innerHTML = '<option value="">Use uploaded asset only</option>' + assets.map(a => `<option value="${a.filename}">${a.filename} (${a.type})</option>`).join('');
    const keepPrevious = previous && assets.some(a => a.filename === previous);
    if (keepPrevious) {
      handAssetFilename.value = previous;
    } else if (assets.length) {
      handAssetFilename.value = assets[0].filename;
      loadLibraryAssetPreview();
    }
    assetLibraryStatus.textContent = assets.length
      ? `Using saved hand: ${handAssetFilename.value || assets[0].filename}. Library has ${assets.length} asset(s).`
      : 'Library empty. Upload a hand asset once; it will be saved for future runs.';
  } catch (err) {
    assetLibraryStatus.textContent = 'Could not load hand asset library.';
  }
}

async function loadLibraryAssetPreview() {
  const filename = handAssetFilename.value;
  if (!filename) return;
  handAsset.value = '';
  const isVideo = /\.(webm|mp4|mov|mkv)$/i.test(filename);
  const url = `/assets/${filename}`;
  handCalibImage.classList.add('hidden');
  handCalibVideo.classList.add('hidden');
  calibEmpty.classList.add('hidden');
  if (isVideo) {
    $('hand_mode').value = 'video';
    handCalibVideo.src = url;
    handCalibVideo.classList.remove('hidden');
    handCalibVideo.play().catch(() => {});
  } else {
    $('hand_mode').value = 'uploaded';
    handCalibImage.src = url;
    handCalibImage.classList.remove('hidden');
  }
  updateCalibrationOverlay();
}

async function applyCurrentPreset() {
  try {
    const res = await fetch('/api/presets/hand');
    const data = await res.json();
    const preset = (data.presets || []).find(p => p.id === handPreset.value);
    if (!preset) return;
    $('hand_side').value = preset.hand_side || 'right';
    if (preset.style_type && $('style_type').value === 'pencil') $('style_type').value = preset.style_type;
    ['hand_mode','hand_scale','hand_opacity','hand_rotation','hand_tip_x','hand_tip_y','hand_video_playback_rate','hand_video_frame_offset','hand_lift_px','hand_shadow_strength'].forEach(id => {
      if (preset[id] !== undefined && $(id)) $(id).value = preset[id];
    });
    if (preset.hand_video_loop !== undefined) $('hand_video_loop').checked = !!preset.hand_video_loop;
    if (preset.hand_video_chroma_key !== undefined) $('hand_video_chroma_key').checked = !!preset.hand_video_chroma_key;
    ['hand_scale','hand_opacity','hand_shadow_strength'].forEach(id => { const label = $(`${id}_val`); if (label) label.textContent = $(id).value; });
    updateCalibrationOverlay();
    assetLibraryStatus.textContent = `Applied preset: ${preset.name}`;
  } catch (err) {
    log('Could not apply preset');
  }
}

async function autoDetectTip() {
  try {
    const fd = new FormData();
    fd.append('hand_side', handSide.value || 'right');
    if (handAsset.files?.[0]) fd.append('hand_asset', handAsset.files[0]);
    else if (handAssetFilename.value) fd.append('asset_filename', handAssetFilename.value);
    else throw new Error('Upload or select a hand asset first.');
    const res = await fetch('/api/hand/auto-tip', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Auto-detect failed');
    $('hand_tip_x').value = data.tip_x;
    $('hand_tip_y').value = data.tip_y;
    updateCalibrationOverlay();
    assetLibraryStatus.textContent = `Detected tip at ${data.tip_x}%, ${data.tip_y}% (${Math.round((data.confidence || 0) * 100)}% confidence)`;
    if (data.asset_name && !handAssetFilename.value) {
      await loadHandAssets();
      handAssetFilename.value = data.asset_name;
      loadLibraryAssetPreview();
    }
  } catch (err) {
    log(err.message || String(err));
  }
}

async function loadProfiles() {
  try {
    const res = await fetch('/api/profiles');
    const data = await res.json();
    const profiles = data.profiles || [];
    profileSelect.innerHTML = '<option value="">Select saved profile…</option>' + profiles.map(p => `<option value="${p.name}">${p.name}</option>`).join('');
  } catch (err) {
    log('Could not load profiles');
  }
}

function applySettingsObject(settings) {
  for (const [key, value] of Object.entries(settings || {})) {
    const el = $(key);
    if (!el) continue;
    if (el.type === 'checkbox') el.checked = !!value;
    else el.value = value;
    const label = $(`${key}_val`);
    if (label) label.textContent = el.value;
  }
  updateCalibrationOverlay();
}

async function loadSelectedProfile() {
  try {
    if (!profileSelect.value) throw new Error('Choose a profile first.');
    const res = await fetch(`/api/profiles/${encodeURIComponent(profileSelect.value)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not load profile');
    profileName.value = data.name || '';
    profileNotes.value = data.notes || '';
    applySettingsObject(data.settings || {});
    if (data.settings?.hand_asset_filename) {
      handAssetFilename.value = data.settings.hand_asset_filename;
      loadLibraryAssetPreview();
    }
    assetLibraryStatus.textContent = `Loaded profile: ${data.name}`;
  } catch (err) {
    log(err.message || String(err));
  }
}

function currentSettingsPayload() {
  const settings = {};
  for (const id of fields) {
    const el = $(id);
    if (!el) continue;
    settings[id] = el.type === 'checkbox' ? el.checked : el.value;
  }
  return settings;
}

async function saveCurrentProfile() {
  try {
    const name = (profileName.value || '').trim();
    if (!name) throw new Error('Enter a profile name first.');
    const payload = { name, notes: (profileNotes.value || '').trim(), settings: currentSettingsPayload() };
    const res = await fetch('/api/profiles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not save profile');
    await loadProfiles();
    profileSelect.value = data.name;
    assetLibraryStatus.textContent = `Saved profile: ${data.name}`;
  } catch (err) {
    log(err.message || String(err));
  }
}

async function deleteSelectedProfile() {
  try {
    const name = profileSelect.value || profileName.value;
    if (!name) throw new Error('Choose a profile to delete.');
    const res = await fetch(`/api/profiles/${encodeURIComponent(name)}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not delete profile');
    await loadProfiles();
    if (profileSelect.value === name) profileSelect.value = '';
    if (profileName.value === name) profileName.value = '';
    assetLibraryStatus.textContent = `Deleted profile: ${name}`;
  } catch (err) {
    log(err.message || String(err));
  }
}

function setBusy(isBusy) {
  analyzeBtn.disabled = isBusy;
  renderBtn.disabled = isBusy;
}

function log(message, data = null) {
  const time = new Date().toLocaleTimeString();
  logBox.textContent = `[${time}] ${message}` + (data ? `\n${JSON.stringify(data, null, 2)}` : '');
}

async function refreshHealth() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    healthBox.innerHTML = `Backend: <strong>${data.status}</strong><br>FFmpeg: <strong>${data.ffmpeg_found ? 'found' : 'missing'}</strong><br>Potrace: ${data.tracing.potrace_found ? 'found' : 'optional'} · VTracer: ${data.tracing.vtracer_found ? 'found' : 'optional'}`;
  } catch (err) {
    healthBox.textContent = 'Backend not reachable. Run python run_backend.py';
  }
}
refreshHealth();
loadHandPresets();
loadHandAssets();
loadProfiles();
applyCameraPreset();

analyzeBtn.addEventListener('click', async () => {
  try {
    setBusy(true);
    log('Generating sketch preview and stroke plan…');
    const res = await fetch('/api/analyze', { method: 'POST', body: buildFormData(false) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Analyze failed');
    lastPreviewPlan = data.plan;
    lastSketchPreviewSrc = data.sketch_preview;
    if (quickPreviewBtn) quickPreviewBtn.disabled = false;
    showSketchPreview(data.sketch_preview);
    renderPassSummary(data.plan.pass_summary || []);
    renderSemanticSummary(data.plan.semantic_regions || [], data.plan.layer_plan || []);
    log(`Sketch preview ready: ${data.plan.stroke_count} strokes, subject ${data.plan.subject_type}`, data.plan.warnings || []);
  } catch (err) {
    log(err.message || String(err));
  } finally {
    setBusy(false);
  }
});

renderBtn.addEventListener('click', async () => {
  try {
    setBusy(true);
    downloadLinks.innerHTML = '';
    resetRenderedVideo();
    progressWrap.classList.remove('hidden');
    progressBar.style.width = '0%';
    progressText.textContent = 'Uploading and queueing render…';
    log('Starting queued render…');
    const res = await fetch('/api/render-queued', { method: 'POST', body: buildFormData(true) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not start render');
    await pollJob(data.job_id);
  } catch (err) {
    log(err.message || String(err));
  } finally {
    setBusy(false);
  }
});

async function pollJob(jobId) {
  while (true) {
    const res = await fetch(`/api/jobs/${jobId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not read job');
    progressBar.style.width = `${data.progress}%`;
    progressText.textContent = `${data.status}: ${data.message} (${data.progress}%)`;
    if (data.status === 'done') {
      handleRenderResult(data.result);
      log('Render complete.', data.result.warnings || []);
      return;
    }
    if (data.status === 'expired') {
      handleRenderResult(data.result);
      log(data.message || 'This render no longer has files in the outputs folder.', data.result?.warnings || []);
      return;
    }
    if (data.status === 'failed') {
      throw new Error(data.error || 'Render failed');
    }
    await new Promise(resolve => setTimeout(resolve, 1100));
  }
}

async function cleanupGeneratedOutputs() {
  const ok = window.confirm('Delete generated videos, previews, plans, audio, and frame folders from outputs? Hand assets and saved profiles will be kept.');
  if (!ok) return;
  try {
    setBusy(true);
    cleanupOutputsBtn.disabled = true;
    cleanupStatus.textContent = 'Cleaning generated files...';
    const res = await fetch('/api/outputs/cleanup', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not clean generated files.');
    stopQuickMotionPreview();
    resetRenderedVideo();
    downloadLinks.innerHTML = '<p class="muted">Generated files were cleaned. Start a new render to create fresh downloads.</p>';
    progressWrap.classList.add('hidden');
    const reclaimedMb = (Number(data.reclaimed_bytes || 0) / (1024 * 1024)).toFixed(1);
    const summary = `Removed ${data.removed_files || 0} files and ${data.removed_dirs || 0} folders (${reclaimedMb} MB).`;
    cleanupStatus.textContent = summary;
    log(summary, data.errors || []);
  } catch (err) {
    cleanupStatus.textContent = 'Cleanup failed.';
    log(err.message || String(err));
  } finally {
    cleanupOutputsBtn.disabled = false;
    setBusy(false);
  }
}

function handleRenderResult(result) {
  if (!result) return;
  renderPassSummary(result.pass_summary || []);
  renderSemanticSummary(result.semantic_regions || [], result.layer_plan || []);
  const files = result.files || {};
  downloadLinks.innerHTML = '';
  if (!Object.keys(files).length) {
    resetRenderedVideo();
    downloadLinks.innerHTML = '<p class="muted">Render files were removed from the outputs folder. Start a new render to create fresh downloads.</p>';
    return;
  }
  for (const [name, url] of Object.entries(files)) {
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    a.textContent = `Download ${name.toUpperCase()}`;
    downloadLinks.appendChild(a);
  }
  if (files.mp4) {
    showRenderedVideo(files.mp4);
  }
  if (handAsset.files?.[0]) {
    handAsset.value = '';
    loadHandAssets();
  }
}

function stopQuickMotionPreview() {
  if (quickPreviewAnimation) {
    cancelAnimationFrame(quickPreviewAnimation);
    quickPreviewAnimation = null;
  }
  if (quickPreviewBtn) quickPreviewBtn.textContent = 'Play quick motion preview';
}

async function toggleQuickMotionPreview() {
  if (quickPreviewAnimation) {
    stopQuickMotionPreview();
    return;
  }
  if (!lastPreviewPlan?.strokes?.length || !lastSketchPreviewSrc) {
    log('Generate sketch preview first, then play the quick motion preview.');
    return;
  }
  try {
    const targetImage = await loadImage(lastSketchPreviewSrc);
    playQuickMotionPreview(lastPreviewPlan, targetImage);
  } catch (err) {
    log(err.message || String(err));
  }
}

function playQuickMotionPreview(plan, targetImage) {
  const canvas = motionPreviewCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const settings = plan.settings || {};
  const width = Number(settings.width || targetImage.naturalWidth || 720);
  const height = Number(settings.height || targetImage.naturalHeight || 1280);
  canvas.width = width;
  canvas.height = height;
  canvas.classList.remove('hidden');
  if (videoOutput) videoOutput.classList.add('hidden');
  if (videoOutputEmpty) videoOutputEmpty.classList.add('hidden');
  if (quickPreviewBtn) quickPreviewBtn.textContent = 'Stop quick motion preview';

  const strokes = plan.strokes || [];
  const durationMs = Math.max(
    Number(settings.duration_seconds || 0) * 1000,
    ...strokes.map(stroke => Number(stroke.end_ms || 0)),
    1000,
  );
  const previewMs = Math.min(9000, Math.max(4500, durationMs * 0.42));
  const targetReveal = $('target_reveal')?.checked || settings.target_reveal || settings.input_type === 'sketch';
  const revealStrength = Math.max(0, Math.min(1, Number($('target_reveal_strength')?.value || settings.target_reveal_strength || 85) / 100));
  const startedAt = performance.now();

  const draw = (now) => {
    const elapsed = now - startedAt;
    const p = Math.min(1, elapsed / previewMs);
    const t = p * durationMs;
    drawQuickPreviewFrame(ctx, width, height, strokes, targetImage, t, p, targetReveal, revealStrength);
    if (p < 1) {
      quickPreviewAnimation = requestAnimationFrame(draw);
    } else {
      stopQuickMotionPreview();
    }
  };
  quickPreviewAnimation = requestAnimationFrame(draw);
  log('Playing quick browser preview. Full render still controls final hand, audio, camera, and MP4 quality.');
}

function drawQuickPreviewFrame(ctx, width, height, strokes, targetImage, t, p, targetReveal, revealStrength) {
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#f2ebdb';
  ctx.fillRect(0, 0, width, height);

  if (targetReveal) {
    drawQuickTargetReveal(ctx, width, height, strokes, targetImage, t, p, revealStrength);
  }

  for (const stroke of strokes) {
    const start = Number(stroke.start_ms || 0);
    const end = Number(stroke.end_ms || start + stroke.duration_ms || start + 1);
    if (t < start) break;
    const progress = t >= end ? 1 : (t - start) / Math.max(1, end - start);
    drawQuickStroke(ctx, stroke, progress, targetReveal);
  }
}

function drawQuickTargetReveal(ctx, width, height, strokes, targetImage, t, p, revealStrength) {
  const mask = document.createElement('canvas');
  mask.width = width;
  mask.height = height;
  const maskCtx = mask.getContext('2d');
  maskCtx.clearRect(0, 0, width, height);
  maskCtx.lineCap = 'round';
  maskCtx.lineJoin = 'round';

  for (const stroke of strokes) {
    const start = Number(stroke.start_ms || 0);
    const end = Number(stroke.end_ms || start + stroke.duration_ms || start + 1);
    if (t < start) break;
    const progress = t >= end ? 1 : (t - start) / Math.max(1, end - start);
    drawQuickRevealStroke(maskCtx, stroke, progress);
  }

  const softened = document.createElement('canvas');
  softened.width = width;
  softened.height = height;
  const softCtx = softened.getContext('2d');
  softCtx.filter = `blur(${Math.round(7 + revealStrength * 10)}px)`;
  softCtx.drawImage(mask, 0, 0);
  softCtx.filter = 'none';
  softCtx.globalCompositeOperation = 'lighter';
  softCtx.globalAlpha = 0.62;
  softCtx.drawImage(mask, 0, 0);

  const catchUp = smoothstep(Math.max(0, Math.min(1, (p - 0.74) / 0.26)));
  if (catchUp > 0) {
    softCtx.globalCompositeOperation = 'source-over';
    softCtx.globalAlpha = catchUp * revealStrength;
    softCtx.fillStyle = '#fff';
    softCtx.fillRect(0, 0, width, height);
  }

  const revealed = document.createElement('canvas');
  revealed.width = width;
  revealed.height = height;
  const revealCtx = revealed.getContext('2d');
  revealCtx.drawImage(targetImage, 0, 0, width, height);
  revealCtx.globalCompositeOperation = 'destination-in';
  revealCtx.drawImage(softened, 0, 0);

  ctx.save();
  ctx.globalAlpha = Math.min(1, 0.88 + revealStrength * 0.12);
  ctx.drawImage(revealed, 0, 0);
  ctx.restore();
}

function drawQuickRevealStroke(ctx, stroke, progress) {
  const points = partialStrokePoints(stroke.points || [], progress);
  if (points.length < 2 || stroke.effect === 'erase') return;
  const layer = stroke.layer || '';
  const thickness = Math.max(1, Number(stroke.thickness || 1.2));
  const width = layer === 'shading' || layer === 'texture' || stroke.effect === 'smudge'
    ? Math.max(24, thickness * 14)
    : Math.max(12, thickness * 9);
  ctx.save();
  ctx.globalAlpha = layer === 'shading' || layer === 'texture' ? 0.7 : 0.95;
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = width;
  ctx.beginPath();
  traceSmoothPath(ctx, points);
  ctx.stroke();
  ctx.restore();
}

function drawQuickStroke(ctx, stroke, progress, targetReveal = false) {
  const points = partialStrokePoints(stroke.points || [], progress);
  if (points.length < 2) return;
  const effect = stroke.effect || 'draw';
  if (effect === 'erase') return;
  const layer = stroke.layer || '';
  const opacity = Math.max(0.08, Math.min(0.82, Number(stroke.opacity || 0.55)));
  const thickness = Math.max(1, Number(stroke.thickness || 1.2));
  const alphaBase = targetReveal ? 0.24 : 0.68;
  const alpha = effect === 'smudge' || layer === 'shading' ? opacity * 0.18 : opacity * alphaBase;
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.strokeStyle = `rgba(35, 33, 30, ${alpha})`;
  ctx.lineWidth = effect === 'smudge' ? thickness * 3.2 : Math.max(0.7, thickness * (targetReveal ? 0.72 : 1));
  ctx.beginPath();
  traceSmoothPath(ctx, points);
  ctx.stroke();
  ctx.restore();
}

function traceSmoothPath(ctx, points) {
  ctx.moveTo(points[0][0], points[0][1]);
  if (points.length === 2) {
    ctx.lineTo(points[1][0], points[1][1]);
    return;
  }
  for (let i = 1; i < points.length - 1; i++) {
    const midX = (points[i][0] + points[i + 1][0]) / 2;
    const midY = (points[i][1] + points[i + 1][1]) / 2;
    ctx.quadraticCurveTo(points[i][0], points[i][1], midX, midY);
  }
  const last = points[points.length - 1];
  ctx.lineTo(last[0], last[1]);
}

function smoothstep(value) {
  const x = Math.max(0, Math.min(1, value));
  return x * x * (3 - 2 * x);
}

function partialStrokePoints(points, progress) {
  if (!points.length) return [];
  if (progress >= 1) return points;
  const lengths = [];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i][0] - points[i - 1][0];
    const dy = points[i][1] - points[i - 1][1];
    const len = Math.hypot(dx, dy);
    lengths.push(len);
    total += len;
  }
  const target = total * Math.max(0, Math.min(1, progress));
  const out = [points[0]];
  let walked = 0;
  for (let i = 1; i < points.length; i++) {
    const len = lengths[i - 1];
    if (walked + len <= target) {
      out.push(points[i]);
      walked += len;
      continue;
    }
    const u = len <= 0 ? 0 : (target - walked) / len;
    out.push([
      points[i - 1][0] + (points[i][0] - points[i - 1][0]) * u,
      points[i - 1][1] + (points[i][1] - points[i - 1][1]) * u,
    ]);
    break;
  }
  return out;
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Could not load sketch preview image for quick motion preview.'));
    img.src = src;
  });
}

function renderPassSummary(rows) {
  if (!rows.length) {
    passSummary.className = 'pass-summary empty';
    passSummary.textContent = 'No pass summary yet.';
    return;
  }
  passSummary.className = 'pass-summary';
  passSummary.innerHTML = rows.map(row => `
    <div class="pass-card">
      <strong>${row.name} · ${row.stroke_count} strokes</strong>
      <span>${row.description}<br>${Math.round(row.start_ms / 100) / 10}s – ${Math.round(row.end_ms / 100) / 10}s</span>
    </div>
  `).join('');
}


function renderSemanticSummary(regions, layerPlan) {
  if (!regions.length) {
    semanticSummary.className = 'pass-summary empty';
    semanticSummary.textContent = 'No semantic regions detected.';
    return;
  }
  const focus = new Map((layerPlan || []).map(row => [row.id, row.focus_regions || []]));
  semanticSummary.className = 'pass-summary';
  semanticSummary.innerHTML = regions.slice(0, 12).map(region => {
    const layers = Object.entries(Object.fromEntries([...focus].filter(([, names]) => names.includes(region.name)))).map(([name]) => name);
    return `
      <div class="pass-card">
        <strong>${region.name} · ${(region.confidence * 100).toFixed(0)}% confidence</strong>
        <span>Role: ${region.role} · Priority: ${region.priority}<br>Layers: ${layers.join(', ') || region.preferred_layers?.join(', ') || 'n/a'}</span>
      </div>
    `;
  }).join('');
}
