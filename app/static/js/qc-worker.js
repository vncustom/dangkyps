// Web Worker: Check file (doc metadata + tinh MD5 file goc) ma khong lam dung giao dien.
// ?v=... cua worker duoc dung lai cho cac file import de tranh ban cu trong cache
importScripts('/static/js/md5.js' + self.location.search, '/static/js/qc-core.js' + self.location.search);

self.onmessage = async (e) => {
  const { file, spec } = e.data;
  try {
    const reader = QC.blobReader(file);
    const meta = { name: file.name, size: file.size };
    const result = await QC.runCheck(reader, meta, spec, (done, total) => {
      self.postMessage({ type: 'progress', done, total });
    });
    self.postMessage({ type: 'done', md5: result.md5, report: result.report });
  } catch (err) {
    self.postMessage({ type: 'error', message: String((err && err.message) || err) });
  }
};
