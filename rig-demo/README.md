# Rig Engine (prototype)

A code-driven character animation engine: **every frame is a pure function of `(score, time)`**.

- **Rig**: the character is a set of numbers (`eyeOpen`, `browInner`, `mouthCurve`, `rhY`, …), with no drawings. Because they're numbers, anything can tween into anything.
- **Poses**: named partial parameter sets (`thinking`, `furious`, `laughing`, …).
- **Styles**: renderers that draw the *same* rig geometry differently (`lineart`, `pencil`, `blueprint`, `comic`, `riso`, `sticker`, `chalk`, `pixel`, `crayon`, `newsprint`, `cutpaper`, glitch styles `pixelwind`, `pop`, `foil`, `rgb`, `vhs`, `acid`, `static`, `ink`, `hologram`, `paint`). Swapping a style doesn't touch the animation.
- **Catalogue (rebuilt from the reference video)**:
  - **Styles:** 118 styles in 13 categories: House, Drawn, Print and paste, Comics, Spooky, 1980s and 1990s, Cartoon, Pixels, Screens and light, Glitch: signal, Glitch: time, Hologram (8 palettes), and Originals.
  - **Poses:** 64 poses in 6 groups: classic, 14 attitudes, 12 feelings, and eye, mouth and hand poses. Eye, mouth and hand poses (`eyes-suspicious`, `mouth-gasp`, `count3`, `thumbsup`…) layer on top of the current body pose.
  - **Script commands:**
    - `who` / `preset` picks a cast member. Doug's cast: child, girl, teen, boss, clerk, old man, professor, bouncer, dancer. Hashbrown's builds: `hashbrown-puppy`, `-chonk`, `-lanky`, `-grandpa`.
    - `camera` picks a shot: 1 full, 2 close, 3 medium, 4 handheld.
    - `grid: 3|5|7` shows the same moment in many styles at once.
    - `set: 'body.w', to: 1.05` sets a value by name.
    - `palette` picks a hologram colour.
- **Doug is a 3D box.** Every build and pose is drawn from these controls:
  - width, height and depth
  - door-seam height
  - camera turn (`yaw`) and how far it's seen from above (`pitch`)
  - lean and twist
  - eye style: oval, round, lashes or heavy-lidded
  - head and hand size

  The face sits on the front panel in perspective. Cast members are builds of him, modelled on the reference video. Hashbrown maps the same controls onto his 2D drawing:
  - build and lean
  - turn, which squeezes the drawing and mirrors it past front-on
  - head and paw size
  - all four eye styles

  The controls are in the Design tab, under Build, View & posture and Eye style.
