// Buoc 1: Check file (iCheck: thong so + MD5 file goc, chay trong trinh duyet) -> Upload chunked.
(function () {
  const form = document.getElementById('upload-form');
  if (!form) return;
  const input = document.getElementById('upload-files');
  const unit = document.getElementById('upload-unit');
  const list = document.getElementById('upload-list');
  const btn = document.getElementById('upload-btn');
  const checkBtn = document.getElementById('check-btn');
  const results = document.getElementById('qc-results');
  const specEl = document.getElementById('qc-spec');
  const spec = JSON.parse(specEl.textContent);
  const workerUrl = specEl.dataset.worker || '/static/js/qc-worker.js';

  const fmtMB = (n) => (n / 1048576).toFixed(1) + ' MB';
  const key = (f) => `${f.name}|${f.size}|${f.lastModified}`;
  const checked = new Map();   // key -> { md5, report }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function refreshButtons() {
    const files = [...input.files];
    btn.disabled = !files.length || !files.every((f) => checked.has(key(f)));
    checkBtn.disabled = !files.length;
  }

  function renderReport(panel, rep) {
    const rows = rep.items.map((i) =>
      `<tr class="qc-${i.status.toLowerCase()}"><td>${i.n}</td><td>${esc(i.param)}</td><td>${esc(i.expected)}</td>` +
      `<td class="mono">${esc(i.actual)}</td><td><b>${i.status}</b></td></tr>`).join('');
    panel.innerHTML =
      `<div class="row"><b>${esc(rep.name)}</b><span class="badge ${rep.result === 'PASS' ? 'dat' : 'khong_dat'}">QC: ${rep.result}</span>` +
      `<span class="muted">MD5 (file gốc): <span class="mono">${rep.md5}</span></span></div>` +
      `<div class="table-wrap" style="max-height:none;margin-top:8px"><table class="qc"><thead><tr><th>Item</th><th>Parameter</th>` +
      `<th>HTV (tạm thời)</th><th>File information</th><th>Result</th></tr></thead><tbody>${rows}</tbody></table></div>` +
      `<p class="muted">INFO: chưa có giới hạn chấp nhận hoặc chưa kiểm. Kết quả chỉ mang tính tham khảo - kỹ thuật quyết định có Upload hay không.</p>`;
  }

  function checkOne(file, panel) {
    return new Promise((resolve) => {
      let worker;
      try { worker = new Worker(workerUrl); }
      catch (err) {
        panel.innerHTML = `<b>${esc(file.name)}</b><div class="alert error" style="margin-top:8px">Trình duyệt không chạy được Web Worker: ${esc(err.message)}</div>`;
        resolve(false); return;
      }
      const t0 = performance.now();
      panel.innerHTML = `<b>${esc(file.name)}</b><div class="progress"><div></div></div><div class="muted status">Đang đọc thông số và tính MD5 file gốc...</div>`;
      const bar = panel.querySelector('.progress > div'), status = panel.querySelector('.status');
      worker.onmessage = (e) => {
        const m = e.data;
        if (m.type === 'progress') {
          bar.style.width = (m.done / m.total * 100).toFixed(1) + '%';
          const mbps = m.done / 1048576 / ((performance.now() - t0) / 1000);
          status.textContent = `Tính MD5: ${fmtMB(m.done)} / ${fmtMB(m.total)} (${mbps.toFixed(0)} MB/s)`;
        } else if (m.type === 'done') {
          checked.set(key(file), { md5: m.md5, report: m.report });
          renderReport(panel, m.report);
          worker.terminate(); resolve(true);
        } else if (m.type === 'error') {
          panel.innerHTML = `<b>${esc(file.name)}</b><div class="alert error" style="margin-top:8px">Check lỗi: ${esc(m.message)}</div>`;
          worker.terminate(); resolve(false);
        }
      };
      worker.onerror = (e) => {
        panel.innerHTML = `<b>${esc(file.name)}</b><div class="alert error" style="margin-top:8px">Check lỗi: ${esc(e.message || 'worker')}</div>`;
        worker.terminate(); resolve(false);
      };
      worker.postMessage({ file, spec });
    });
  }

  input.addEventListener('change', () => { results.innerHTML = ''; refreshButtons(); });
  input.addEventListener('input', refreshButtons);

  checkBtn.addEventListener('click', async () => {
    checkBtn.disabled = true; btn.disabled = true; input.disabled = true;
    results.innerHTML = '';
    try {
      for (const file of input.files) {
        const panel = document.createElement('div');
        panel.className = 'panel';
        results.appendChild(panel);
        if (!checked.has(key(file))) await checkOne(file, panel);
        else renderReport(panel, checked.get(key(file)).report);
      }
    } finally {
      input.disabled = false;
      refreshButtons();
    }
  });

  async function api(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) {
      let msg = r.statusText;
      try { msg = (await r.json()).detail || msg; } catch (e) {}
      const err = new Error(msg); err.status = r.status; throw err;
    }
    return r.json();
  }

  async function sendChunk(id, offset, blob) {
    for (let attempt = 0; attempt < 4; attempt++) {
      try {
        return await api(`/api/upload/${id}?offset=${offset}`, { method: 'PUT', body: blob });
      } catch (e) {
        if (e.status && e.status < 500 && e.status !== 409) throw e;
        if (e.status === 409) {  // lech offset: hoi server da nhan bao nhieu
          const st = await api(`/api/upload/${id}`);
          if (st.received >= offset + blob.size) return { received: st.received };
          if (st.received !== offset) throw e;
        }
        await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
      }
    }
    throw new Error('Gửi chunk thất bại sau nhiều lần thử');
  }

  async function uploadOne(file, row) {
    const chk = checked.get(key(file));
    const bar = row.querySelector('.progress > div');
    const status = row.querySelector('.status');
    const init = await api('/api/upload/init', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_name: file.name, size: file.size, unit: unit.value,
        md5: chk.md5, qc: { result: chk.report.result, items: chk.report.items },
      }),
    });
    let offset = 0;
    while (offset < file.size) {
      const blob = file.slice(offset, Math.min(offset + init.chunk_size, file.size));
      const res = await sendChunk(init.upload_id, offset, blob);
      offset = res.received;
      bar.style.width = (offset / file.size * 100).toFixed(1) + '%';
      status.textContent = `${fmtMB(offset)} / ${fmtMB(file.size)}`;
    }
    status.textContent = 'Đã nhận đủ, đang đối chiếu MD5 và xử lý...';
    const done = await api(`/api/upload/${init.upload_id}/finish`, { method: 'POST' });
    status.textContent = `Xong - File ID ${done.file_id}, MD5 ${done.md5} (khớp MD5 lúc Check)` +
      (done.duplicate_of ? ` (⚠ trùng MD5 với File ID ${done.duplicate_of})` : '');
  }

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (btn.disabled) return;
    const files = [...input.files];
    const bad = files.filter((f) => checked.get(key(f)).report.result === 'FAIL');
    if (bad.length && !confirm(`Có ${bad.length} file KHÔNG ĐẠT một số thông số QC:\n${bad.map((f) => '- ' + f.name).join('\n')}\n\nVẫn Upload?`)) return;
    btn.disabled = true; checkBtn.disabled = true; input.disabled = true;
    let failed = false;
    for (const file of files) {
      const row = document.createElement('div');
      row.className = 'panel';
      row.innerHTML = `<b></b><div class="progress"><div></div></div><div class="muted status">Đang chờ...</div>`;
      row.querySelector('b').textContent = file.name;
      list.prepend(row);
      try { await uploadOne(file, row); }
      catch (e) {
        failed = true;
        row.querySelector('.status').textContent = 'Lỗi: ' + e.message;
        row.querySelector('.progress > div').style.background = '#f0546a';
      }
    }
    input.disabled = false; input.value = ''; results.innerHTML = ''; checked.clear();
    refreshButtons();
    if (!failed) setTimeout(() => location.reload(), 1500);
  });

  // Trinh duyet co the khoi phuc file da chon sau khi tai lai / quay lai trang (khong ban su kien change)
  refreshButtons();
  window.addEventListener('load', refreshButtons);
  window.addEventListener('pageshow', refreshButtons);
  setTimeout(refreshButtons, 300);
})();
