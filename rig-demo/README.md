# Rig Engine (prototype)

A code-driven character animation engine: **every frame is a pure function of `(score, time)`**.

- **Rig**: the character is a set of numbers (`eyeOpen`, `browInner`, `mouthCurve`, `rhY`, …), with no drawings. Because they're numbers, anything can tween into anything.
- **Poses**: named partial parameter sets (`thinking`, `furious`, `laughing`, …).
- **Styles**: renderers that draw the *same* rig geometry differently (`pencil`, `blueprint`, `ink`, `hologram`, `paint`). Swapping a style doesn't touch the animation.
- **Characters**: `fridge` and `corgi`. They read the same params, so every pose and style works on both. Switch with `{ at: [10, 1], character: 'corgi' }`. Characters can also use extra channels (the corgi uses `earL`, `earR`, `tailWag` and `tongue`), which other characters ignore.
- **Score**: events in musical time, `{ at: [bar, beat], pose | style | set | talk }`, compiled to keyframes with an overshoot ease, plus always-on secondary motion (breathing, blinking, 12fps line "boil", lip flap).

## Run it
Open `rig-demo/index.html` in a browser. Edit the score on the left; changes apply live, and the line that's currently playing is highlighted. You can load a song to sync to and record a WebM.

## Frame-exact export
```bash
node rig-demo/render.cjs out.mp4 30 song.mp3
```
This steps time frame by frame in headless Chromium and pipes the frames to ffmpeg, so no frames are dropped. Needs Playwright and ffmpeg.

## Extending
- New expression: add an entry to `POSES`.
- New look: add an entry to `STYLES` (colours, line weight, jitter, passes, glow, fills).
- New character: add a function to `CHARACTERS` that draws with `pen.fill` and `pen.stroke` and reads the shared params. `drawEyes` is reusable.
