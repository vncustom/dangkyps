// node tests/js/run_qc.js <file.mp4> <spec-json>  -> in ket qua QC (chay dung code trinh duyet)
const fs = require('fs');
const path = require('path');
const QC = require(path.join(__dirname, '..', '..', 'app', 'static', 'js', 'qc-core.js'));

(async () => {
  const file = process.argv[2];
  const specArg = process.argv[3];   // chuoi JSON hoac duong dan file .json (tranh loi quote cua shell)
  const spec = JSON.parse((specArg.trim().startsWith('{') ? specArg : fs.readFileSync(specArg, 'utf8')).replace(/^﻿/, ''));
  const blob = await fs.openAsBlob(file);
  const reader = QC.blobReader(blob);
  const t0 = Date.now();
  const out = await QC.runCheck(reader, { name: path.basename(file), size: blob.size }, spec);
  out.seconds = (Date.now() - t0) / 1000;
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
