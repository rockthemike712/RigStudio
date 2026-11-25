/* ----- finding the words: a small singing-voice detector -----
   Per 20 ms frame of the stereo mix (22 kHz): 13 MFCCs (tone colour), how centred the sound is, pitch strength and
   pitch, spectral flatness/centroid, sibilance and loudness. Each frame also sees the mean and spread of those over
   the surrounding ~0.5 s. A small neural network (VOCAL_MODEL, trained on songs whose vocals were separated with
   Demucs to get the true "is someone singing" timeline) turns that into a probability of singing. The mouth opens
   only inside sung phrases, follows each syllable's loudness, and vowel colour sets how wide or round it is. */
function fftInPlace(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) { let bit = n >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit; if (i < j) { let q = re[i]; re[i] = re[j]; re[j] = q; q = im[i]; im[i] = im[j]; im[j] = q; } }
  for (let len = 2; len <= n; len <<= 1) { const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang), h = len >> 1;
    for (let i = 0; i < n; i += len) { let cr = 1, ci = 0; for (let j = 0; j < h; j++) { const a = i + j, b = a + h, xr = re[b] * cr - im[b] * ci, xi = re[b] * ci + im[b] * cr;
      re[b] = re[a] - xr; im[b] = im[a] - xi; re[a] += xr; im[a] += xi; const q = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = q; } } }
}
const VF_PER = 20, VF_CTX = 12;   // per-frame features; context half-width in frames (±0.24 s)
async function vocalFeatures(buf, progress) {
  const sr = 22050, N = 1024, hop = 441, len = Math.ceil(buf.duration * sr);
  const oc = new OfflineAudioContext(2, len, sr), src = oc.createBufferSource(), hp = oc.createBiquadFilter();
  src.buffer = buf; hp.type = 'highpass'; hp.frequency.value = 80; src.connect(hp); hp.connect(oc.destination); src.start();
  const r = await oc.startRendering(), Lc = r.getChannelData(0), Rc = r.numberOfChannels > 1 ? r.getChannelData(1) : Lc;
  const fr = Math.max(0, Math.floor((Lc.length - N) / hop)), half = N / 2, binHz = sr / N, kb = f => Math.round(f / binHz);
  const win = new Float32Array(N).map((_, i) => .5 - .5 * Math.cos(2 * Math.PI * i / (N - 1)));
  // 26 mel filters 100–8000 Hz → 13 cepstral coefficients
  const NM = 26, mel = f => 2595 * Math.log10(1 + f / 700), imel = m => 700 * (10 ** (m / 2595) - 1), mpts = [];
  for (let i = 0; i < NM + 2; i++) mpts.push(kb(imel(mel(100) + (mel(8000) - mel(100)) * i / (NM + 1))));
  const dct = []; for (let c = 0; c < 13; c++) { const row = new Float32Array(NM); for (let m = 0; m < NM; m++) row[m] = Math.cos(Math.PI * c * (m + .5) / NM); dct.push(row); }
  const b0 = kb(250), b1 = kb(4000), f1a = kb(300), f1b = kb(900), f2a = kb(1400), f2b = kb(2800), s0 = kb(4500), s1 = kb(9000);
  const X = new Float32Array(fr * VF_PER), cdb = new Float32Array(fr), harmA = new Float32Array(fr), f1r = new Float32Array(fr), f2r = new Float32Array(fr);
  const re = new Float64Array(N), im = new Float64Array(N), Pm = new Float64Array(half), Pc = new Float64Array(N), melE = new Float64Array(NM);
  for (let f = 0; f < fr; f++) {
    const o = f * hop; for (let i = 0; i < N; i++) { re[i] = Lc[o + i] * win[i]; im[i] = Rc[o + i] * win[i]; }
    fftInPlace(re, im); Pc.fill(0);
    let eAll = 0, eC = 0, eM = 0, e1 = 0, e2 = 0, eS = 0, eSide = 0, lg = 0, nb = 0, cen = 0;
    for (let k = 1; k < half; k++) {   // split the packed transform into left/right, then mid, side and the centred part
      const zr = re[k], zi = im[k], wr2 = re[N - k], wi2 = -im[N - k];
      const ar = (zr + wr2) / 2, ai = (zi + wi2) / 2, br = (zi - wi2) / 2, bi = -(zr - wr2) / 2;
      const M = Math.hypot((ar + br) / 2, (ai + bi) / 2), Sd = Math.hypot((ar - br) / 2, (ai - bi) / 2), c = Math.max(0, 1 - Sd / (M + 1e-9)), p = M * M;
      Pm[k] = p; eAll += p; eSide += Sd * Sd;
      if (k >= b0 && k <= b1) { const pc = p * c * c; Pc[k] = pc; Pc[N - k] = pc; eC += pc; eM += p; if (k >= f1a && k < f1b) e1 += pc; if (k >= f2a && k < f2b) e2 += pc; lg += Math.log(p + 1e-12); nb++; cen += k * p; }
      if (k >= s0 && k < s1) eS += p;
    }
    for (let m = 0; m < NM; m++) { let s = 0; const a = mpts[m], c2 = mpts[m + 1], d = mpts[m + 2];
      for (let k = a; k < d; k++) s += Pm[k] * (k < c2 ? (k - a) / Math.max(1, c2 - a) : (d - k) / Math.max(1, d - c2)); melE[m] = Math.log(s + 1e-10); }
    const base = f * VF_PER; for (let c = 0; c < 13; c++) { let s = 0; for (let m = 0; m < NM; m++) s += dct[c][m] * melE[m]; X[base + c] = s / NM; }
    for (let i = 0; i < N; i++) { re[i] = Pc[i]; im[i] = 0; } fftInPlace(re, im);    // autocorrelation of the centred voice band → pitch
    let best = 25, bv = -1e30; for (let j = 25; j <= 220; j++) if (re[j] > bv) { bv = re[j]; best = j; }
    const harm = bv / (re[0] + 1e-12);
    cdb[f] = 10 * Math.log10(eC + 1e-12); harmA[f] = harm; f1r[f] = e1 / (eC + 1e-12); f2r[f] = e2 / (eC + 1e-12);
    X[base + 13] = eC / (eM + 1e-12);                                      // how centred the voice band is
    X[base + 14] = Math.log10((eSide + 1e-9) / (eAll + 1e-9));             // side vs whole
    X[base + 15] = harm;                                                   // pitch strength
    X[base + 16] = harm > .3 ? Math.log2(sr / best / 100) : 0;             // pitch (octaves above 100 Hz)
    X[base + 17] = nb ? Math.exp(lg / nb) / (eM / nb + 1e-12) : 0;         // spectral flatness
    X[base + 18] = eM > 0 ? Math.log2(cen / eM * binHz / 250 + 1e-6) : 0;   // centroid
    X[base + 19] = Math.log10(eS / (eAll + 1e-12) + 1e-6);                 // sibilance share
    if (f % 400 === 399) { progress && progress(f / fr); await new Promise(q => setTimeout(q)); }
  }
  // loudness relative to the song (so quiet songs and loud masters look alike)
  const sorted = Float32Array.from(cdb).sort(), top = sorted[Math.floor(sorted.length * .99)] || 0;
  return { fr, X, cdb, top, harm: harmA, f1r, f2r, lipRate: sr / hop };
}
function contextFeatures(V) {   // per frame: its own features + mean & spread over ±0.24 s + loudness
  const { fr, X } = V, D = VF_PER * 2 + 2, Z = new Float32Array(fr * D), sum = new Float64Array(VF_PER), sq = new Float64Array(VF_PER);
  for (let f = 0; f < fr; f++) {
    sum.fill(0); sq.fill(0); let n = 0;
    for (let j = Math.max(0, f - VF_CTX); j <= Math.min(fr - 1, f + VF_CTX); j++) { n++; for (let c = 0; c < VF_PER; c++) { const v = X[j * VF_PER + c]; sum[c] += v; sq[c] += v * v; } }
    const o = f * D; for (let c = 0; c < VF_PER; c++) { const m = sum[c] / n; Z[o + c] = m; Z[o + VF_PER + c] = Math.sqrt(Math.max(0, sq[c] / n - m * m)); }
    Z[o + D - 2] = (V.cdb[f] - V.top) / 20; let lo = 0; for (let j = Math.max(0, f - VF_CTX); j <= Math.min(fr - 1, f + VF_CTX); j++) lo = Math.max(lo, V.cdb[j]); Z[o + D - 1] = (lo - V.top) / 20;
  }
  return { Z, D };
}
function vocalProbability(V) {   // run the small network over every frame
  const { Z, D } = contextFeatures(V), M = VOCAL_MODEL, H = M.b1.length, p = new Float32Array(V.fr), h = new Float32Array(H);
  for (let f = 0; f < V.fr; f++) {
    const o = f * D; for (let j = 0; j < H; j++) { let s = M.b1[j]; for (let i = 0; i < D; i++) s += M.W1[j * D + i] * (Z[o + i] - M.mu[i]) / M.sd[i]; h[j] = s > 0 ? s : 0; }
    let s = M.b2; for (let j = 0; j < H; j++) s += M.W2[j] * h[j]; p[f] = 1 / (1 + Math.exp(-s));
  }
  return p;
}
async function vocalTrack(buf, progress) {
  const V = await vocalFeatures(buf, progress), fr = V.fr;
  const prob = typeof VOCAL_MODEL !== 'undefined' ? vocalProbability(V) : new Float32Array(fr);
  const clamp = v => Math.max(0, Math.min(1, v)), phrase = new Float32Array(fr), lip = new Float32Array(fr), width = new Float32Array(fr), near = new Uint8Array(fr);
  for (let f = 0; f < fr; f++) {
    let s = 0, n = 0, lm = -1e9; for (let j = f - 7; j <= f + 7; j++) if (j >= 0 && j < fr) { s += prob[j]; n++; } for (let j = f - 25; j < f + 25; j++) if (j >= 0 && j < fr) lm = Math.max(lm, V.cdb[j]);
    phrase[f] = s / n; lip[f] = clamp((V.cdb[f] - (lm - 18)) / 18); width[f] = clamp((V.f2r[f] - .08) / .35 + .2 - (V.f1r[f] - .5) * .4);
    for (let j = f - 3; j <= f + 3; j++) if (j >= 0 && j < fr && V.harm[j] > .3) { near[f] = 1; break; }
  }
  return { lipRate: V.lipRate, phrase, lip, width, near, prob };
}
function buildMouth(A, sens = .5) {   // phrase gate with hysteresis; sensitivity 0 = strict, 1 = loose
  const thr = .75 - sens * .5, n = A.phrase.length, mouth = new Float32Array(n); let on = false;
  for (let f = 0; f < n; f++) { on = on ? A.phrase[f] > thr * .75 : A.phrase[f] > thr; mouth[f] = on && A.near[f] ? Math.max(0, (A.lip[f] - .25) / .75) : 0; }
  A.mouth = mouth;
}
