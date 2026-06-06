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
const togglePreviewPanelBtn = $('togglePreviewPanelBtn');
const sectionPlanner = $('sectionPlanner');
const applySectionGuideBtn = $('applySectionGuideBtn');
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
let sectionDragState = null;
let selectedSectionRegion = null;
let sectionFocusSelectedOnly = false;
let previewPanelCollapsed = localStorage.getItem('previewPanelCollapsed') === 'true';
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
togglePreviewPanelBtn?.addEventListener('click', () => {
  previewPanelCollapsed = !previewPanelCollapsed;
  localStorage.setItem('previewPanelCollapsed', String(previewPanelCollapsed));
  updatePreviewPanelCollapse();
});
cameraMovePreset.addEventListener('change', () => applyCameraPreset());
artDirectorBtn.addEventListener('click', () => analyzeCurrentImageWithArtDirector());
timelineArtDirectorBtn.addEventListener('click', () => analyzeTimelineWithArtDirector());
applyArtDirectorBtn.addEventListener('click', () => applyLastArtDirectorRecommendations());
sketchierPresetBtn.addEventListener('click', () => applySketchierPreset());
sketchInputPresetBtn.addEventListener('click', () => applySketchInputPreset());
portraitSequenceBtn.addEventListener('click', () => applyPortraitArtistSequence());
applySectionGuideBtn.addEventListener('click', () => {
  if (syncSectionGuideToJson(true)) log('Applied section guide. Generate preview again or render to use this order.');
});
sectionPlanner.addEventListener('click', (event) => {
  const action = event.target?.dataset?.sectionAction;
  if (action === 'portrait-parts') {
    usePortraitParts();
    return;
  }
  if (action === 'separate-boxes') {
    separateSectionBoxes();
    return;
  }
  if (action === 'add-part') {
    addSectionPart();
    return;
  }
  if (action === 'focus-selected') {
    sectionFocusSelectedOnly = !sectionFocusSelectedOnly;
    updateSectionFocusMode();
    return;
  }
  if (action === 'delete-part') {
    deleteSelectedSectionPart();
    return;
  }
  const editButton = event.target.closest?.('.section-edit-button');
  if (editButton) {
    selectSectionRegion(editButton.closest('.section-box')?.dataset?.region, false);
    return;
  }
  const target = event.target.closest?.('[data-region]');
  if (target) selectSectionRegion(target.dataset.region, false);
});
sectionPlanner.addEventListener('input', (event) => {
  if (event.target?.dataset?.inspectorField) {
    updateSectionRowFromInspector(event.target);
    return;
  }
  if (event.target?.dataset?.sectionField) {
    updateSectionOverlayFromRows();
    syncSectionGuideToJson(false);
  }
});
sectionPlanner.addEventListener('change', (event) => {
  if (event.target?.dataset?.inspectorField) {
    updateSectionRowFromInspector(event.target);
    return;
  }
  if (event.target?.dataset?.sectionField) {
    updateSectionOverlayFromRows();
    renderSectionInspector(selectedSectionRegion);
    syncSectionGuideToJson(false);
  }
});
sectionPlanner.addEventListener('pointerdown', (event) => startSectionDrag(event));
window.addEventListener('pointermove', (event) => updateSectionDrag(event));
window.addEventListener('pointerup', () => endSectionDrag());
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
    section_sequence: [
      { region: 'left_eye', order: 1, mode: 'complete', direction: 'center_out', shading_direction: 'left_to_right' },
      { region: 'right_eye', order: 2, mode: 'complete', direction: 'center_out', shading_direction: 'left_to_right' },
      { region: 'left_eyebrow', order: 3, mode: 'complete', direction: 'left_to_right', shading_direction: 'left_to_right' },
      { region: 'right_eyebrow', order: 4, mode: 'complete', direction: 'left_to_right', shading_direction: 'left_to_right' },
      { region: 'mouth', order: 5, mode: 'complete', direction: 'center_out', shading_direction: 'left_to_right' },
      { region: 'nose', order: 6, mode: 'complete', direction: 'top_to_bottom', shading_direction: 'top_to_bottom' },
      { region: 'face_outline', order: 7, mode: 'complete', direction: 'top_to_bottom', shading_direction: 'top_to_bottom' },
      { region: 'jaw_cheek', order: 8, mode: 'complete', direction: 'top_to_bottom', shading_direction: 'top_to_bottom' },
      { region: 'hair_top', order: 9, mode: 'complete', direction: 'top_to_bottom', shading_direction: 'top_to_bottom' },
      { region: 'hair_side', order: 10, mode: 'complete', direction: 'top_to_bottom', shading_direction: 'top_to_bottom' },
      { region: 'neck_clothing', order: 11, mode: 'complete', direction: 'top_to_bottom', shading_direction: 'left_to_right' }
    ],
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

