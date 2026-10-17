// Doi chieu md5.js voi crypto cua Node: nhieu do dai, chia nho tuy y, buffer lech 4 byte.
const crypto = require('crypto');
const path = require('path');
const MD5Stream = require(path.join(__dirname, '..', '..', 'app', 'static', 'js', 'md5.js'));

function ref(buf) { return crypto.createHash('md5').update(buf).digest('hex').toUpperCase(); }
let seed = 12345;
const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff);

let checked = 0;
const lengths = [0, 1, 2, 3, 55, 56, 57, 63, 64, 65, 119, 120, 121, 127, 128, 129, 1000, 4096, 65537, 1048576 + 7];
for (const len of lengths) {
  const data = crypto.randomBytes(len);
  const h = new MD5Stream();
  let pos = 0;
  while (pos < len) {                       // chia manh ngau nhien (1..200000 byte)
    const n = Math.min(len - pos, 1 + (rnd() % 200000));
    // dua du lieu vao buffer lech byteOffset de kiem tra nhanh khong thang hang
    const shifted = new Uint8Array(n + 3).subarray(1 + (rnd() % 3));
    const piece = shifted.subarray(0, n); piece.set(data.subarray(pos, pos + n));
    h.update(piece);
    pos += n;
  }
  const got = h.hex();
  if (got !== ref(data)) { console.error(`MD5 SAI voi do dai ${len}: ${got} != ${ref(data)}`); process.exit(1); }
  checked++;
}
console.log(`OK ${checked} truong hop`);
