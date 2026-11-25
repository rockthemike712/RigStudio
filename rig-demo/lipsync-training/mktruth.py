import numpy as np, wave, json, sys
def read(p):
    import soundfile as sf; x, sr = sf.read(p); return (x.mean(1) if x.ndim > 1 else x), sr
INSTRUMENTAL = {'fiddle'}   # instrumental beat: Demucs files the fiddle under 'vocals'
for name in sys.argv[1:]:
    v, sr = read(f'sep/out/htdemucs/{name}/vocals.wav'); hop = sr // 100; n = len(v) // hop
    rms = np.array([np.sqrt((v[i*hop:(i+2)*hop]**2).mean() + 1e-12) for i in range(n)]); db = 20*np.log10(rms)
    a, _ = read(f'sep/out/htdemucs/{name}/no_vocals.wav')
    arms = np.array([np.sqrt((a[i*hop:(i+2)*hop]**2).mean() + 1e-12) for i in range(n)]); adb = 20*np.log10(arms)
    truth = ((db > np.percentile(db, 99) - 30) & (db > adb - 14)).astype(int)    # loud enough, and a real part of the mix
    if name in INSTRUMENTAL: truth[:] = 0
    # close tiny gaps (<80 ms) and drop blips (<60 ms) so it reflects sung phrases at syllable level
    t = truth.copy()
    for i in range(1, n-8):
        if t[i-1] and not t[i] and t[i:i+8].any(): t[i] = 1
    json.dump(t.tolist(), open(f'sep/{name}.truth.json', 'w'))
    # summary of vocal structure: seconds with vocals per 15 s
    per = [round(t[k*1500:(k+1)*1500].mean(), 2) for k in range(n // 1500 + 1)]
    print(name, f'{t.mean()*100:.0f}% vocal frames', 'per-15s:', per)
