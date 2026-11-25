#!/usr/bin/env node
// png-to-room: turn a few layer pictures into a Rig Studio room (a layered SVG for "Import SVG room…").
//
//   node rig-demo/tools/png-to-room.mjs my-room.svg back.png:900 furniture.png:350 rug.png:40 front.png:-250
//
// Each argument is picture:depth. 0 is where the character stands, bigger is further back, negative is in front.
// Pictures should be the same shape as the stage (16:9, e.g. 1920×1080) and drawn as seen with the camera at rest:
// the character stands in the middle with its feet about 84% of the way down. Transparent PNGs work best. For a
// picture with a solid background, the full-frame background shape is dropped; add :keep (wall.png:900:keep) to keep it.
//
// Tracing is done by openvector (https://github.com/Microck/openvector), run through npx, so the first run downloads it.
// Its colours are kept; Rig Studio matches each colour to a style role by how light it is, so every style still applies.
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, basename } from 'node:path';

const [out, ...specs] = process.argv.slice(2);
if (!out || !specs.length || !out.endsWith('.svg')) {
  console.error('usage: png-to-room.mjs out.svg picture.png:depth[:keep] ...\n  e.g. png-to-room.mjs bedroom.svg wall.png:900:keep bed.png:350 rug.png:40 toybox.png:-250');
  process.exit(1);
}
const W = 1920, H = 1080, work = mkdtempSync(join(tmpdir(), 'png-to-room-')), layers = [];
try {
  for (const spec of specs) {
    const m = /^(.*?):(-?\d+(?:\.\d+)?)(:keep)?$/.exec(spec);
    if (!m) throw new Error(`"${spec}" should be picture.png:depth (for example back.png:900)`);
    const [, file, depth, keep] = m; if (!existsSync(file)) throw new Error(`can't find ${file}`);
    const traced = join(work, `layer${layers.length}.svg`);
    process.stdout.write(`tracing ${basename(file)} (depth ${depth})… `);
    const r = spawnSync('npx', ['--yes', 'openvector', 'vectorize', file, '--output', traced, '--force', '--shrink-source'], { encoding: 'utf8', shell: process.platform === 'win32' });
    if (r.status !== 0) throw new Error(`openvector failed on ${file}:\n${r.stderr || r.stdout}`);
    const svg = readFileSync(traced, 'utf8'), vb = (/viewBox="([^"]+)"/.exec(svg) || [])[1];
    const [vx, vy, vw, vh] = vb ? vb.trim().split(/[\s,]+/).map(Number) : [0, 0, W, H];
    let paths = [...svg.matchAll(/<path\b[^>]*\/>/g)].map(q => q[0]);
    if (!keep) paths = paths.filter(p => {   // drop a solid background: a shape covering (almost) the whole picture
      const nums = ((/\sd="([^"]*)"/.exec(p) || [])[1] || '').match(/-?\d+(?:\.\d+)?/g) || [];
      let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
      for (let i = 0; i + 1 < nums.length; i += 2) { const x = +nums[i], y = +nums[i + 1]; x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
      return !(x1 - x0 >= vw * .97 && y1 - y0 >= vh * .97);
    });
    // fit the picture to the 1920×1080 stage, centred, like the stage itself does
    const s = Math.min(W / vw, H / vh), tx = (W - vw * s) / 2 - vx * s, ty = (H - vh * s) / 2 - vy * s;
    layers.push({ depth: +depth, name: basename(file), body: paths.map(p => p.replace(/\sopacity="[^"]*"/, '')).join('\n      '), tf: `translate(${+tx.toFixed(2)} ${+ty.toFixed(2)}) scale(${+s.toFixed(5)})`, n: paths.length });
    console.log(`${paths.length} shapes`);
  }
  layers.sort((a, b) => b.depth - a.depth);
  writeFileSync(out, `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}">
  <!-- made by png-to-room from ${layers.map(l => `${l.name} (${l.depth})`).join(', ')}. Load it with "Import SVG room…" in the Room tab. -->
${layers.map(l => `  <g data-depth="${l.depth}">
    <g transform="${l.tf}">
      ${l.body}
    </g>
  </g>`).join('\n')}
</svg>
`);
  console.log(`wrote ${out}: ${layers.length} layers, ${layers.reduce((a, l) => a + l.n, 0)} shapes`);
} catch (e) { console.error(e.message); process.exitCode = 1; }
finally { rmSync(work, { recursive: true, force: true }); }
