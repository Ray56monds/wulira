// API client with polling fallback
const API = window.location.origin;

export async function post(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

export async function get(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Request failed');
  }
  return res.json();
}

export async function del(path) {
  const res = await fetch(`${API}${path}`, { method: 'DELETE' });
  return res.json();
}

export async function getBlob(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error('Export failed');
  return res.blob();
}

// Watch job via polling (reliable on all platforms including HF Spaces)
export function watchJob(jobId, onUpdate) {
  let active = true;
  let prevLogLen = 0;

  const poll = async () => {
    if (!active) return;
    try {
      const data = await get(`/api/job/${jobId}`);
      const log = data.log || [];
      const status = data.status || 'unknown';

      // Map status to progress percentage
      const progressMap = { queued: 5, processing: 15, downloading: 25, detecting_language: 50, transcribing: 70, done: 100, error: 0 };
      let progress = progressMap[status] || 15;
      // If we have log entries, estimate progress from them
      if (log.length > prevLogLen) {
        progress = Math.min(90, 10 + log.length * 12);
      }
      if (status === 'done') progress = 100;

      onUpdate({ status, progress, log, newEntries: log.slice(prevLogLen), source: 'poll' });
      prevLogLen = log.length;

      if (status === 'done' || status === 'error') {
        active = false;
        return;
      }
    } catch {}
    if (active) setTimeout(poll, 1500);
  };

  // Start immediately
  poll();
  return () => { active = false; };
}
