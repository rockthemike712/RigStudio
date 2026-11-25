import numpy as np, json, sys, os
D_ = os.path.dirname(os.path.abspath(__file__)) + '/sep/'
def load(name):
    meta = json.load(open(D_ + name + '.feat.json')); Z = np.fromfile(D_ + name + '.feat.bin', dtype=np.float32).reshape(meta['fr'], meta['D'])
    truth = np.array(json.load(open(D_ + name + '.truth.json'))); t = np.arange(meta['fr']) * 441 / 22050 + 512 / 22050
    y = truth[np.clip(np.round(t * 100).astype(int), 0, len(truth) - 1)]
    return np.nan_to_num(Z.astype(np.float64)), y.astype(np.float64)

def train(Xs, ys, H=24, epochs=25, seed=0, l2=1e-4):
    X = np.concatenate(Xs); y = np.concatenate(ys); mu = X.mean(0); sd = X.std(0) + 1e-6; Xn = (X - mu) / sd
    w_pos = .5 / max(y.mean(), 1e-3); w_neg = .5 / max(1 - y.mean(), 1e-3)   # balance classes
    rng = np.random.default_rng(seed); D = X.shape[1]
    W1 = rng.normal(0, np.sqrt(2 / D), (H, D)); b1 = np.zeros(H); W2 = rng.normal(0, np.sqrt(1 / H), H); b2 = 0.0
    P = [W1, b1, W2, np.array([b2])]; m = [np.zeros_like(p) for p in P]; v = [np.zeros_like(p) for p in P]; lr, t = 3e-3, 0
    for ep in range(epochs):
        idx = rng.permutation(len(Xn))
        for s in range(0, len(idx), 512):
            bi = idx[s:s + 512]; xb = Xn[bi]; yb = y[bi]; wb = np.where(yb > .5, w_pos, w_neg)
            a = xb @ P[0].T + P[1]; h = np.maximum(a, 0); z = h @ P[2] + P[3][0]; p = 1 / (1 + np.exp(-z))
            g = (p - yb) * wb / len(bi); gW2 = h.T @ g + l2 * P[2]; gb2 = np.array([g.sum()]); gh = np.outer(g, P[2]) * (a > 0)
            gW1 = gh.T @ xb + l2 * P[0]; gb1 = gh.sum(0); grads = [gW1, gb1, gW2, gb2]; t += 1
            for i in range(4):
                m[i] = .9 * m[i] + .1 * grads[i]; v[i] = .999 * v[i] + .001 * grads[i] ** 2
                P[i] -= lr * (m[i] / (1 - .9 ** t)) / (np.sqrt(v[i] / (1 - .999 ** t)) + 1e-8)
        lr *= .9
    return dict(mu=mu, sd=sd, W1=P[0], b1=P[1], W2=P[2], b2=float(P[3][0]))

def predict(M, X):
    h = np.maximum(((X - M['mu']) / M['sd']) @ M['W1'].T + M['b1'], 0); return 1 / (1 + np.exp(-(h @ M['W2'] + M['b2'])))

def gate(p, thr=.5):
    ph = np.convolve(p, np.ones(15) / 15, 'same'); g = np.zeros(len(p), bool); on = False
    for i in range(len(p)): on = ph[i] > thr * .75 if on else ph[i] > thr; g[i] = on
    return g

def score(g, y):
    tp = (g & (y > .5)).sum(); fp = (g & (y < .5)).sum(); fn = (~g & (y > .5)).sum(); P = tp / max(1, tp + fp); R = tp / max(1, tp + fn)
    inst = np.zeros(len(y), bool); i = 0
    while i < len(y):
        if y[i] > .5: i += 1; continue
        j = i
        while j < len(y) and y[j] < .5: j += 1
        if j - i >= 100: inst[i:j] = True    # ≥ 2 s without vocals (50 fps)
        i = j
    return dict(P=round(P, 2), R=round(R, 2), F1=round(2 * P * R / max(1e-9, P + R), 2), instOpen=round(g[inst].mean(), 2) if inst.any() else None)

if __name__ == '__main__':
    names = sys.argv[1:]; data = {n: load(n) for n in names}
    print('leave-one-song-out (song never seen in training):')
    for n in names:
        M = train([data[k][0] for k in names if k != n], [data[k][1] for k in names if k != n]); print(f'  {n:14s}', score(gate(predict(M, data[n][0])), data[n][1]))
    M = train([d[0] for d in data.values()], [d[1] for d in data.values()])
    json.dump({k: (np.round(v, 5).tolist() if isinstance(v, np.ndarray) else round(v, 5)) for k, v in M.items()} | {'W1': np.round(M['W1'], 5).ravel().tolist()}, open(D_ + 'model.json', 'w'))
    print('final model trained on all', len(names), 'songs → sep/model.json')
