const API_BASE = 'https://wulira.app'; // Change to your deployed URL

export async function submitJob(url, model = 'base', language = null) {
  const res = await fetch(`${API_BASE}/api/transcribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, model, language }),
  });
  return res.json();
}

export async function getJob(jobId) {
  const res = await fetch(`${API_BASE}/api/job/${jobId}`);
  return res.json();
}

export async function getJobs(limit = 20) {
  const res = await fetch(`${API_BASE}/api/jobs?limit=${limit}`);
  return res.json();
}

export async function deleteJob(jobId) {
  const res = await fetch(`${API_BASE}/api/job/${jobId}`, { method: 'DELETE' });
  return res.json();
}

export async function exportLyrics(jobId, format = 'txt') {
  const res = await fetch(`${API_BASE}/api/job/${jobId}/export/${format}`);
  return res.text();
}

export async function searchLyrics(jobId, query) {
  const res = await fetch(`${API_BASE}/api/job/${jobId}/search?q=${encodeURIComponent(query)}`);
  return res.json();
}

export async function translateJob(jobId, fromCode, toCode) {
  const res = await fetch(`${API_BASE}/api/job/${jobId}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_code: fromCode, to_code: toCode }),
  });
  return res.json();
}

export async function getLyricsStats(jobId) {
  const res = await fetch(`${API_BASE}/api/job/${jobId}/lyrics-stats`);
  return res.json();
}

export function connectWebSocket(jobId, onMessage) {
  const proto = API_BASE.startsWith('https') ? 'wss' : 'ws';
  const host = API_BASE.replace(/^https?:\/\//, '');
  const ws = new WebSocket(`${proto}://${host}/ws/job/${jobId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}
