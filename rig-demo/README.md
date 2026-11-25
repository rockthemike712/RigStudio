# Rig Engine (prototype)

A code-driven character animation engine: **every frame is a pure function of `(score, time)`**.

- **Rig**: the character is a set of numbers (`eyeOpen`, `browInner`, `mouthCurve`, `rhY`, …), with no drawings. Because they're numbers, anything can tween into anything.
- **Poses**: named partial parameter sets (`thinking`, `furious`, `laughing`, …).
- **Styles**: renderers that draw the *same* rig geometry differently (`lineart`, `pencil`, `blueprint`, `comic`, `riso`, `sticker`, `chalk`, `pixel`, `crayon`, `newsprint`, `cutpaper`, glitch styles `pixelwind`, `pop`, `foil`, `rgb`, `vhs`, `acid`, `static`, `ink`, `hologram`, `paint`). Swapping a style doesn't touch the animation.
- **Catalogue (rebuilt from the reference video)**:
  - **Styles:** 118 styles in 13 categories: House, Drawn, Print and paste, Comics, Spooky, 1980s and 1990s, Cartoon, Pixels, Screens and light, Glitch: signal, Glitch: time, Hologram (8 palettes), and Originals.
  - **Poses:** 64 poses in 6 groups: classic, 14 attitudes, 12 feelings, and eye, mouth and hand poses. Eye, mouth and hand poses (`eyes-suspicious`, `mouth-gasp`, `count3`, `thumbsup`…) layer on top of the current body pose.
  - **Script commands:**
    - `who` / `preset` picks a cast member, Doug's builds: child, girl, teen, boss, clerk, old man, professor, bouncer, dancer.
    - `camera` picks a shot: 1 full, 2 close, 3 medium, 4 handheld.
    - `grid: 3|5|7` shows the same moment in many styles at once.
    - `set: 'body.w', to: 1.05` sets a value by name.
    - `palette` picks a hologram colour.
- **Characters**: `fridge` and `hashbrown` (a red-and-white Pembroke, modelled on his owner's ink drawing; standing 3/4 view). They read the same params, so every pose and style works on both. Switch with `{ at: [10, 1], character: 'hashbrown' }`. Characters can also use extra channels (Hashbrown uses `earL`, `earR`, `tailWag` and `tongue`), which other characters ignore.
- **Score**: events in musical time, `{ at: [bar, beat], pose | style | set | talk }`, compiled to keyframes with an overshoot ease, plus always-on secondary motion (breathing, blinking, 12fps line "boil", lip flap).

## Run it
Open `rig-demo/index.html` in a browser. It has three parts:
- **Stage** (middle): the character, animating.
- **Control deck** (right): Character, Style and Pose tabs with live thumbnails, plus a Design tab of sliders for every rig parameter.
  - **Paused:** clicks and slider moves are previews. Press "Add at bar X, beat Y" to write the preview into the script.
  - **Playing:** every click is recorded into the script on the nearest half-beat, so you can perform along to a song ("Load song").
- **Script** (left): the source of truth. It's editable, changes apply live, and the line currently playing is highlighted.

## Songs
"Load song" decodes the file and analyses it once:
- **Tempo:** the BPM and the first downbeat, so `[bar, beat]` lands on the song's real bars.
- **Envelopes:** separate levels for vocals (300–3400 Hz), bass (under 140 Hz) and overall energy.

With "Listening: on", the character reacts to the song:
- the mouth follows the vocals
- the body squashes, bounces and flicks its ears on every beat
- the tail wags with the song's energy, and the body sways on the beat

"✨ Auto-animate" writes a whole script from the song's structure. It picks calmer styles and poses for quiet sections and glitch styles for big ones, changing on 4-bar boundaries.

**Lip sync** tells words apart from instruments. It doesn't transcribe lyrics. Instead, every 20 ms it measures:
- how centred the sound is (voices sit in the middle of the mix; stereo guitars and hats don't)
- how strongly pitched it is
- how much the pitch glides (voices slide; instruments hold notes)
- how often pitched sound switches on and off (consonants interrupt words)

A section of about 0.8 s is treated as words when there's enough evidence. Within words, the mouth follows each syllable. Vowel colour sets the shape: wide for "ee"/"a", round for "oo"/"o".

The **Lip sync** slider sets how readily sound counts as words. On a test song with spoken words, a centred synth solo, stereo guitars and drums:
- the accuracy score (F1) went from 0.39 to 0.74
- mouth movement during the synth solo went from 84% of the time to 1–2%

What the detector can still mistake for a voice is a centred lead instrument that slides between notes, like a slide guitar or a theremin.

## Frame-exact export
```bash
node rig-demo/render.cjs out.mp4 30 song.mp3 --auto   # --auto: build the script from the song
```
This steps time frame by frame in headless Chromium and pipes the frames to ffmpeg, so no frames are dropped. Needs Playwright and ffmpeg.

## Extending
- New expression: add an entry to `POSES`.
- New look: add an entry to `STYLES`. A style sets:
  - lines: colour, weight, jitter, passes, glow
  - fills per role: flat colour, `grad`, `hatch`, `dots`, `scribble`, `stripes`, `spray`, `foil`, `rainbow` or `noise`
  - optional `bgFx` background and `layers` (printed passes)
  - a `post` effect chain from `FX`: threshold, gradmap, palette, teletext, ascii, pixelsort, datamosh, trails, melt, cubist and more

  Then list it in `STYLE_CATS`.
- **New character from art (recommended)**: an SVG rig. You can load it with "Import SVG character…" in the Character tab, or embed it like `characters/hashbrown.svg`. The format:
  - `viewBox="0 0 1000 1000"`.
  - One `<g id="…" data-pivot="x,y">` per part: `tail`, `body`, `leg-back`, `leg-front-left`, `leg-front-right`, `chest-ruff`, `head`, `ear-left`, `ear-right`, `nose`.
  - Swappable face groups: `eyes-open|happy|closed|wide`, `brows-neutral|angry|worried`, `mouth-smile|grin|flat|frown|o`.
  - Plain `<path>`s only, filled by class (`fur`, `white`, `pink`, `dark`). Unfilled paths are linework.
  The loader samples each path into points, so every style (pencil boil, hologram glow, paint) still applies to the art.
- New character in code: add a function to `CHARACTERS` that draws with `pen.fill` and `pen.stroke` and reads the shared params. `drawEyes` is reusable.