function renderSectionPlanner(regions, subjectType = 'auto') {
  if (!sectionPlanner) return;
  if (!regions.length) {
    sectionPlanner.className = 'section-planner empty';
    sectionPlanner.textContent = 'Generate sketch preview to review and guide drawing sections.';
    return;
  }
  const ordered = [...regions]
    .filter(region => region?.name && region.name !== 'overall_subject' && region.name !== 'background')
    .sort((a, b) => defaultRegionOrder(a.name, subjectType) - defaultRegionOrder(b.name, subjectType) || a.name.localeCompare(b.name))
    .slice(0, 14);
  if (!ordered.length) {
    sectionPlanner.className = 'section-planner empty';
    sectionPlanner.textContent = 'No editable drawing sections were detected.';
    return;
  }
  const settings = lastPreviewPlan?.settings || {};
  const canvasWidth = Number(settings.width || 720);
  const canvasHeight = Number(settings.height || 1280);
  const imageSrc = lastSketchPreviewSrc || sourcePreview?.src || '';
  sectionPlanner.className = 'section-planner';
  sectionPlanner.innerHTML = `
    <div class="section-planner-head">
      <strong>Editable drawing guide</strong>
      <span>Select a part, move its boundary, then edit order, shape, stroke direction, and shading beside the map.</span>
      <div class="section-map-actions">
        <button type="button" data-section-action="portrait-parts">Use portrait parts</button>
        <button type="button" data-section-action="separate-boxes">Separate boxes</button>
        <button type="button" data-section-action="add-part">Add part</button>
        <button type="button" data-section-action="focus-selected" aria-pressed="${sectionFocusSelectedOnly ? 'true' : 'false'}">${sectionFocusSelectedOnly ? 'Show all parts' : 'Focus selected part'}</button>
      </div>
    </div>
    <div class="section-workspace">
      <div class="section-map">
        ${imageSrc ? `<img src="${imageSrc}" alt="Section map" />` : ''}
        <svg viewBox="0 0 ${canvasWidth} ${canvasHeight}" preserveAspectRatio="xMidYMid meet" aria-label="Editable section overlay">
          ${ordered.map((region, idx) => sectionOverlayHtml(region, idx + 1)).join('')}
        </svg>
      </div>
      <div class="section-inspector empty">Select a drawing part to edit its properties.</div>
    </div>
    <details class="section-grid-wrap">
      <summary>Advanced table</summary>
      <div class="section-grid">
        ${sectionTableHeaderHtml()}
        ${ordered.map((region, idx) => sectionRowHtml(region, idx + 1, subjectType, canvasWidth, canvasHeight)).join('')}
      </div>
    </details>
  `;
  selectSectionRegion(ordered[0]?.name, false);
  updateSectionFocusMode();
}

function updatePreviewPanelCollapse() {
  document.body.classList.toggle('preview-collapsed', previewPanelCollapsed);
  if (!togglePreviewPanelBtn) return;
  togglePreviewPanelBtn.textContent = previewPanelCollapsed ? 'Show preview' : 'Collapse preview';
  togglePreviewPanelBtn.setAttribute('aria-expanded', previewPanelCollapsed ? 'false' : 'true');
}

function sectionOverlayHtml(region, order) {
  const [x1, y1, x2, y2] = region.bbox || [0, 0, 1, 1];
  const name = escapeHtml(region.name);
  const label = escapeHtml(region.name.replaceAll('_', ' '));
  const w = Math.max(1, x2 - x1);
  const h = Math.max(1, y2 - y1);
  return `
    <g class="section-box" data-region="${name}">
      <rect class="section-box-body" x="${x1}" y="${y1}" width="${w}" height="${h}"></rect>
      <polygon class="section-polygon-body hidden"></polygon>
      <text x="${x1 + 8}" y="${y1 + 22}" data-label="${label}">${order}. ${label}</text>
      <g class="section-edit-button" transform="translate(${Math.max(0, x1 + w - 62)}, ${Math.max(0, y1 - 32)})">
        <rect width="58" height="24" rx="5"></rect>
        <text x="29" y="17">Edit</text>
      </g>
      <rect class="resize-handle nw" data-handle="nw" x="${x1 - 7}" y="${y1 - 7}" width="14" height="14"></rect>
      <rect class="resize-handle ne" data-handle="ne" x="${x1 + w - 7}" y="${y1 - 7}" width="14" height="14"></rect>
      <rect class="resize-handle sw" data-handle="sw" x="${x1 - 7}" y="${y1 + h - 7}" width="14" height="14"></rect>
      <rect class="resize-handle se" data-handle="se" x="${x1 + w - 7}" y="${y1 + h - 7}" width="14" height="14"></rect>
    </g>
  `;
}

function sectionTableHeaderHtml() {
  return `
    <div class="section-row section-row-header" aria-hidden="true">
      <span>Order</span>
      <span>Part</span>
      <span>Completion</span>
      <span>Shape</span>
      <span class="section-area-header">Area: X / Y / W / H / Rot</span>
      <span>Stroke direction</span>
      <span>Shading direction</span>
    </div>
  `;
}

