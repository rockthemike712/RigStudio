import numpy as np, json, sys
sys.path.insert(0, '.'); import train as T
names = 'oddity broadcast roses doitto recordplayer kicks9d beggin buryafriend fiddle onelast'.split()
data = {n: T.load(n) for n in names}
def dump(M, path): json.dump({'mu': np.round(M['mu'], 5).tolist(), 'sd': np.round(M['sd'], 5).tolist(), 'W1': np.round(M['W1'], 5).ravel().tolist(), 'b1': np.round(M['b1'], 5).tolist(), 'W2': np.round(M['W2'], 5).tolist(), 'b2': round(M['b2'], 5)}, open(path, 'w'))
for n in names: dump(T.train([data[k][0] for k in names if k != n], [data[k][1] for k in names if k != n]), f'sep/model.without-{n}.json')
dump(T.train([d[0] for d in data.values()], [d[1] for d in data.values()]), 'sep/model.json'); print('ok')
