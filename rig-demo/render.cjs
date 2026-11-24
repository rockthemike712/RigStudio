// Offline, frame-exact render of rig-demo/index.html to MP4 (no screen recording, no dropped frames).
// Usage: node rig-demo/render.cjs out.mp4 [fps=30] [song.mp3]
// Needs Playwright (Chromium) and ffmpeg on PATH.
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

(async () => {
  const [out = 'rig.mp4', fps = '30', song] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.join(__dirname, 'index.html'));
  const duration = await page.evaluate(() => window.RIG.duration());
  const frames = Math.ceil(duration * fps);

  const args = ['-y', '-f', 'image2pipe', '-framerate', fps, '-i', '-'];
  if (song) args.push('-i', song, '-shortest', '-c:a', 'aac');
  args.push('-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', out);
  const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'inherit', 'inherit'] });

  for (let f = 0; f < frames; f++) {
    const b64 = await page.evaluate(t => { window.RIG.renderAt(t); return window.RIG.canvas.toDataURL('image/png').split(',')[1]; }, f / fps);
    if (!ff.stdin.write(Buffer.from(b64, 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
    if (f % fps === 0) process.stdout.write(`\rframe ${f}/${frames}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  console.log(`\nwrote ${out} (${duration.toFixed(1)}s @ ${fps}fps)`);
})();