function sectionRowHtml(region, order, subjectType, canvasWidth, canvasHeight) {
  const name = escapeHtml(region.name);
  const label = escapeHtml(region.name.replaceAll('_', ' '));
  const direction = defaultRegionDirection(region.name, subjectType);
  const shade = defaultShadingDirection(region.name, subjectType);
  const area = bboxToPercent(region.bbox || [0, 0, canvasWidth, canvasHeight], canvasWidth, canvasHeight);
  return `
    <div class="section-row" data-region="${name}">
      <input type="number" min="1" max="99" value="${order}" data-section-field="order" aria-label="Section order for ${label}" />
      <div class="section-name">
        <strong>${label}</strong>
        <span>${escapeHtml(region.role || 'section')} · ${(Number(region.confidence || 0) * 100).toFixed(0)}%</span>
      </div>
      <select data-section-field="mode" aria-label="Completion mode for ${label}">
        <option value="complete" selected>Complete before next</option>
        <option value="lines_first">Lines first, shade later</option>
        <option value="shading_only">Shading pass only</option>
        <option value="skip">Skip</option>
      </select>
      <select data-section-field="shape" aria-label="Part shape for ${label}">
        <option value="rectangle" selected>Rectangle</option>
        <option value="freeform">Freeform mask</option>
      </select>
      <div class="section-area" aria-label="Area for ${label}">
        <input type="number" min="0" max="100" step="0.5" value="${area.x}" data-section-field="x" title="X %" />
        <input type="number" min="0" max="100" step="0.5" value="${area.y}" data-section-field="y" title="Y %" />
        <input type="number" min="1" max="100" step="0.5" value="${area.w}" data-section-field="w" title="Width %" />
        <input type="number" min="1" max="100" step="0.5" value="${area.h}" data-section-field="h" title="Height %" />
        <input type="number" min="-180" max="180" step="1" value="0" data-section-field="rotation" title="Rotation degrees" />
      </div>
      <select data-section-field="direction" aria-label="Stroke direction for ${label}">
        ${directionOptions(direction)}
      </select>
      <select data-section-field="shading_direction" aria-label="Shading direction for ${label}">
        ${directionOptions(shade)}
      </select>
    </div>
  `;
}

function bboxToPercent(bbox, canvasWidth, canvasHeight) {
  const [x1, y1, x2, y2] = bbox.map(Number);
  return {
    x: roundOne(x1 / canvasWidth * 100),
    y: roundOne(y1 / canvasHeight * 100),
    w: roundOne(Math.max(1, x2 - x1) / canvasWidth * 100),
    h: roundOne(Math.max(1, y2 - y1) / canvasHeight * 100)
  };
}

function roundOne(value) {
  return Math.round(value * 10) / 10;
}

function selectSectionRegion(region, scrollRow = false) {
  if (!region || !sectionPlanner) return;
  selectedSectionRegion = region;
  sectionPlanner.querySelectorAll('[data-region]').forEach(el => {
    el.classList.toggle('selected', el.dataset.region === region);
  });
  const row = sectionPlanner.querySelector(`.section-row[data-region="${CSS.escape(region)}"]`);
  if (scrollRow) row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  renderSectionInspector(region);
  updateSectionFocusMode();
}

function updateSectionFocusMode() {
  if (!sectionPlanner) return;
  sectionPlanner.classList.toggle('focus-selected', sectionFocusSelectedOnly);
  const button = sectionPlanner.querySelector('[data-section-action="focus-selected"]');
  if (button) {
    button.textContent = sectionFocusSelectedOnly ? 'Show all parts' : 'Focus selected part';
    button.setAttribute('aria-pressed', sectionFocusSelectedOnly ? 'true' : 'false');
    button.classList.toggle('active-toggle', sectionFocusSelectedOnly);
  }
}

function renderSectionInspector(region) {
  const inspector = sectionPlanner?.querySelector('.section-inspector');
  if (!inspector) return;
  const row = region ? sectionPlanner.querySelector(`.section-row[data-region="${CSS.escape(region)}"]`) : null;
  if (!row) {
    inspector.className = 'section-inspector empty';
    inspector.textContent = 'Select a drawing part to edit its properties.';
    return;
  }
  inspector.className = 'section-inspector';
  inspector.dataset.inspectorRegion = region;
  const label = region.replaceAll('_', ' ');
  const value = name => row.querySelector(`[data-section-field="${name}"]`)?.value || '';
  const area = readSectionArea(row);
  inspector.innerHTML = `
    <div class="section-inspector-title">
      <div>
        <span>Selected part</span>
        <strong>${escapeHtml(label)}</strong>
      </div>
      <button type="button" data-section-action="delete-part">Delete</button>
    </div>
    <div class="section-inspector-grid">
      <label>Order <input type="number" min="1" max="99" value="${escapeHtml(value('order'))}" data-inspector-field="order" /></label>
      <label>Mode <select data-inspector-field="mode">${modeOptions(value('mode'))}</select></label>
      <label>Shape <select data-inspector-field="shape">${shapeOptions(value('shape'))}</select></label>
      <label>X % <input type="number" min="0" max="100" step="0.5" value="${area.x}" data-inspector-field="x" /></label>
      <label>Y % <input type="number" min="0" max="100" step="0.5" value="${area.y}" data-inspector-field="y" /></label>
      <label>W % <input type="number" min="1" max="100" step="0.5" value="${area.w}" data-inspector-field="w" /></label>
      <label>H % <input type="number" min="1" max="100" step="0.5" value="${area.h}" data-inspector-field="h" /></label>
      <label>Rotate <input type="number" min="-180" max="180" step="1" value="${escapeHtml(value('rotation'))}" data-inspector-field="rotation" /></label>
      <label>Stroke <select data-inspector-field="direction">${directionOptions(value('direction'))}</select></label>
      <label>Shading <select data-inspector-field="shading_direction">${directionOptions(value('shading_direction'))}</select></label>
    </div>
  `;
}

