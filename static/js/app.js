// App controller — wires UI, API, and visualizer
import { post, get, del, getBlob, watchJob } from './api.js';
import { initVisualizer, setEnergy, pulse } from './visualizer.js';

let currentJobId = null;
let currentJob = null;

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
  initVisualizer();
  initNav();
  loadJobs();
});

// ── Upload audio file ──
window.uploadAudio = async function() {
  const fileInput = document.getElementById('audio-file');
  const file = fileInput.files?.[0];
  if (!file) return toast('Select an audio file');

  const btn = document.getElementById('upload-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Uploading...';

  const logBox = document.getElementById('activity-log');
  const progressWrap = document.getElementById('progress-wrap');
  logBox.innerHTML = '';
  progressWrap.style.display = 'block';
  addLog('Uploading audio file...');

  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', document.getElementById('model-select').value);
    formData.append('language', document.getElementById('lang-select').value || '');
    formData.append('title', document.getElementById('upload-title').value || file.name);

    const res = await fetch(`${window.location.origin}/api/transcribe-audio`, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');

    currentJobId = data.job_id;
    addLog(`Job queued: ${data.job_id.slice(0, 8)}...`);
    pulse();

    watchJob(data.job_id, (update) => handleJobUpdate(update, btn, logBox));
  } catch (e) {
    addLog(`Error: ${e.message}`, 'error');
    btn.disabled = false;
    btn.textContent = '⬆ Upload & Extract';
    toast(e.message);
  }
};

// ── Navigation ──
function initNav() {
  document.querySelectorAll('nav button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.panel).classList.add('active');
      if (btn.dataset.panel === 'p-jobs') loadJobs();
      if (btn.dataset.panel === 'p-stats') loadStats();
    });
  });
}

function switchTo(panel) {
  document.querySelectorAll('nav button').forEach(b => {
    b.classList.toggle('active', b.dataset.panel === panel);
  });
  document.querySelectorAll('.panel').forEach(p => {
    p.classList.toggle('active', p.id === panel);
  });
}

// ── Toast ──
window.toast = function(msg) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
};

// ── Submit ──
window.submitJob = async function() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) return toast('Paste a YouTube URL');

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Submitting...';

  const logBox = document.getElementById('activity-log');
  const progressWrap = document.getElementById('progress-wrap');
  logBox.innerHTML = '';
  progressWrap.style.display = 'block';
  addLog('Submitting job...');

  try {
    const data = await post('/api/transcribe', {
      url,
      model: document.getElementById('model-select').value,
      language: document.getElementById('lang-select').value || null,
    });

    currentJobId = data.job_id;
    addLog(`Job queued: ${data.job_id.slice(0, 8)}...`);
    pulse();

    // Watch with polling
    watchJob(data.job_id, (update) => handleJobUpdate(update, btn, logBox));

  } catch (e) {
    addLog(`Error: ${e.message}`, 'error');
    btn.disabled = false;
    btn.textContent = '🎤 Extract';
    toast(e.message);
  }
};

function handleJobUpdate(update, btn, logBox) {
  const stages = {
    queued: 'Waiting in queue...',
    processing: 'Processing...',
    downloading: 'Downloading audio...',
    detecting_language: 'Detecting language...',
    transcribing: 'Extracting lyrics...',
    done: 'Lyrics extracted!',
    error: 'Failed',
  };

  document.getElementById('progress-bar').style.width = update.progress + '%';
  document.getElementById('progress-text').textContent = stages[update.status] || update.status;
  setEnergy(update.progress / 100);

  if (update.newEntries && update.newEntries.length > 0) {
    update.newEntries.forEach(msg => {
      const cls = update.status === 'error' ? 'error' : update.status === 'done' ? 'done' : 'active';
      addLog(msg, cls);
    });
  }

  if (update.status === 'done') {
    pulse();
    btn.disabled = false;
    btn.textContent = '🎤 Extract';
    document.getElementById('upload-btn').disabled = false;
    document.getElementById('upload-btn').textContent = '⬆ Upload & Extract';
    toast('Lyrics ready!');
    setTimeout(() => {
      loadJob(currentJobId);
      switchTo('p-viewer');
    }, 800);
  }
  if (update.status === 'error') {
    btn.disabled = false;
    btn.textContent = '🎤 Extract';
    document.getElementById('upload-btn').disabled = false;
    document.getElementById('upload-btn').textContent = '⬆ Upload & Extract';
    toast('Job failed — check the log');
  }
}

