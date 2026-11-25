const { chromium } = require('playwright'); const fs = require('fs');
(async () => { const b = await chromium.launch(); const p = await b.newPage(); const dir = process.argv[2];
  await p.goto('file://' + dir + '/feat.html');
  for (const name of process.argv.slice(3)) {
    await p.setInputFiles('#f', `${dir}/sep/${name}.mp3`);
    const r = await p.evaluate(async () => { const ac = new OfflineAudioContext(2, 1, 44100), buf = await ac.decodeAudioData(await document.getElementById('f').files[0].arrayBuffer());
      const V = await vocalFeatures(buf), { Z, D } = contextFeatures(V); const u8 = new Uint8Array(Z.buffer); let s = ''; for (let i = 0; i < u8.length; i += 32768) s += String.fromCharCode.apply(null, u8.subarray(i, i + 32768)); return { fr: V.fr, D, b64: btoa(s) }; });
    fs.writeFileSync(`${dir}/sep/${name}.feat.bin`, Buffer.from(r.b64, 'base64')); fs.writeFileSync(`${dir}/sep/${name}.feat.json`, JSON.stringify({ fr: r.fr, D: r.D })); console.log(name, r.fr, 'frames ×', r.D);
  } await b.close(); })();