function updateSectionRowFromInspector(control) {
  const inspector = control.closest('.section-inspector');
  const region = inspector?.dataset?.inspectorRegion;
  const field = control.dataset.inspectorField;
  const row = region ? sectionPlanner.querySelector(`.section-row[data-region="${CSS.escape(region)}"]`) : null;
  const rowControl = row?.querySelector(`[data-section-field="${field}"]`);
  if (!rowControl) return;
  rowControl.value = control.value;
  updateSectionOverlayFromRows();
  syncSectionGuideToJson(false);
}

function updateSectionOverlayFromRows() {
  const settings = lastPreviewPlan?.settings || {};
  const canvasWidth = Number(settings.width || 720);
  const canvasHeight = Number(settings.height || 1280);
  const rows = Array.from(sectionPlanner?.querySelectorAll('.section-row') || []);
  for (const row of rows) {
    const region = row.dataset.region;
    const group = sectionPlanner.querySelector(`.section-box[data-region="${CSS.escape(region)}"]`);
    if (!group) continue;
    const area = readSectionArea(row);
    const shape = row.querySelector('[data-section-field="shape"]')?.value || 'rectangle';
    const rotation = Number(row.querySelector('[data-section-field="rotation"]')?.value || 0);
    const x = area.x / 100 * canvasWidth;
    const y = area.y / 100 * canvasHeight;
    const w = area.w / 100 * canvasWidth;
    const h = area.h / 100 * canvasHeight;
    const rect = group.querySelector('.section-box-body');
    const polygon = group.querySelector('.section-polygon-body');
    const text = group.querySelector('text');
    const order = row.querySelector('[data-section-field="order"]')?.value || '';
    const points = sectionPolygonPoints(area, shape, rotation);
    const pixelPoints = points.map(([px, py]) => [px / 100 * canvasWidth, py / 100 * canvasHeight]);
    if (shape === 'rectangle' && Math.abs(rotation) < 0.1) {
      rect?.classList.remove('hidden');
      polygon?.classList.add('hidden');
      rect?.setAttribute('x', x);
      rect?.setAttribute('y', y);
      rect?.setAttribute('width', Math.max(1, w));
      rect?.setAttribute('height', Math.max(1, h));
      rect?.removeAttribute('transform');
    } else {
      rect?.classList.add('hidden');
      polygon?.classList.remove('hidden');
      polygon?.setAttribute('points', pixelPoints.map(([px, py]) => `${roundOne(px)},${roundOne(py)}`).join(' '));
    }
    text?.setAttribute('x', x + 8);
    text?.setAttribute('y', y + 22);
    if (text) text.textContent = `${order}. ${text.dataset.label || region.replaceAll('_', ' ')}`;
    const editButton = group.querySelector('.section-edit-button');
    if (editButton) {
      const bx = Math.max(0, Math.min(canvasWidth - 62, x + Math.max(1, w) - 62));
      const by = Math.max(0, y - 32);
      editButton.setAttribute('transform', `translate(${roundOne(bx)}, ${roundOne(by)})`);
    }
    positionSectionHandles(group, x, y, Math.max(1, w), Math.max(1, h));
  }
}

function positionSectionHandles(group, x, y, w, h) {
  const positions = {
    nw: [x - 7, y - 7],
    ne: [x + w - 7, y - 7],
    sw: [x - 7, y + h - 7],
    se: [x + w - 7, y + h - 7]
  };
  for (const [handle, [hx, hy]] of Object.entries(positions)) {
    const node = group.querySelector(`.resize-handle.${handle}`);
    node?.setAttribute('x', hx);
    node?.setAttribute('y', hy);
  }
}

function readSectionArea(row) {
  const field = name => Number(row.querySelector(`[data-section-field="${name}"]`)?.value || 0);
  const x = Math.max(0, Math.min(99, field('x')));
  const y = Math.max(0, Math.min(99, field('y')));
  const w = Math.max(1, Math.min(100 - x, field('w') || 1));
  const h = Math.max(1, Math.min(100 - y, field('h') || 1));
  return { x, y, w, h };
}

function setSectionArea(row, area) {
  const x = Math.max(0, Math.min(99, area.x));
  const y = Math.max(0, Math.min(99, area.y));
  const w = Math.max(1, Math.min(100 - x, area.w));
  const h = Math.max(1, Math.min(100 - y, area.h));
  const values = { x, y, w, h };
  for (const [name, value] of Object.entries(values)) {
    const input = row.querySelector(`[data-section-field="${name}"]`);
    if (input) input.value = roundOne(value);
  }
}

