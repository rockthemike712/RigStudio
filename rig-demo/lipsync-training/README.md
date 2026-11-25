# Lip-sync model training

The studio's singing detector (`VOCAL_MODEL` in `../index.html`) is a small neural network: 42 inputs, 24 hidden units, 1 output. It's trained on songs where the true "someone is singing" timeline comes from separating the vocals with [Demucs](https://github.com/facebookresearch/demucs).

The songs themselves aren't in the repo. Put MP3s in `sep/` as `<name>.mp3`.

## Steps
1. Separate the vocals:
   ```bash
   python -m demucs --two-stems=vocals -n htdemucs -o sep/out sep/*.mp3
   ```
2. Build the reference timelines (`sep/<name>.truth.json`):
   ```bash
   python mktruth.py name1 name2 ...
   ```
   A frame counts as singing when the vocal stem is within 30 dB of its peak and within 14 dB of the accompaniment. Add instrumental tracks whose lead Demucs mistakes for a voice (fiddles, saxes) to `INSTRUMENTAL`.
3. Export features. This runs `vocal-features.js` in Chromium, the same code the studio uses:
   ```bash
   node featdump.cjs "$PWD" name1 name2 ...
   ```
4. Train with leave-one-song-out scores:
   ```bash
   python train.py name1 name2 ...
   ```
   This writes `sep/model.json`; paste it into `var VOCAL_MODEL = …` in `../index.html`.
5. Optionally, get a fair score in the real page. Train held-out models with `loo_models.py`, then:
   ```bash
   node sweep.cjs <page> "$PWD" .5
   ```

## Results
These are from the first training run: 10 songs, each song scored by a model that never saw it.

| | Old loudness trigger | Hand-tuned detector | This model |
|---|---|---|---|
| Mouth moving during instrumental stretches | 23% | 37% | **20%** |
| Accuracy against the singing timeline (F1), 9 vocal songs | 0.67 | 0.66 | 0.64 |
| … excluding the whispered *Bury a Friend* | 0.66 | 0.67 | **0.70** |

**Known gaps:**
- whispered vocals, if no similar song is in the training set
- the rotating "9D" mixes, which defeat the centre-panning cue
- fiddle-like lead instruments

More (and more varied) training songs is the main lever.