- **Characters**: `fridge` and `hashbrown` (a red-and-white Pembroke, modelled on his owner's ink drawing; standing 3/4 view). They read the same params, so every pose and style works on both. Switch with `{ at: [10, 1], character: 'hashbrown' }`. Characters can also use extra channels (Hashbrown uses `earL`, `earR`, `tailWag` and `tongue`), which other characters ignore.
- **Rooms and the 2.5D camera.** A `room` track changes on its own, like style: `{ at: [9, 1], room: 'kitchen' }`.
  - Rooms: `kitchen`, `living`, `stage`, `street`, `park`, `space`, and `none` (the style's own background).
  - Each room is a paper diorama: floor and walls in real perspective, 3D boxes for furniture and buildings, and flat cut-outs standing at different depths. It's drawn with the style's own pen, so every room works in every style. Room surfaces use each style's flat colours rather than its full texture (crayon scribble over a whole wall costs ~100 ms a frame), and far layers are veiled so the character stays in front.
  - Camera moves: `move: 'push' | 'pull' | 'pan' | 'orbit' | 'drift' | 'sweep' | 'still'` (or `camera: 'orbit'`). A move runs over two bars and eases in from the last one. Near layers slide further than far ones, boxes show their sides, and orbiting turns Doug for real (Hashbrown, a flat drawing, turns a little). Push-ins on top of close-ups are capped so the camera never ends up inside the character.
  - The camera is also rig values: `dolly`, `pan`, `orbit` and `dof` (depth blur) in Design → Camera, so `set` works on them too.
  - **Depth of field:** the far layers and the things in front of the character are softly out of focus. Each blurred layer is drawn at half size and only the area it covers is scaled, so the kitchen costs about 2 ms more and the park, whose far layer spans the frame, about 12 ms (in a software-rendered test browser). `set: { dof: 0 }` turns it off.
  - **Things in front:** each room has a prop between the camera and the character, at the edge of the frame: a kitchen chair, an armchair, the crowd's heads at the stage, a bin, a bush, a moon rock. They slide past fastest when the camera moves.
  - **Lighting:** `light: 'auto' | 'day' | 'sunset' | 'night' | 'stage' | 'neon' | 'none'` is its own track. It falls on the room and the character together. `auto` (the default) uses the room's own light: daylight in the kitchen and living room, a spotlight on stage, night on the street and in space, sunset in the park. Dark-background styles get a lighter touch.
  - Room tab: tap a room or a move to preview it, then Add. Auto-animate gives the star a home room (kitchen for Doug's family, living room for Hashbrown's), moves somewhere else for big sections, and picks a shot and a move per section. Untick "Rooms" to keep the style backgrounds.
- **Score**: events in musical time, `{ at: [bar, beat], pose | style | set | talk }`, compiled to keyframes with an overshoot ease, plus always-on secondary motion (breathing, blinking, 12fps line "boil", lip flap).

## Run it
Open `rig-demo/index.html` in a browser. It has three parts:
- **Stage** (middle): the character, animating.
- **Control deck** (right): Character, Style, Pose and Room tabs with live thumbnails, plus a Design tab of sliders for every rig parameter.
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

**One character per song (default).** With "One character for the whole song" ticked (Character tab), tapping a character makes it the star of the whole song, and character switches in any script are ignored. Untick it for multi-character videos, where the script's `who` / `character` switches apply.

Loading a song **animates it automatically**: no script needed, just press Play. Auto-animate reads the song's sections, loudness and where the vocals are:
- vocals get talk-to-camera poses and medium or close shots
- instrumentals get dancing poses and wide shots
- big sections get handheld shots and wilder styles

Options next to the button:
- **Styles:** follow the song, keep current, calm or wild.
- **Camera moves:** on or off.

Each press of ✨ is a new take. A script you've written yourself is never replaced on load.

**Lip sync** uses a small singing detector trained on real songs; see `lipsync-training/`. For every 20 ms of audio it looks at:
- tone colour (MFCCs)
- how centred the sound is in the stereo mix
- pitch strength and pitch
- spectral shape and sibilance
- how all of those vary over the surrounding half second

Within sung phrases, the mouth follows each syllable. Vowel colour sets the shape: wide for "ee"/"a", round for "oo"/"o". The **Lip sync** slider trades catching quiet vocals against staying shut during instrumentals.

Scored on 10 songs, each by a model trained without that song, the mouth moved during instrumental stretches 20% of the time. The previous versions scored 23% and 37%. Known gaps:
- whispered vocals
- rotating "9D" mixes
- fiddle-like lead instruments

## Frame-exact export
```bash
node rig-demo/render.cjs out.mp4 30 song.mp3 --auto   # --auto: build the script from the song
```
This steps time frame by frame in headless Chromium and pipes the frames to ffmpeg, so no frames are dropped. Needs Playwright and ffmpeg.

## Extending
- New expression: add an entry to `POSES`.
- **Your own room from art:** "Import SVG room…" in the Room tab, or see `rooms/bedroom.svg`. The format:
  - `viewBox="0 0 1920 1080"`, drawn as seen with the camera at rest.
  - One `<g data-depth="…">` per paper layer: `0` is where the character stands, bigger numbers are further back (a back wall is around 900, a skyline 2000+), negative numbers are in front of the character (around -250).
  - The character stands in the middle with its feet at y ≈ 905. Keep x 700–1220, y 250–905 clear, except for low things on the floor.
  - Fills by class follow the style: `fur`, `white`, `pink`, `dark`, `side`. Plain colours also work: dark ones become `dark`, colourful ones the accents (`fur` if warm, otherwise `pink`), and the rest `side` or `white` by lightness. Shapes with no fill are line work.
  - A prompt for an image AI: *"Write an SVG (viewBox 0 0 1920 1080) of a [cosy bedroom], flat cartoon style, plain shapes only (rect, circle, ellipse, polygon, path), no gradients, text or images. Split it into layers as `<g data-depth="N">`: the back wall at 900, furniture at 300–500, a rug on the floor at 40, and one prop poking in from a corner at -250. Leave the middle (x 700–1220, y 250–905) empty for a character who stands with feet at y 905. Give each filled shape class="white", "side", "fur", "pink" or "dark"."*
- **A room from pictures:** `tools/png-to-room.mjs` turns a few layer images into a room SVG, so an image AI only has to draw pictures, not write SVG code. It traces each one with [openvector](https://github.com/Microck/openvector) (fetched on first use through `npx`; needs Node 22.19+):

  ```sh
  node rig-demo/tools/png-to-room.mjs my-room.svg wall.png:900:keep bed.png:350 rug.png:40 toybox.png:-250
  ```

  - Each argument is `picture:depth`, with depths as above. Draw every picture as the whole 16:9 frame seen with the camera at rest, with only that layer's things in it; transparent PNGs work best.
  - A solid background is dropped automatically; `:keep` keeps it (for the back wall).
  - Traced colours are kept. On import, dark shapes become `dark`, colourful ones the style's accents (warm → `fur`, others → `pink`), and the rest `side` or `white` by lightness. So every style still applies.
  - Each picture takes about 8 seconds to trace. Then load the SVG with "Import SVG room…".
- New room in code: add a function to `ROOMS` and list it in `ROOM_LIST`. It gets a helper `R` with `walls`, `plane`, `tint`, `line`, `rect`, `box` (real 3D, back faces culled) and `card` (a cut-out at a depth). Units match the character; `y` is up from the floor (negative), `z` is depth away from the camera.
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