function sectionPolygonPoints(area, shape, rotation = 0) {
  const cx = area.x + area.w / 2;
  const cy = area.y + area.h / 2;
  const base = shape === 'freeform'
    ? [
        [area.x + area.w * 0.10, area.y + area.h * 0.34],
        [area.x + area.w * 0.24, area.y + area.h * 0.08],
        [area.x + area.w * 0.58, area.y + area.h * 0.02],
        [area.x + area.w * 0.90, area.y + area.h * 0.20],
        [area.x + area.w * 0.96, area.y + area.h * 0.62],
        [area.x + area.w * 0.72, area.y + area.h * 0.95],
        [area.x + area.w * 0.30, area.y + area.h * 0.92],
        [area.x + area.w * 0.04, area.y + area.h * 0.68]
      ]
    : [
        [area.x, area.y],
        [area.x + area.w, area.y],
        [area.x + area.w, area.y + area.h],
        [area.x, area.y + area.h]
      ];
  return base.map(([x, y]) => rotatePointPct(x, y, cx, cy, rotation));
}

function rotatePointPct(x, y, cx, cy, degrees) {
  const radians = degrees * Math.PI / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  const dx = x - cx;
  const dy = y - cy;
  return [roundOne(cx + dx * cos - dy * sin), roundOne(cy + dx * sin + dy * cos)];
}

function startSectionDrag(event) {
  if (event.target.closest?.('.section-edit-button')) return;
  const group = event.target.closest?.('.section-box');
  if (!group || !sectionPlanner.contains(group)) return;
  const svg = group.ownerSVGElement;
  const row = sectionPlanner.querySelector(`.section-row[data-region="${CSS.escape(group.dataset.region)}"]`);
  if (!svg || !row) return;
  event.preventDefault();
  selectSectionRegion(group.dataset.region, false);
  const start = sectionSvgPoint(svg, event);
  sectionDragState = {
    svg,
    row,
    region: group.dataset.region,
    handle: event.target.dataset.handle || 'move',
    start,
    area: readSectionArea(row)
  };
  document.body.classList.add('section-dragging');
  event.target.setPointerCapture?.(event.pointerId);
}

function updateSectionDrag(event) {
  if (!sectionDragState) return;
  event.preventDefault();
  const { svg, row, handle, start, area } = sectionDragState;
  const settings = lastPreviewPlan?.settings || {};
  const canvasWidth = Number(settings.width || 720);
  const canvasHeight = Number(settings.height || 1280);
  const point = sectionSvgPoint(svg, event);
  const dx = (point.x - start.x) / canvasWidth * 100;
  const dy = (point.y - start.y) / canvasHeight * 100;
  const next = { ...area };
  if (handle === 'move') {
    next.x = area.x + dx;
    next.y = area.y + dy;
  } else {
    if (handle.includes('w')) {
      next.x = area.x + dx;
      next.w = area.w - dx;
    }
    if (handle.includes('e')) next.w = area.w + dx;
    if (handle.includes('n')) {
      next.y = area.y + dy;
      next.h = area.h - dy;
    }
    if (handle.includes('s')) next.h = area.h + dy;
  }
  setSectionArea(row, next);
  updateSectionOverlayFromRows();
}

function endSectionDrag() {
  if (sectionDragState) {
    syncSectionGuideToJson(false);
    renderSectionInspector(sectionDragState.region);
  }
  sectionDragState = null;
  document.body.classList.remove('section-dragging');
}

function sectionSvgPoint(svg, event) {
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  const mapped = point.matrixTransform(svg.getScreenCTM().inverse());
  return { x: mapped.x, y: mapped.y };
}

function usePortraitParts() {
  const settings = lastPreviewPlan?.settings || {};
  const canvasWidth = Number(settings.width || 720);
  const canvasHeight = Number(settings.height || 1280);
  const parts = [
    ['left_eye', 'focal', 1, [30, 35, 18, 10], 'center_out'],
    ['right_eye', 'focal', 2, [54, 35, 18, 10], 'center_out'],
    ['left_eyebrow', 'focal', 3, [28, 29, 20, 8], 'left_to_right'],
    ['right_eyebrow', 'focal', 4, [53, 29, 20, 8], 'left_to_right'],
    ['mouth', 'focal', 5, [38, 56, 25, 11], 'center_out'],
    ['nose', 'focal', 6, [43, 41, 14, 18], 'top_to_bottom'],
    ['face_outline', 'form', 7, [25, 22, 50, 48], 'top_to_bottom'],
    ['hair_top', 'support', 8, [18, 8, 64, 23], 'top_to_bottom'],
    ['hair_side', 'support', 9, [15, 30, 70, 43], 'top_to_bottom'],
    ['neck_clothing', 'support', 10, [30, 70, 40, 22], 'top_to_bottom']
  ];
  const regions = parts.map(([name, role, order, pct]) => {
    const [x, y, w, h] = pct;
    return {
      name,
      role,
      confidence: 0.96,
      bbox: [x / 100 * canvasWidth, y / 100 * canvasHeight, (x + w) / 100 * canvasWidth, (y + h) / 100 * canvasHeight]
    };
  });
  $('subject_type').value = 'portrait';
  renderSectionPlanner(regions, 'portrait');
  sectionPlanner.querySelectorAll('.section-row').forEach((row, idx) => {
    row.querySelector('[data-section-field="order"]').value = parts[idx][2];
    row.querySelector('[data-section-field="direction"]').value = parts[idx][4];
    row.querySelector('[data-section-field="shading_direction"]').value = defaultShadingDirection(row.dataset.region, 'portrait');
    if (row.dataset.region.includes('hair')) row.querySelector('[data-section-field="shape"]').value = 'freeform';
  });
  updateSectionOverlayFromRows();
  syncSectionGuideToJson(false);
  log('Created editable portrait parts. Drag or resize boxes, then apply the section guide.');
}

