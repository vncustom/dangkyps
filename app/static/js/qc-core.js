// QC (iCheck) chay hoan toan trong trinh duyet tren FILE GOC cua ky thuat:
//  - doc metadata MP4 (ftyp/moov) de lay thong so video/audio
//  - tinh MD5 toan bo file goc
//  - doi chieu voi yeu cau HTV (spec) -> bao cao PASS / FAIL / INFO
// Khong phu thuoc DOM, chay duoc trong Web Worker va trong Node (de test).
(function (root) {
  'use strict';

  const MD5Stream = (typeof module !== 'undefined' && module.exports) ? require('./md5.js') : root.MD5Stream;

  // ---------- doc file ----------
  function blobReader(blob) {
    return {
      size: blob.size,
      read: async (off, len) => new Uint8Array(await blob.slice(off, Math.min(off + len, blob.size)).arrayBuffer()),
    };
  }

  async function md5File(reader, onProgress, chunk) {
    chunk = chunk || 8 * 1024 * 1024;
    const h = new MD5Stream();
    let off = 0;
    let next = reader.read(0, chunk);
    while (off < reader.size) {
      const cur = await next;
      off += cur.length;
      if (cur.length === 0) throw new Error('Đọc file bị gián đoạn (file thay đổi hoặc không đọc được)');
      if (off < reader.size) next = reader.read(off, chunk);   // doc truoc khoi tiep theo trong luc bam
      h.update(cur);
      if (onProgress) onProgress(off, reader.size);
    }
    return h.hex();
  }

  // ---------- helper nhi phan ----------
  const u8 = (b, o) => b[o];
  const u16 = (b, o) => (b[o] << 8) | b[o + 1];
  const u32 = (b, o) => ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0;
  const i32 = (b, o) => (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3];
  const u64 = (b, o) => u32(b, o) * 4294967296 + u32(b, o + 4);
  const i64 = (b, o) => i32(b, o) * 4294967296 + u32(b, o + 4);
  const cc = (b, o) => String.fromCharCode(b[o], b[o + 1], b[o + 2], b[o + 3]);

  function boxes(b, start, end) {
    const out = [];
    let p = start;
    while (p + 8 <= end) {
      let size = u32(b, p);
      const type = cc(b, p + 4);
      let hdr = 8;
      if (size === 1) { size = u64(b, p + 8); hdr = 16; } else if (size === 0) { size = end - p; }
      if (size < hdr || p + size > end) break;
      out.push({ type, start: p, hdr, data: p + hdr, end: p + size });
      p += size;
    }
    return out;
  }
  const kids = (b, box) => boxes(b, box.data, box.end);
  const kid = (b, box, type) => kids(b, box).find((x) => x.type === type);

  async function topLevelBoxes(reader) {
    const list = [];
    let off = 0;
    for (let n = 0; off + 8 <= reader.size && n < 20000; n++) {
      const h = await reader.read(off, 16);
      let size = u32(h, 0);
      const type = cc(h, 4);
      let hdr = 8;
      if (size === 1) { size = u64(h, 8); hdr = 16; } else if (size === 0) { size = reader.size - off; }
      if (size < hdr) break;
      list.push({ type, off, size, hdr });
      off += size;
    }
    return list;
  }

  // ---------- bit reader cho SPS H.264 ----------
  function unescapeRbsp(b) {
    const out = [];
    for (let i = 0; i < b.length; i++) {
      if (i >= 2 && b[i] === 3 && b[i - 1] === 0 && b[i - 2] === 0) continue;
      out.push(b[i]);
    }
    return Uint8Array.from(out);
  }
  class Bits {
    constructor(b) { this.b = b; this.p = 0; }
    bit() { const v = (this.b[this.p >> 3] >> (7 - (this.p & 7))) & 1; this.p++; return v; }
    bits(n) { let v = 0; while (n-- > 0) v = v * 2 + this.bit(); return v; }
    ue() { let z = 0; while (this.bit() === 0 && z < 32) z++; return z === 0 ? 0 : (2 ** z - 1) + this.bits(z); }
    se() { const k = this.ue(); return (k & 1) ? (k + 1) / 2 : -(k / 2); }
  }
  function parseAvcSps(nal) {
    const r = new Bits(unescapeRbsp(nal.subarray(1)));
    const profile = r.bits(8); r.bits(8); const level = r.bits(8); r.ue();
    let chroma = 1, depth = 8;
    if ([100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135].includes(profile)) {
      chroma = r.ue();
      if (chroma === 3) r.bit();
      depth = r.ue() + 8; r.ue(); r.bit();
      if (r.bit()) {
        const lists = chroma !== 3 ? 8 : 12;
        for (let i = 0; i < lists; i++) {
          if (!r.bit()) continue;
          let last = 8, nxt = 8;
          for (let j = 0; j < (i < 6 ? 16 : 64); j++) {
            if (nxt !== 0) nxt = (last + r.se() + 256) % 256;
            last = nxt === 0 ? last : nxt;
          }
        }
      }
    }
    r.ue();
    const pocType = r.ue();
    if (pocType === 0) r.ue();
    else if (pocType === 1) { r.bit(); r.se(); r.se(); const n = r.ue(); for (let i = 0; i < n; i++) r.se(); }
    r.ue(); r.bit(); r.ue(); r.ue();
    const frameMbsOnly = r.bit();
    return { profile, level, chroma, depth, progressive: frameMbsOnly === 1 };
  }

  const AVC_PROFILES = { 66: 'Baseline', 77: 'Main', 88: 'Extended', 100: 'High', 110: 'High 10', 122: 'High 4:2:2', 244: 'High 4:4:4 Predictive' };
  const HEVC_PROFILES = { 1: 'Main', 2: 'Main 10', 3: 'Main Still Picture', 4: 'Rext' };
  const CODEC_NAMES = { avc1: 'h264', avc3: 'h264', hvc1: 'hevc', hev1: 'hevc', mp4v: 'mpeg4', av01: 'av1', vp09: 'vp9' };
  const AAC_PROFILES = { 1: 'Main', 2: 'LC', 3: 'SSR', 4: 'LTP', 5: 'HE-AAC', 29: 'HE-AACv2' };
  const AAC_RATES = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350];
  const AAC_CH = [0, 1, 2, 3, 4, 5, 6, 8];

  function pixFmt(chroma, depth) {
    const base = { 0: 'gray', 1: 'yuv420p', 2: 'yuv422p', 3: 'yuv444p' }[chroma] || 'unknown';
    return depth > 8 ? `${base}${depth}le` : base;
  }

  // ---------- parse track ----------
  function parseStbl(b, stbl) {
    const out = { sizeSum: 0, count: 0, deltas: [], firstChunk: null, entry: null };
    const stsd = kid(b, stbl, 'stsd');
    if (stsd) out.entry = boxes(b, stsd.data + 8, stsd.end)[0] || null;
    const stts = kid(b, stbl, 'stts');
    if (stts) {
      const n = u32(b, stts.data + 4);
      for (let i = 0; i < n; i++) out.deltas.push({ count: u32(b, stts.data + 8 + i * 8), delta: u32(b, stts.data + 12 + i * 8) });
    }
    const stsz = kid(b, stbl, 'stsz');
    if (stsz) {
      const fixed = u32(b, stsz.data + 4), n = u32(b, stsz.data + 8);
      out.count = n;
      if (fixed) out.sizeSum = fixed * n;
      else for (let i = 0; i < n; i++) out.sizeSum += u32(b, stsz.data + 12 + i * 4);
    }
    const co = kid(b, stbl, 'stco') || kid(b, stbl, 'co64');
    if (co && u32(b, co.data + 4) > 0) out.firstChunk = co.type === 'stco' ? u32(b, co.data + 8) : u64(b, co.data + 8);
    return out;
  }

  function parseTrak(b, trak) {
    const t = { handler: '', timescale: 1, duration: 0, elst: [] };
    const mdia = kid(b, trak, 'mdia');
    if (!mdia) return null;
    const hdlr = kid(b, mdia, 'hdlr');
    if (hdlr) t.handler = cc(b, hdlr.data + 8);
    const mdhd = kid(b, mdia, 'mdhd');
    if (mdhd) {
      const v1 = u8(b, mdhd.data) === 1;
      t.timescale = u32(b, mdhd.data + (v1 ? 20 : 12)) || 1;
      t.duration = v1 ? u64(b, mdhd.data + 24) : u32(b, mdhd.data + 16);
    }
    const minf = kid(b, mdia, 'minf');
    const stbl = minf && kid(b, minf, 'stbl');
    if (stbl) Object.assign(t, parseStbl(b, stbl));
    const edts = kid(b, trak, 'edts');
    const elst = edts && kid(b, edts, 'elst');
    if (elst) {
      const v1 = u8(b, elst.data) === 1;
      const n = u32(b, elst.data + 4);
      let p = elst.data + 8;
      for (let i = 0; i < n; i++) {
        t.elst.push(v1 ? { dur: u64(b, p), media: i64(b, p + 8) } : { dur: u32(b, p), media: i32(b, p + 4) });
        p += v1 ? 20 : 12;
      }
    }
    t.udta = kid(b, trak, 'udta') || null;
    return t;
  }

  function parseVideoEntry(b, entry) {
    const v = { fourcc: entry.type, codec: CODEC_NAMES[entry.type] || entry.type.trim() };
    v.width = u16(b, entry.data + 24);
    v.height = u16(b, entry.data + 26);
    const cs = boxes(b, entry.data + 78, entry.end);
    const pasp = cs.find((x) => x.type === 'pasp');
    v.par = pasp ? [u32(b, pasp.data) || 1, u32(b, pasp.data + 4) || 1] : [1, 1];
    const hvcC = cs.find((x) => x.type === 'hvcC');
    const avcC = cs.find((x) => x.type === 'avcC');
    if (hvcC) {
      const d = hvcC.data;
      const idc = u8(b, d + 1) & 0x1f;
      const flags = u8(b, d + 6);
      const prog = (flags >> 7) & 1, inter = (flags >> 6) & 1;
      v.profile = HEVC_PROFILES[idc] || `profile_idc ${idc}`;
      v.level = u8(b, d + 12) / 30;
      v.chroma = u8(b, d + 16) & 3;
      v.depth = (u8(b, d + 17) & 7) + 8;
      v.progressive = prog && !inter ? true : (!prog && inter ? false : null);
      v.scanNote = 'hvcC general_progressive/interlaced_source_flag';
    } else if (avcC) {
      const d = avcC.data;
      v.profile = AVC_PROFILES[u8(b, d + 1)] || `profile_idc ${u8(b, d + 1)}`;
      v.level = u8(b, d + 3) / 10;
      v.chroma = 1; v.depth = 8; v.progressive = null;
      if ((u8(b, d + 5) & 0x1f) > 0) {
        const len = u16(b, d + 6);
        try {
          const sps = parseAvcSps(b.subarray(d + 8, d + 8 + len));
          v.chroma = sps.chroma; v.depth = sps.depth; v.progressive = sps.progressive;
          v.scanNote = 'SPS frame_mbs_only_flag';
        } catch (e) { /* giu mac dinh */ }
      }
    }
    return v;
  }

  function parseDescriptors(b, p, end, found) {
    while (p + 2 <= end) {
      const tag = b[p++];
      let len = 0, n = 0, c;
      do { c = b[p++]; len = (len << 7) | (c & 0x7f); n++; } while ((c & 0x80) && n < 4);
      if (tag === 0x03) { parseDescriptors(b, p + 3 + ((b[p + 2] & 0x80) ? 2 : 0), p + len, found); }
      else if (tag === 0x04) { found.oti = b[p]; parseDescriptors(b, p + 13, p + len, found); }
      else if (tag === 0x05) { found.asc = b.subarray(p, p + len); }
      p += len;
    }
  }

  // Cac fourcc audio khong nen (PCM) trong MP4/MOV
  const PCM_FOURCC = new Set(['sowt', 'twos', 'in24', 'in32', 'fl32', 'fl64', 'lpcm', 'ipcm', 'fpcm', 'raw ', 's16l', 's16b', 's24l', 's24b']);

  function parseAudioEntry(b, entry) {
    const ver = u16(b, entry.data + 8);
    const a = { fourcc: entry.type, codec: PCM_FOURCC.has(entry.type) ? 'pcm' : entry.type.trim(),
      channels: u16(b, entry.data + 16), rate: u32(b, entry.data + 24) >>> 16 };
    if (ver === 2) {   // QuickTime sound description v2: sample rate la float64, kenh la uint32
      a.rate = Math.round(new DataView(b.buffer, b.byteOffset + entry.data + 32, 8).getFloat64(0));
      a.channels = u32(b, entry.data + 40);
    }
    const cs = boxes(b, entry.data + 28 + (ver === 1 ? 16 : ver === 2 ? 36 : 0), entry.end);
    const esds = cs.find((x) => x.type === 'esds');
    if (entry.type === 'mp4a' && esds) {
      const found = {};
      parseDescriptors(b, esds.data + 4, esds.end, found);
      if (found.oti === 0x40 && found.asc && found.asc.length >= 2) {
        const r = new Bits(found.asc);
        let aot = r.bits(5);
        if (aot === 31) aot = 32 + r.bits(6);
        const idx = r.bits(4);
        const rate = idx === 15 ? r.bits(24) : AAC_RATES[idx];
        const chCfg = r.bits(4);
        a.codec = 'aac';
        a.profile = AAC_PROFILES[aot] || `AOT ${aot}`;
        if (rate) a.rate = rate;
        if (chCfg > 0 && chCfg < AAC_CH.length) a.channels = AAC_CH[chCfg];
      } else if (found.oti === 0x6b || found.oti === 0x69) { a.codec = 'mp3'; }
    }
    return a;
  }

  function frameCountToTc(n, nf, drop) {
    if (drop) {
      const df = Math.round(nf * 0.066666);
      const per10 = nf * 600 - df * 9, perMin = nf * 60 - df;
      const d = Math.floor(n / per10), m = n % per10;
      n += df * 9 * d + (m > df ? df * Math.floor((m - df) / perMin) : 0);
    }
    const ff = n % nf, s = Math.floor(n / nf);
    const p = (x) => String(x).padStart(2, '0');
    return `${p(Math.floor(s / 3600))}:${p(Math.floor(s / 60) % 60)}:${p(s % 60)}${drop ? ';' : ':'}${p(ff)}`;
  }

  // ---------- doc thong tin file ----------
  async function readInfo(reader) {
    const top = await topLevelBoxes(reader);
    const info = { size: reader.size, brand: '', fragmented: false, video: null, audio: null, startTc: null, startTcNote: '', startTime: 0 };
    const ftyp = top.find((t) => t.type === 'ftyp');
    if (ftyp) info.brand = cc(await reader.read(ftyp.off + ftyp.hdr, 4), 0);
    const moovTop = top.find((t) => t.type === 'moov');
    if (!moovTop) throw new Error('Không tìm thấy khối moov: file không phải MP4 hợp lệ hoặc chưa ghi xong');
    if (moovTop.size > 512 * 1024 * 1024) throw new Error('Khối moov quá lớn');
    const b = await reader.read(moovTop.off, moovTop.size);
    const moov = { data: moovTop.hdr, end: moovTop.size };
    info.fragmented = top.some((t) => t.type === 'moof') || !!kid(b, moov, 'mvex');

    let movieTs = 1000;
    const mvhd = kid(b, moov, 'mvhd');
    if (mvhd) movieTs = u32(b, mvhd.data + (u8(b, mvhd.data) === 1 ? 20 : 12)) || 1000;

    const tracks = kids(b, moov).filter((x) => x.type === 'trak').map((x) => parseTrak(b, x)).filter(Boolean);
    const vt = tracks.find((t) => t.handler === 'vide' && t.entry);
    const at = tracks.find((t) => t.handler === 'soun' && t.entry);
    const tt = tracks.find((t) => t.handler === 'tmcd' && t.entry);

    if (vt) {
      const v = parseVideoEntry(b, vt.entry);
      const total = vt.deltas.reduce((s, d) => s + d.count * d.delta, 0);
      v.packets = vt.deltas.reduce((s, d) => s + d.count, 0) || vt.count;
      v.durationSec = (total || vt.duration) / vt.timescale;
      const body = vt.deltas.slice();   // bo qua sample cuoi khi xet do deu
      if (body.length && body[body.length - 1].count > 0) body[body.length - 1] = { count: body[body.length - 1].count - 1, delta: body[body.length - 1].delta };
      const distinct = new Set(body.filter((d) => d.count > 0).map((d) => d.delta));
      v.constant = v.packets > 0 ? distinct.size <= 1 : null;
      const delta = vt.deltas.length ? vt.deltas[0].delta : 0;
      v.fps = v.packets > 0 && v.durationSec > 0 ? (v.constant && delta ? vt.timescale / delta : v.packets / v.durationSec) : null;
      v.deltaMs = v.constant && delta ? (delta / vt.timescale) * 1000 : null;
      v.bitrate = v.durationSec > 0 ? (vt.sizeSum * 8) / v.durationSec : null;
      let g = (x, y) => (y ? g(y, x % y) : x);
      const w = v.width * v.par[0], h = v.height * v.par[1];
      const ratio = h ? w / h : 0;
      const known = [[16, 9], [4, 3], [21, 9], [1, 1], [3, 2], [2, 1]].find(([x, y]) => Math.abs(ratio - x / y) < 0.01);
      v.aspect = known ? `${known[0]}:${known[1]}` : (h ? `${w / g(w, h)}:${h / g(w, h)}` : '');
      info.video = v;
      let empty = 0;
      for (const e of vt.elst) { if (e.media === -1) empty += e.dur; else break; }
      info.startTime = empty / movieTs;
    }
    if (at) {
      const a = parseAudioEntry(b, at.entry);
      const total = at.deltas.reduce((s, d) => s + d.count * d.delta, 0);
      a.durationSec = (total || at.duration) / at.timescale;
      a.bitrate = a.durationSec > 0 ? (at.sizeSum * 8) / a.durationSec : null;
      info.audio = a;
    }

    // start timecode: track tmcd, neu khong co thi metadata hang (cac atom (c)TIM/(c)TSC/(c)TSZ trong udta)
    const vendor = {};
    const udtas = [kid(b, moov, 'udta'), ...tracks.map((t) => t.udta)].filter(Boolean);
    for (const u of udtas) {
      for (const x of kids(b, u)) {
        if (b[x.start + 4] === 0xa9) {
          const len = u16(b, x.data);
          vendor[cc(b, x.start + 4)] = String.fromCharCode(...b.subarray(x.data + 4, x.data + 4 + len)).trim();
        }
      }
    }
    if (tt && tt.firstChunk !== null && tt.firstChunk + 4 <= reader.size) {
      const e = tt.entry;
      const nf = u8(b, e.data + 24) || Math.round(info.video && info.video.fps || 25);
      const drop = (u32(b, e.data + 12) & 1) === 1;
      const n = u32(await reader.read(tt.firstChunk, 4), 0);
      info.startTc = frameCountToTc(n, nf, drop);
      info.startTcNote = 'tmcd track';
    } else if (vendor['©TIM']) {
      info.startTc = vendor['©TIM'];
      info.startTcNote = 'vendor ©TIM metadata; no tmcd track';
      if (vendor['©TSC']) info.startTcNote += `; ©TSC=${vendor['©TSC']}`;
      if (vendor['©TSZ']) info.startTcNote += `; ©TSZ=${vendor['©TSZ']}`;
    }
    return info;
  }

  // ---------- doi chieu spec ----------
  const fmt = {
    gib: (n) => `${(n / 1073741824).toFixed(3)} GiB`,
    mbps: (n) => `${(n / 1e6).toFixed(2)} Mb/s`,
    kbps: (n) => `${Math.round(n / 1000)} kb/s`,
  };
  const CODEC_LABEL = { h264: 'H.264 / AVC', hevc: 'H.265 / HEVC', mpeg4: 'MPEG-4 Visual', av1: 'AV1', vp9: 'VP9' };

  function evaluate(info, meta, md5, spec) {
    const items = [];
    const add = (param, expected, actual, status) => items.push({ n: items.length + 1, param, expected, actual, status });
    const v = info.video, a = info.audio;
    const NA = 'Không đọc được';
    const eq = (x, y) => String(x).toLowerCase() === String(y).toLowerCase();
    const judge = (ok, known) => (known === false ? 'INFO' : (ok ? 'PASS' : 'FAIL'));

    add('File name', 'Display only', meta.name, 'INFO');
    add('File size', 'Display only', fmt.gib(meta.size), 'INFO');
    add('Container', spec.container, `ISO Base Media (brand ${info.brand || '?'})${info.fragmented ? ', fragmented' : ''}`, info.brand === 'qt  ' ? 'FAIL' : 'PASS');
    add('Video compression', CODEC_LABEL[spec.video_codec] || spec.video_codec, v ? v.codec : 'Không có video', v ? judge(eq(v.codec, spec.video_codec)) : 'FAIL');
    add('Video profile', spec.video_profiles.join(' / '), v ? v.profile || NA : '-',
      v && v.profile ? judge(spec.video_profiles.some((p) => eq(p, v.profile))) : (v ? 'INFO' : 'FAIL'));
    add('Video level', `≥ ${spec.video_level_min.toFixed(1)}`, v && v.level ? v.level.toFixed(1) : NA, v && v.level ? judge(v.level >= spec.video_level_min - 1e-6) : 'INFO');
    add('Resolution', `${spec.width} × ${spec.height}`, v ? `${v.width} × ${v.height}` : '-', v ? judge(v.width === spec.width && v.height === spec.height) : 'FAIL');
    add('Aspect ratio', spec.aspect, v ? v.aspect : '-', v ? judge(eq(v.aspect, spec.aspect)) : 'FAIL');
    add('Frame rate', `${spec.fps.toFixed(3)} fps`, v && v.fps ? `${v.fps.toFixed(3)} fps` : NA, v && v.fps ? judge(Math.abs(v.fps - spec.fps) < 0.005) : 'INFO');
    const cad = v && v.constant !== null && v.packets ? (v.constant ? `Constant (${v.packets} packets; ${v.deltaMs.toFixed(3)} ms spacing)` : `Variable (${v.packets} packets)`) : NA;
    add('Frame cadence', spec.cadence[0].toUpperCase() + spec.cadence.slice(1), cad, v && v.constant !== null && v.packets ? judge(eq(v.constant ? 'constant' : 'variable', spec.cadence)) : 'INFO');
    const scan = v ? (v.progressive === true ? 'progressive' : v.progressive === false ? 'interlaced' : 'unknown (flag absent)') : '-';
    add('Scan', spec.scan[0].toUpperCase() + spec.scan.slice(1), v && v.scanNote ? `${scan} (${v.scanNote})` : scan,
      v && v.progressive !== null ? judge(eq(scan, spec.scan)) : (v ? 'INFO' : 'FAIL'));
    const chromaTxt = { 0: '4:0:0', 1: '4:2:0', 2: '4:2:2', 3: '4:4:4' };
    add('Chroma / bit depth', `${spec.chroma} / ${spec.bit_depth}-bit`, v && v.chroma !== undefined ? `${chromaTxt[v.chroma]} / ${v.depth}-bit (${pixFmt(v.chroma, v.depth)})` : NA,
      v && v.chroma !== undefined ? judge(chromaTxt[v.chroma] === spec.chroma && v.depth === spec.bit_depth) : 'INFO');
    add('Video bitrate', 'VBR; limits pending', v && v.bitrate ? fmt.mbps(v.bitrate) : NA, 'INFO');
    add('GOP / CABAC / references', 'Display only', 'Not measured in quick scan', 'INFO');
    const audioLabel = (f) => (f === 'aac' ? `AAC ${spec.audio_aac_profile}` : f === 'pcm' ? 'PCM (không nén)' : f.toUpperCase());
    const audioOk = (x) => spec.audio_formats.some((f) => (f === 'aac' ? x.codec === 'aac' && eq(x.profile || '', spec.audio_aac_profile) : x.codec === f));
    add('Audio format', spec.audio_formats.map(audioLabel).join(' / '),
      a ? (a.codec === 'pcm' ? `pcm (${a.fourcc.trim()})` : `${a.codec}${a.profile ? ' ' + a.profile : ''}`) : 'Không có audio',
      a ? judge(audioOk(a)) : 'FAIL');
    add('Audio sample rate', `${spec.audio_rate / 1000} kHz`, a ? `${a.rate} Hz` : '-', a ? judge(a.rate === spec.audio_rate) : 'FAIL');
    add('Audio channels', spec.audio_channels === 2 ? 'Stereo L/R' : String(spec.audio_channels), a ? String(a.channels) : '-', a ? judge(a.channels === spec.audio_channels) : 'FAIL');
    add('Audio bitrate', 'Limits pending', a && a.bitrate ? fmt.kbps(a.bitrate) : NA, 'INFO');
    add('Duration', 'Display only', v ? `${v.durationSec.toFixed(3)} s` : NA, 'INFO');
    add('Start timecode', `${spec.start_tc} (provisional)`, info.startTc ? `${info.startTc} (${info.startTcNote})` : 'Không có timecode trong file',
      info.startTc ? judge(info.startTc === spec.start_tc) : 'INFO');
    add('Start time', 'Rule pending', info.startTime.toFixed(6), 'INFO');
    add('Integrated loudness', 'Not specified', 'Not checked', 'INFO');
    add('True peak', 'Not specified', 'Not checked', 'INFO');
    add('Loudness range', 'Not specified', 'Not checked', 'INFO');
    add('File MD5', 'Tính từ file gốc', md5 || 'Not checked', 'INFO');
    return { result: items.some((i) => i.status === 'FAIL') ? 'FAIL' : 'PASS', items, md5, name: meta.name, size: meta.size };
  }

  // Chay tron bo Check: parse metadata -> MD5 -> danh gia
  async function runCheck(reader, meta, spec, onProgress) {
    const info = await readInfo(reader);
    const md5 = await md5File(reader, onProgress);
    return { info, md5, report: evaluate(info, meta, md5, spec) };
  }

  const api = { blobReader, md5File, readInfo, evaluate, runCheck, MD5Stream };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.QC = api;
})(typeof self !== 'undefined' ? self : globalThis);
