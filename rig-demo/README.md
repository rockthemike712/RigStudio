# Rig Engine (prototype)

A code-driven character animation engine: **every frame is a pure function of `(score, time)`**.

- **Rig**: the character is a set of numbers (`eyeOpen`, `browInner`, `mouthCurve`, `rhY`, …), with no drawings. Because they're numbers, anything can tween into anything.
- **Poses**: named partial parameter sets (`thinking`, `furious`, `laughing`, …).
- **Styles**: renderers that draw the *same* rig geometry differently (`lineart`, `pencil`, `blueprint`, `comic`, `riso`, `sticker`, `chalk`, `pixel`, `crayon`, `newsprint`, `cutpaper`, `ink`, `hologram`, `paint`). Swapping a style doesn't touch the animation.
- **Characters**: `fridge` and `hashbrown` (a red-and-white Pembroke, modelled on his owner's ink drawing; standing 3/4 view). They read the same params, so every pose and style works on both. Switch with `{ at: [10, 1], character: 'hashbrown' }`. Characters can also use extra channels (Hashbrown uses `earL`, `earR`, `tailWag` and `tongue`), which other characters ignore.
- **Score**: events in musical time, `{ at: [bar, beat], pose | style | set | talk }`, compiled to keyframes with an overshoot ease, plus always-on secondary motion (breathing, blinking, 12fps line "boil", lip flap).

## Run it
Open `rig-demo/index.html` in a browser. It has three parts:
- **Stage** (middle): the character, animating.
- **Control deck** (right): Character, Style and Pose tabs with live thumbnails, plus a Design tab of sliders for every rig parameter.
  - **Paused:** clicks and slider moves are previews. Press "Add at bar X, beat Y" to write the preview into the script.
  - **Playing:** every click is recorded into the script on the nearest half-beat, so you can perform along to a song ("Load song").
- **Script** (left): the source of truth. It's editable, changes apply live, and the line currently playing is highlighted.

## Frame-exact export
```bash
node rig-demo/render.cjs out.mp4 30 song.mp3
```
This steps time frame by frame in headless Chromium and pipes the frames to ffmpeg, so no frames are dropped. Needs Playwright and ffmpeg.

## Extending
- New expression: add an entry to `POSES`.
- New look: add an entry to `STYLES` (colours, line weight, jitter, passes, glow, fills).
- **New character from art (recommended)**: an SVG rig. You can load it with "Import SVG character…" in the Character tab, or embed it like `characters/hashbrown.svg`. The format:
  - `viewBox="0 0 1000 1000"`.
  - One `<g id="…" data-pivot="x,y">` per part: `tail`, `body`, `leg-back`, `leg-front-left`, `leg-front-right`, `chest-ruff`, `head`, `ear-left`, `ear-right`, `nose`.
  - Swappable face groups: `eyes-open|happy|closed|wide`, `brows-neutral|angry|worried`, `mouth-smile|grin|flat|frown|o`.
  - Plain `<path>`s only, filled by class (`fur`, `white`, `pink`, `dark`). Unfilled paths are linework.
  The loader samples each path into points, so every style (pencil boil, hologram glow, paint) still applies to the art.
- New character in code: add a function to `CHARACTERS` that draws with `pen.fill` and `pen.stroke` and reads the shared params. `drawEyes` is reusable.