function separateSectionBoxes() {
  const rows = Array.from(sectionPlanner?.querySelectorAll('.section-row') || []);
  if (!rows.length) return;
  rows.sort((a, b) => Number(a.querySelector('[data-section-field="order"]').value) - Number(b.querySelector('[data-section-field="order"]').value));
  rows.forEach((row, idx) => {
    const area = readSectionArea(row);
    const col = idx % 2;
    const band = Math.floor(idx / 2);
    const next = {
      x: col ? 52 : 8,
      y: Math.min(88, 6 + band * 16),
      w: Math.min(40, Math.max(18, area.w)),
      h: Math.min(14, Math.max(8, area.h))
    };
    setSectionArea(row, next);
  });
  updateSectionOverlayFromRows();
  syncSectionGuideToJson(false);
  log('Separated section boxes into a clean editable layout. Adjust each part over the image as needed.');
}

function addSectionPart() {
  const rows = Array.from(sectionPlanner?.querySelectorAll('.section-row') || []);
  if (!rows.length) return;
  const settings = lastPreviewPlan?.settings || {};
  const canvasWidth = Number(settings.width || 720);
  const canvasHeight = Number(settings.height || 1280);
  const nextOrder = Math.max(0, ...rows.map(row => Number(row.querySelector('[data-section-field="order"]')?.value || 0))) + 1;
  const proposed = `part_${nextOrder}`;
  const typed = window.prompt('Name this drawing part', proposed);
  const regionName = uniqueSectionRegionName(normalizeSectionRegionName(typed || proposed));
  if (!regionName) return;
  const region = {
    name: regionName,
    role: 'custom',
    confidence: 1,
    bbox: [0.35 * canvasWidth, 0.35 * canvasHeight, 0.65 * canvasWidth, 0.55 * canvasHeight]
  };
  sectionPlanner.querySelector('.section-map svg')?.insertAdjacentHTML('beforeend', sectionOverlayHtml(region, nextOrder));
  sectionPlanner.querySelector('.section-grid')?.insertAdjacentHTML('beforeend', sectionRowHtml(region, nextOrder, $('subject_type').value || 'auto', canvasWidth, canvasHeight));
  updateSectionOverlayFromRows();
  selectSectionRegion(regionName, false);
  syncSectionGuideToJson(false);
  log(`Added drawing part "${regionName.replaceAll('_', ' ')}". Move its boundary over the image and edit its properties beside the map.`);
}

function deleteSelectedSectionPart() {
  const region = selectedSectionRegion;
  if (!region) return;
  const rows = Array.from(sectionPlanner?.querySelectorAll('.section-row') || []);
  if (rows.length <= 1) {
    log('Keep at least one drawing part in the guide.');
    return;
  }
  sectionPlanner.querySelector(`.section-box[data-region="${CSS.escape(region)}"]`)?.remove();
  sectionPlanner.querySelector(`.section-row[data-region="${CSS.escape(region)}"]`)?.remove();
  const next = sectionPlanner.querySelector('.section-row')?.dataset?.region || null;
  selectedSectionRegion = null;
  updateSectionOverlayFromRows();
  selectSectionRegion(next, false);
  syncSectionGuideToJson(false);
}

function normalizeSectionRegionName(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48) || 'part';
}

function uniqueSectionRegionName(base) {
  const existing = new Set(Array.from(sectionPlanner?.querySelectorAll('.section-row') || []).map(row => row.dataset.region));
  let name = base;
  let idx = 2;
  while (existing.has(name)) {
    name = `${base}_${idx}`;
    idx += 1;
  }
  return name;
}

function modeOptions(selected = 'complete') {
  const rows = [
    ['complete', 'Complete before next'],
    ['lines_first', 'Lines first, shade later'],
    ['shading_only', 'Shading pass only'],
    ['skip', 'Skip']
  ];
  return rows.map(([value, label]) => `<option value="${value}"${value === selected ? ' selected' : ''}>${label}</option>`).join('');
}

function shapeOptions(selected = 'rectangle') {
  const rows = [
    ['rectangle', 'Rectangle'],
    ['freeform', 'Freeform mask']
  ];
  return rows.map(([value, label]) => `<option value="${value}"${value === selected ? ' selected' : ''}>${label}</option>`).join('');
}

