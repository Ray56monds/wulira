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

// Poll job status + log (fallback when WebSocket fails)
export function pollJob(jobId, onUpdate, intervalMs = 2000) {
  let active = true;
  const poll = async () => {
    if (!active) return;
    try {
      const data = await get(`/api/job/${jobId}/log`);
      onUpdate(data);
      if (data.status === 'done' || data.status === 'error') {
        active = false;
        return;
      }
    } catch {}
    if (active) setTimeout(poll, intervalMs);
  };
  poll();
  return () => { active = false; };
}

// Try WebSocket, fall back to polling
export function watchJob(jobId, onUpdate) {
  let wsOk = false;
  let stopPoll = null;

  try {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws/job/${jobId}`);

    ws.onopen = () => { wsOk = true; };
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data);
      onUpdate({ status: d.stage, progress: d.progress || 0, log: [], source: 'ws' });
      if (d.stage === 'done' || d.stage === 'error') ws.close();
    };
    ws.onerror = () => {
      if (!wsOk) startPolling();
    };
    ws.onclose = () => {
      if (!wsOk) startPolling();
    };
  } catch {
    startPolling();
  }

  function startPolling() {
    if (stopPoll) return;
    stopPoll = pollJob(jobId, (data) => {
      onUpdate({ ...data, source: 'poll' });
    });
  }

  return () => { if (stopPoll) stopPoll(); };
}
