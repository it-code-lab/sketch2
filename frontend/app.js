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
const sourcePreview = $('sourcePreview');
const sketchPreview = $('sketchPreview');
const passSummary = $('passSummary');
const semanticSummary = $('semanticSummary');
const healthBox = $('healthBox');

const fields = [
  'input_type', 'subject_type', 'style_type', 'ratio', 'sketch_strength', 'stroke_density',
  'human_randomness', 'duration_seconds', 'fps', 'max_strokes', 'paper_texture',
  'construction_pass', 'accent_pass', 'hand_overlay', 'pencil_audio', 'seed', 'trace_mode',
  'stroke_extraction_mode', 'planning_mode', 'art_director_json', 'camera_motion', 'smudge_pass', 'eraser_pass',
  'title_card_text', 'watermark_text', 'hand_mode', 'hand_scale', 'hand_opacity',
  'hand_rotation', 'hand_tip_x', 'hand_tip_y'
];

['sketch_strength','stroke_density','human_randomness','hand_scale','hand_opacity'].forEach(id => {
  const input = $(id);
  const label = $(`${id}_val`);
  if (input && label) input.addEventListener('input', () => label.textContent = input.value);
});

imageInput.addEventListener('change', () => previewFile(imageInput.files?.[0], sourcePreview));

const dropZone = $('dropZone');
['dragenter','dragover'].forEach(evt => dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add('drag'); }));
['dragleave','drop'].forEach(evt => dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.remove('drag'); }));
dropZone.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files?.[0];
  if (!file) return;
  imageInput.files = e.dataTransfer.files;
  previewFile(file, sourcePreview);
});

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
  if (includeHand && $('hand_mode').value === 'uploaded' && handAsset.files?.[0]) {
    fd.append('hand_asset', handAsset.files[0]);
  }
  return fd;
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

analyzeBtn.addEventListener('click', async () => {
  try {
    setBusy(true);
    log('Analyzing stroke plan…');
    const res = await fetch('/api/analyze', { method: 'POST', body: buildFormData(false) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Analyze failed');
    sketchPreview.src = data.sketch_preview;
    sketchPreview.classList.remove('placeholder');
    renderPassSummary(data.plan.pass_summary || []);
    renderSemanticSummary(data.plan.semantic_regions || [], data.plan.layer_plan || []);
    log(`Plan ready: ${data.plan.stroke_count} strokes, subject ${data.plan.subject_type}`, data.plan.warnings || []);
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
    videoOutput.classList.add('hidden');
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
    if (data.status === 'failed') {
      throw new Error(data.error || 'Render failed');
    }
    await new Promise(resolve => setTimeout(resolve, 1100));
  }
}

function handleRenderResult(result) {
  if (!result) return;
  renderPassSummary(result.pass_summary || []);
  renderSemanticSummary(result.semantic_regions || [], result.layer_plan || []);
  const files = result.files || {};
  downloadLinks.innerHTML = '';
  for (const [name, url] of Object.entries(files)) {
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    a.textContent = `Download ${name.toUpperCase()}`;
    downloadLinks.appendChild(a);
  }
  if (files.mp4) {
    videoOutput.src = files.mp4;
    videoOutput.classList.remove('hidden');
  }
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