function directionOptions(selected) {
  const rows = [
    ['auto', 'Auto direction'],
    ['left_to_right', 'Left to right'],
    ['right_to_left', 'Right to left'],
    ['top_to_bottom', 'Top to bottom'],
    ['bottom_to_top', 'Bottom to top'],
    ['center_out', 'Center outward'],
    ['outside_in', 'Outside inward']
  ];
  return rows.map(([value, label]) => `<option value="${value}"${value === selected ? ' selected' : ''}>${label}</option>`).join('');
}

function defaultRegionOrder(region, subjectType) {
  if (subjectType === 'portrait') {
    const order = {
      left_eye: 1, right_eye: 2, left_eyebrow: 3, right_eyebrow: 4,
      mouth: 5, nose: 6, face_outline: 7, jaw_cheek: 8,
      hair_top: 9, hair_side: 10, neck_clothing: 11
    };
    return order[region] || 50;
  }
  if (subjectType === 'architecture') {
    const order = { roof: 1, central_structure: 2, entrance: 3, left_pillars: 4, right_pillars: 5, carvings: 6, ground: 7 };
    return order[region] || 50;
  }
  return 50;
}

function defaultRegionDirection(region, subjectType) {
  if (subjectType === 'portrait') {
    if (region.includes('eye') || region === 'mouth') return 'center_out';
    if (region.includes('hair') || region.includes('face') || region.includes('jaw') || region === 'nose') return 'top_to_bottom';
  }
  if (subjectType === 'architecture' && (region.includes('roof') || region.includes('ground'))) return 'left_to_right';
  return 'auto';
}

function defaultShadingDirection(region, subjectType) {
  if (subjectType === 'portrait' && region.includes('hair')) return 'top_to_bottom';
  if (subjectType === 'portrait') return 'left_to_right';
  return defaultRegionDirection(region, subjectType);
}

function syncSectionGuideToJson(showErrors = false) {
  const rows = Array.from(sectionPlanner?.querySelectorAll('.section-row') || []);
  if (!rows.length) return false;
  let plan = {};
  try {
    const raw = $('art_director_json').value.trim();
    plan = raw ? JSON.parse(raw) : {};
  } catch (err) {
    if (showErrors) log('Art Director JSON is not valid. Fix it or clear it before applying the section guide.');
    return false;
  }
  const subject = lastPreviewPlan?.subject_type || $('subject_type').value || 'auto';
  plan.subject_type = subject === 'auto' ? plan.subject_type || 'portrait' : subject;
  plan.section_sequence = rows.map(row => {
    const field = name => row.querySelector(`[data-section-field="${name}"]`)?.value || '';
    const area = readSectionArea(row);
    const shape = field('shape') || 'rectangle';
    const rotation = Number(field('rotation')) || 0;
    const settings = lastPreviewPlan?.settings || {};
    const canvasWidth = Number(settings.width || 720);
    const canvasHeight = Number(settings.height || 1280);
    const polygonPct = sectionPolygonPoints(area, shape, rotation);
    const bbox = [
      area.x / 100 * canvasWidth,
      area.y / 100 * canvasHeight,
      (area.x + area.w) / 100 * canvasWidth,
      (area.y + area.h) / 100 * canvasHeight
    ].map(value => Math.round(value * 10) / 10);
    const section = {
      region: row.dataset.region,
      order: Number(field('order')) || 99,
      mode: field('mode') || 'complete',
      shape,
      rotation,
      direction: field('direction') || 'auto',
      shading_direction: field('shading_direction') || 'auto',
      bbox_pct: [area.x, area.y, area.w, area.h],
      bbox
    };
    if (shape !== 'rectangle' || Math.abs(rotation) > 0.1) section.polygon_pct = polygonPct;
    return section;
  }).sort((a, b) => a.order - b.order);
  plan.region_priority = Object.fromEntries(plan.section_sequence.map((row, idx) => [row.region, idx * 10 - 100]));
  plan.artist_sequence = plan.artist_sequence || true;
  $('planning_mode').value = 'art_director_json';
  $('art_director_json').value = JSON.stringify(plan, null, 2);
  return true;
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
  renderSectionPlanner([], 'auto');
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
  syncSectionGuideToJson(false);
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
updatePreviewPanelCollapse();
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
    renderSectionPlanner(data.plan.semantic_regions || [], data.plan.subject_type || $('subject_type').value);
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
    syncSectionGuideToJson(false);
    const targetImage = await loadImage(lastSketchPreviewSrc);
    playQuickMotionPreview(buildSectionGuidedPreviewPlan(lastPreviewPlan), targetImage);
  } catch (err) {
    log(err.message || String(err));
  }
}

