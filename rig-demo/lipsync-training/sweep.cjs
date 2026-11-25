// one browser, many songs: score lip sync for several sensitivities with held-out models
const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const [page, dir, ...sensList] = process.argv.slice(2), songs = 'oddity broadcast roses doitto recordplayer kicks9d beggin buryafriend fiddle onelast'.split(' ');
  const b = await chromium.launch(); const res = {};
  for (const n of songs) {
    const p = await b.newPage(); await p.goto('file://' + page); await p.waitForTimeout(200);
    await p.evaluate(m => { VOCAL_MODEL = m; }, JSON.parse(fs.readFileSync(`${dir}/sep/model.without-${n}.json`)));
    const [fc] = await Promise.all([p.waitForEvent('filechooser'), p.click('#loadSong')]); await fc.setFiles(`${dir}/sep/${n}.mp3`);
    await p.waitForFunction(() => window.RIG.hasSong(), null, { timeout: 300000 });
    const truth = JSON.parse(fs.readFileSync(`${dir}/sep/${n}.truth.json`));
    for (const s of sensList) {
      const open = await p.evaluate(([n, s]) => { buildMouth(song.an, +s); const o = []; for (let i = 0; i < n; i++) o.push(react({ ...BASE, mouthOpen: 0 }, i / 100 + .005).mouthOpen > 3 ? 1 : 0); return o; }, [truth.length, s]);
      let tp = 0, fp = 0, fn = 0; open.forEach((o, i) => { const v = truth[i]; if (o && v) tp++; else if (o && !v) fp++; else if (!o && v) fn++; });
      let inst = 0, io = 0; for (let i = 0; i < truth.length;) { if (truth[i]) { i++; continue; } let j = i; while (j < truth.length && !truth[j]) j++; if (j - i >= 200) for (let k = i; k < j; k++) { inst++; io += open[k]; } i = j; }
      const P = tp / (tp + fp || 1), R = tp / (tp + fn || 1); (res[s] = res[s] || {})[n] = { F1: 2 * P * R / (P + R || 1), io: io / inst };
    }
    await p.close();
  }
  for (const s of sensList) { const r = res[s], ks = Object.keys(r); const f1 = ks.filter(k => k !== 'fiddle').reduce((a, k) => a + r[k].F1, 0) / 9, io = ks.reduce((a, k) => a + r[k].io, 0) / ks.length;
    console.log(`sens ${s}: mean F1 ${f1.toFixed(2)}  open-in-instrumentals ${io.toFixed(2)}  bury ${r.buryafriend.F1.toFixed(2)}  oddity ${r.oddity.F1.toFixed(2)}/${r.oddity.io.toFixed(2)}`); }
  await b.close();
})();
