// MD5 tang dan (khong phu thuoc thu vien) - dung de tinh MD5 file goc trong trinh duyet (Web Worker).
(function (root) {
  'use strict';

  const K = new Int32Array(64);
  for (let i = 0; i < 64; i++) K[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296) | 0;
  const S = new Int32Array([
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
    5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
    4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
    6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
  ]);

  class MD5Stream {
    constructor() {
      this.s = new Int32Array([0x67452301, 0xefcdab89 | 0, 0x98badcfe | 0, 0x10325476]);
      this.tail = new Uint8Array(64);
      this.tailLen = 0;
      this.total = 0;
    }

    // words: Int32Array (little-endian), wi: chi so word dau cua block, n: so block
    _blocks(words, wi, n) {
      const s = this.s;
      let a0 = s[0], b0 = s[1], c0 = s[2], d0 = s[3];
      for (; n > 0; n--, wi += 16) {
        let a = a0, b = b0, c = c0, d = d0, f, t, sh, i;
        for (i = 0; i < 16; i++) {
          f = (b & c) | (~b & d);
          t = (a + f + K[i] + words[wi + i]) | 0;
          a = d; d = c; c = b; sh = S[i];
          b = (b + ((t << sh) | (t >>> (32 - sh)))) | 0;
        }
        for (; i < 32; i++) {
          f = (d & b) | (~d & c);
          t = (a + f + K[i] + words[wi + ((5 * i + 1) & 15)]) | 0;
          a = d; d = c; c = b; sh = S[i];
          b = (b + ((t << sh) | (t >>> (32 - sh)))) | 0;
        }
        for (; i < 48; i++) {
          f = b ^ c ^ d;
          t = (a + f + K[i] + words[wi + ((3 * i + 5) & 15)]) | 0;
          a = d; d = c; c = b; sh = S[i];
          b = (b + ((t << sh) | (t >>> (32 - sh)))) | 0;
        }
        for (; i < 64; i++) {
          f = c ^ (b | ~d);
          t = (a + f + K[i] + words[wi + ((7 * i) & 15)]) | 0;
          a = d; d = c; c = b; sh = S[i];
          b = (b + ((t << sh) | (t >>> (32 - sh)))) | 0;
        }
        a0 = (a0 + a) | 0; b0 = (b0 + b) | 0; c0 = (c0 + c) | 0; d0 = (d0 + d) | 0;
      }
      s[0] = a0; s[1] = b0; s[2] = c0; s[3] = d0;
    }

    update(data) {
      let pos = 0;
      const len = data.length;
      this.total += len;
      if (this.tailLen > 0) {
        const need = 64 - this.tailLen;
        const take = Math.min(need, len);
        this.tail.set(data.subarray(0, take), this.tailLen);
        this.tailLen += take;
        pos = take;
        if (this.tailLen < 64) return this;
        this._blocks(new Int32Array(this.tail.buffer, 0, 16), 0, 1);
        this.tailLen = 0;
      }
      const nBlocks = (len - pos) >> 6;
      if (nBlocks > 0) {
        let src = data;
        let base = pos;
        if ((data.byteOffset + pos) % 4 !== 0) {  // can bo nho thang hang 4 byte de dung Int32Array
          src = data.slice(pos, pos + nBlocks * 64);
          base = 0;
        }
        const words = new Int32Array(src.buffer, src.byteOffset + base, nBlocks * 16);
        this._blocks(words, 0, nBlocks);
        pos += nBlocks * 64;
      }
      if (pos < len) {
        this.tail.set(data.subarray(pos), 0);
        this.tailLen = len - pos;
      }
      return this;
    }

    hex() {
      const total = this.total;
      const pad = new Uint8Array(((this.tailLen < 56 ? 56 : 120) - this.tailLen) + 8);
      pad[0] = 0x80;
      const lo = (total % 536870912) * 8;   // 2^29 * 8 = 2^32
      const hi = Math.floor(total / 536870912);
      const lenOff = pad.length - 8;
      for (let i = 0; i < 4; i++) {
        pad[lenOff + i] = (lo >>> (8 * i)) & 0xff;
        pad[lenOff + 4 + i] = (hi >>> (8 * i)) & 0xff;
      }
      this.update(pad);
      let out = '';
      for (let w = 0; w < 4; w++) {
        for (let i = 0; i < 4; i++) out += ((this.s[w] >>> (8 * i)) & 0xff).toString(16).padStart(2, '0');
      }
      return out.toUpperCase();
    }
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = MD5Stream;
  else root.MD5Stream = MD5Stream;
})(typeof self !== 'undefined' ? self : globalThis);