function buildSectionGuidedPreviewPlan(plan) {
  if (!plan?.strokes?.length) return plan;
  let director = {};
  try {
    const raw = $('art_director_json')?.value?.trim() || '';
    director = raw ? JSON.parse(raw) : {};
  } catch {
    return plan;
  }
  const sequence = Array.isArray(director.section_sequence)
    ? director.section_sequence
        .filter(row => row?.region)
        .map((row, idx) => ({ ...row, order: Number(row.order || idx + 1), idx }))
        .sort((a, b) => a.order - b.order || a.idx - b.idx)
    : [];
  if (!sequence.length) return plan;

  const settings = plan.settings || {};
  const width = Number(settings.width || 720);
  const height = Number(settings.height || 1280);
  const rules = sequence.map(section => ({
    ...section,
    polygon: sectionPreviewPolygon(section)
  })).filter(section => section.polygon.length >= 3);
  const ruleByRegion = new Map(sequence.map((section, idx) => [section.region, { ...section, sortIndex: idx }]));
  const fallbackOrder = sequence.length + 20;
  const strokes = plan.strokes.map(stroke => ({
    ...stroke,
    points: Array.isArray(stroke.points) ? stroke.points.map(point => [...point]) : []
  }));

  for (const stroke of strokes) {
    const owner = rules.find(rule => strokeTouchesPreviewPolygon(stroke, rule.polygon, width, height));
    if (owner) stroke.region = owner.region;
  }

  const visible = strokes.filter(stroke => ruleByRegion.get(stroke.region)?.mode !== 'skip' && Number(stroke.opacity ?? 1) > 0);
  visible.sort((a, b) => {
    const ar = ruleByRegion.get(a.region);
    const br = ruleByRegion.get(b.region);
    const ao = ar ? ar.order : fallbackOrder;
    const bo = br ? br.order : fallbackOrder;
    const ap = sectionPreviewLayerPhase(a.layer, ar?.mode);
    const bp = sectionPreviewLayerPhase(b.layer, br?.mode);
    return ao - bo || ap - bp || Number(a.bbox?.[1] || 0) - Number(b.bbox?.[1] || 0) || Number(a.bbox?.[0] || 0) - Number(b.bbox?.[0] || 0);
  });

  const durationMs = Math.max(
    Number(settings.duration_seconds || 0) * 1000,
    ...visible.map(stroke => Number(stroke.end_ms || 0)),
    1000
  );
  const weights = visible.map(stroke => Math.max(20, Number(stroke.duration_ms || 0) || Math.max(20, Number(stroke.length || 24) * 2.2)));
  const totalWeight = weights.reduce((sum, value) => sum + value, 0) || 1;
  let cursor = 0;
  visible.forEach((stroke, idx) => {
    const dur = Math.max(16, weights[idx] / totalWeight * durationMs);
    stroke.start_ms = Math.round(cursor);
    cursor += dur;
    stroke.duration_ms = Math.round(dur);
    stroke.end_ms = Math.round(cursor);
  });

  return { ...plan, strokes: visible };
}

function strokeCenterPct(stroke, width, height) {
  if (Array.isArray(stroke.bbox) && stroke.bbox.length >= 4) {
    return [
      ((Number(stroke.bbox[0]) + Number(stroke.bbox[2])) / 2) / width * 100,
      ((Number(stroke.bbox[1]) + Number(stroke.bbox[3])) / 2) / height * 100
    ];
  }
  const points = Array.isArray(stroke.points) ? stroke.points : [];
  if (!points.length) return [50, 50];
  const sum = points.reduce((acc, point) => [acc[0] + Number(point[0] || 0), acc[1] + Number(point[1] || 0)], [0, 0]);
  return [sum[0] / points.length / width * 100, sum[1] / points.length / height * 100];
}

function sectionPreviewPolygon(section) {
  if (Array.isArray(section.polygon_pct) && section.polygon_pct.length >= 3) {
    return section.polygon_pct.map(point => [Number(point[0]), Number(point[1])]);
  }
  if (Array.isArray(section.bbox_pct) && section.bbox_pct.length >= 4) {
    const [x, y, w, h] = section.bbox_pct.map(Number);
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
  }
  return [];
}

function pointInPreviewPolygon(point, polygon) {
  const [x, y] = point;
  let inside = false;
  let j = polygon.length - 1;
  for (let i = 0; i < polygon.length; i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    if (((yi > y) !== (yj > y)) && x < (xj - xi) * (y - yi) / Math.max(1e-6, yj - yi) + xi) inside = !inside;
    j = i;
  }
  return inside;
}

function strokeTouchesPreviewPolygon(stroke, polygon, width, height) {
  const samples = [strokeCenterPct(stroke, width, height)];
  const points = Array.isArray(stroke.points) ? stroke.points : [];
  if (points.length) {
    const step = Math.max(1, Math.floor(points.length / 8));
    for (let i = 0; i < points.length; i += step) {
      samples.push([Number(points[i][0] || 0) / width * 100, Number(points[i][1] || 0) / height * 100]);
    }
    const last = points[points.length - 1];
    samples.push([Number(last[0] || 0) / width * 100, Number(last[1] || 0) / height * 100]);
  }
  return samples.some(point => pointInPreviewPolygon(point, polygon));
}

function sectionPreviewLayerPhase(layer, mode = 'complete') {
  const phases = { layout: -0.2, key: 0, contour: 0.1, secondary: 0.24, texture: 0.42, shading: 0.58, accent: 0.78 };
  if (mode === 'lines_first' && ['texture', 'shading', 'smudge'].includes(layer)) return 1.4;
  if (mode === 'shading_only' && !['texture', 'shading', 'smudge'].includes(layer)) return 1.2;
  return phases[layer] ?? 0.5;
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
