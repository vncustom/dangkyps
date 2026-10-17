// Upload chunked: cat file thanh chunk, gui tuan tu, server tinh MD5 tang dan.
(function () {
  const form = document.getElementById('upload-form');
  if (!form) return;
  const input = document.getElementById('upload-files');
  const unit = document.getElementById('upload-unit');
  const list = document.getElementById('upload-list');
  const btn = document.getElementById('upload-btn');

  const fmt = (n) => (n / 1048576).toFixed(1) + ' MB';

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
    const bar = row.querySelector('.progress > div');
    const status = row.querySelector('.status');
    const init = await api('/api/upload/init', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: file.name, size: file.size, unit: unit.value }),
    });
    let offset = 0;
    while (offset < file.size) {
      const blob = file.slice(offset, Math.min(offset + init.chunk_size, file.size));
      const res = await sendChunk(init.upload_id, offset, blob);
      offset = res.received;
      bar.style.width = (offset / file.size * 100).toFixed(1) + '%';
      status.textContent = `${fmt(offset)} / ${fmt(file.size)}`;
    }
    status.textContent = 'Đang tính MD5 và xử lý...';
    const done = await api(`/api/upload/${init.upload_id}/finish`, { method: 'POST' });
    status.textContent = `Xong - File ID ${done.file_id}, MD5 ${done.md5}` +
      (done.duplicate_of ? ` (⚠ trùng MD5 với File ID ${done.duplicate_of})` : '');
  }

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (!input.files.length) return;
    btn.disabled = true;
    let failed = false;
    for (const file of input.files) {
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
    btn.disabled = false;
    input.value = '';
    if (!failed) setTimeout(() => location.reload(), 1500);
  });
})();
