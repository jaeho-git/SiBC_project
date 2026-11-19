# age-adjusted crosswalk alternative (nested within the same global folds) - v2 library
from xwlib import *
import json
R, I, D, BB = load(); REF = pd.read_pickle('REF.pkl'); DIS = pd.read_pickle('DIS.pkl')
imode = I.set_index('seq')['mode'].astype(str); BB['mode_o'] = BB.seq_o.map(imode)
FOLD = np.full(len(BB), -1)
gid = {u: i for i, u in enumerate(sorted(BB.user_id.unique()))}; BB['g'] = BB.user_id.map(gid)
for k, (tr, te) in enumerate(GroupKFold(5).split(BB, groups=BB.g)): FOLD[te] = k
age = pd.to_numeric(BB.age_o, errors='coerce').values
res = []
for d in DIS:
    for c in ['irs', 'mrs']:
        xo, xn, ro, m = bridge_values(R, BB, d, c)
        if c == 'irs': m = m & BB.mode_o.isin({'1', '4'}).values
        idx = np.where(m)[0]
        if len(idx) < 30: continue
        sx = BB.sex_o.values[idx]; fo = FOLD[idx]; truth = np.full(len(idx), np.nan); p0 = truth.copy(); p1 = truth.copy()
        for s in SEXES:
            k = sx == s
            if k.any(): truth[k] = to_rank(REF, xn[idx[k]], d, s, c)
        for f in range(5):
            for s in SEXES:
                tr = np.where((fo != f) & (sx == s))[0]; te = np.where((fo == f) & (sx == s))[0]
                if not len(te): continue
                cw = CW(xo[idx[tr]], xn[idx[tr]], SCALE[c]); p0[te] = to_rank(REF, cw(xo[idx[te]]), d, s, c)
                if cw.kind == 'isotonic' and len(tr) >= 10:
                    resid = lg(xn[idx[tr]]) - lg(cw(xo[idx[tr]])); a = age[idx[tr]]; mu = np.nanmean(a); A = a - mu
                    b = np.nansum(A * resid) / np.nansum(A * A) if np.nansum(A * A) > 0 else 0
                    p1[te] = to_rank(REF, ilg(lg(cw(xo[idx[te]])) + b * (age[idx[te]] - mu)), d, s, c)
                else: p1[te] = p0[te]
        ok = np.isfinite(truth) & np.isfinite(p0)
        res.append(dict(disease=d, score=c, base=(band(truth[ok]) == band(p0[ok])).mean(), age=(band(truth[ok]) == band(p1[ok])).mean()))
X = pd.DataFrame(res); X['gain'] = X.age - X.base
out = {c: dict(base=float(X[X.score == c].base.median()), age=float(X[X.score == c].age.median()), better=int((X[(X.score == c)].gain > 0.005).sum()), worse=int((X[(X.score == c)].gain < -0.005).sum())) for c in ['irs', 'mrs']}
json.dump(out, open('x8c.json', 'w')); print(out)