function addLog(msg, cls = '') {
  const box = document.getElementById('activity-log');
  const el = document.createElement('div');
  el.className = 'entry ' + cls;
  el.textContent = msg;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

// ── Jobs ──
async function loadJobs() {
  try {
    const data = await get('/api/jobs?limit=30');
    const list = data.jobs || [];
    const el = document.getElementById('jobs-list');
    if (!list.length) { el.innerHTML = '<p style="color:var(--text2);text-align:center;padding:20px">No jobs yet — extract some lyrics!</p>'; return; }
    el.innerHTML = list.map(j => `
      <div class="job-item" onclick="loadJob('${j.job_id}')">
        <span class="badge badge-${j.status}">${j.status}</span>
        <div class="job-info">
          <div class="name">${esc(j.title || j.job_id.slice(0,12))}</div>
          <div class="meta">${esc(j.language_detected || '')} · ${esc(j.lyrics_source || '')} · ${j.created_at ? new Date(j.created_at).toLocaleTimeString() : ''}</div>
        </div>
        <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); deleteJob('${j.job_id}')">✕</button>
      </div>
    `).join('');
  } catch {}
}

window.loadJob = async function(jobId) {
  try {
    currentJob = await get(`/api/job/${jobId}`);
    currentJobId = jobId;
    renderLyrics(currentJob);
    switchTo('p-viewer');
  } catch (e) { toast(e.message); }
};

window.deleteJob = async function(jobId) {
  await del(`/api/job/${jobId}`);
  toast('Deleted');
  loadJobs();
};

// ── Lyrics Viewer ──
function renderLyrics(job) {
  document.getElementById('viewer-title').textContent = job.title || 'Untitled';
  document.getElementById('viewer-meta').innerHTML = `
    ${esc(job.uploader || '?')} · ${esc(job.language_detected || '?')} (${job.language_confidence || 0}%) · Source: ${esc(job.lyrics_source || 'whisper')} · ${fmtTime(job.duration || 0)}
  `;
  const segs = job.transcript || [];
  const box = document.getElementById('lyrics-box');
  if (!segs.length) { box.innerHTML = '<p style="color:var(--text2);padding:20px;text-align:center">No lyrics found</p>'; return; }
  box.innerHTML = segs.map((s, i) => `
    <div class="lyric-line" data-i="${i}">
      ${s.start != null ? `<span class="ts">${fmtTime(s.start)}</span>` : ''}
      <span class="txt">${esc(s.text)}</span>
    </div>
  `).join('');
}

// ── Search ──
let searchT;
window.searchLyrics = function() {
  clearTimeout(searchT);
  searchT = setTimeout(async () => {
    const q = document.getElementById('search-input').value.trim();
    document.querySelectorAll('.lyric-line.highlight').forEach(e => e.classList.remove('highlight'));
    if (!q || q.length < 2 || !currentJobId) return;
    try {
      const data = await get(`/api/job/${currentJobId}/search?q=${encodeURIComponent(q)}`);
      (data.results || []).forEach(r => {
        const el = document.querySelector(`.lyric-line[data-i="${r.index}"]`);
        if (el) { el.classList.add('highlight'); el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
      });
    } catch {}
  }, 300);
};

// ── Export ──
window.exportLyrics = async function() {
  if (!currentJobId) return toast('No job selected');
  const fmt = document.getElementById('export-select').value;
  try {
    const blob = await getBlob(`/api/job/${currentJobId}/export/${fmt}`);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `wulira-lyrics.${fmt}`;
    a.click();
    toast(`Exported as ${fmt.toUpperCase()}`);
  } catch { toast('Export failed'); }
};

// ── Translate ──
window.translateLyrics = async function() {
  if (!currentJobId || !currentJob) return toast('Load a job first');
  const to = document.getElementById('translate-select').value;
  const from = currentJob.language_code || 'en';
  document.getElementById('translate-status').textContent = 'Translating...';
  try {
    const data = await post(`/api/job/${currentJobId}/translate`, { from_code: from, to_code: to });
    document.getElementById('translate-status').textContent = `✓ ${from} → ${to}`;
    document.getElementById('translate-output').innerHTML = (data.translated || []).map(s => `
      <div class="trans-row">
        <div class="orig">${esc(s.original_text || '')}</div>
        <div class="result">${esc(s.text || '')}</div>
      </div>
    `).join('');
  } catch (e) { document.getElementById('translate-status').textContent = e.message; }
};

// ── Stats ──
async function loadStats() {
  try {
    const d = await get('/api/stats');
    document.getElementById('api-stats').innerHTML = `
      <div class="stat-card"><div class="num">${d.total_jobs||0}</div><div class="lbl">Total</div></div>
      <div class="stat-card"><div class="num">${d.processing||0}</div><div class="lbl">Processing</div></div>
      <div class="stat-card"><div class="num">${d.done||0}</div><div class="lbl">Done</div></div>
      <div class="stat-card"><div class="num">${d.errors||0}</div><div class="lbl">Errors</div></div>
      <div class="stat-card"><div class="num">${(d.models_cached||[]).length}</div><div class="lbl">Models</div></div>
    `;
  } catch {}
  if (currentJobId) {
    try {
      const d = await get(`/api/job/${currentJobId}/lyrics-stats`);
      const s = d.statistics || {};
      document.getElementById('lyrics-stats-wrap').style.display = 'block';
      document.getElementById('lyrics-stats').innerHTML = `
        <div class="stat-card"><div class="num">${s.total_words||0}</div><div class="lbl">Words</div></div>
        <div class="stat-card"><div class="num">${s.unique_words||0}</div><div class="lbl">Unique</div></div>
        <div class="stat-card"><div class="num">${s.words_per_minute||0}</div><div class="lbl">WPM</div></div>
        <div class="stat-card"><div class="num">${s.vocabulary_richness||0}</div><div class="lbl">Richness</div></div>
        <div class="stat-card"><div class="num">${s.chorus_percentage||0}%</div><div class="lbl">Chorus</div></div>
      `;
    } catch {}
  }
}

// ── Helpers ──
function fmtTime(s) { const m = Math.floor(s/60); return `${m}:${String(Math.floor(s%60)).padStart(2,'0')}`; }
function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
