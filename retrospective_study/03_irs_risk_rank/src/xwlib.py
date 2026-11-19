# -*- coding: utf-8 -*-
"""IRS model-version crosswalk library (v2, after Codex review 2026-11-19).
Times are KST-naive (source create_date offsets are all +09)."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import GroupKFold

B0 = pd.Timestamp('2026-07-01 10:00')   # model switch (old model before, July model from)
TS = pd.Timestamp('2026-07-01 15:00')   # end of the 7/1 batch; reference table starts here
B1 = pd.Timestamp('2026-08-02')         # next model change
SC = ['irs', 'mrs', 'lrs', 'prs']
SCALE = {'irs': 'logit', 'mrs': 'logit', 'lrs': 'raw', 'prs': 'raw'}   # LRS/PRS are not probabilities (values <0 and >1 occur)
SEXES = ['F', 'M']

def load():
    import os
    R = pd.concat([pd.read_csv(f, dtype=str) for f in ['res_b.csv', 'res_p1.csv', 'res_miss.csv', 'res_ob.csv'] if os.path.exists(f)]).drop_duplicates(['seq', 'disease'])
    R['seq'] = R.seq.astype(int)
    for c in SC:
        R[c + '_pn'] = pd.to_numeric(R[c + '_p'], errors='coerce'); R[c + '_rn'] = pd.to_numeric(R[c + '_r'], errors='coerce')
    I = pd.read_pickle('I_final.pkl'); D = pd.read_pickle('D_final.pkl'); BB = pd.read_pickle('BB_final.pkl').reset_index(drop=True)
    tmap = I.set_index('seq').t; R['t'] = R.seq.map(tmap); R['user_id'] = R.seq.map(I.set_index('seq').user_id)
    return R, I, D, BB

def build_ref(R, exclude_users=None):
    T = R[(R.t >= TS) & (R.t < B1)]
    if exclude_users is not None: T = T[~T.user_id.isin(exclude_users)]
    ref = {}
    for (d, s), g in T.groupby(['disease', 'sex']):
        for c in SC:
            t = g[g[c + '_pn'].notna() & g[c + '_rn'].notna()][[c + '_pn', c + '_rn']].sort_values([c + '_pn', c + '_rn'])
            if len(t): ref[(d, s, c)] = (t[c + '_pn'].values, t[c + '_rn'].values)
    return ref

def round_half_up(x): return np.floor(np.asarray(x, float) + 0.5)

def to_rank(ref, p, d, s, c, detail=False):
    """Rank from the July reference table. Inside an observed rank interval -> that rank exactly.
    In a gap between two observed ranks -> linear interpolation, rounded half-up.
    Outside the observed range -> the end rank (np.interp holds the ends)."""
    p = np.asarray(p, float); out = np.full(len(p), np.nan); loc = np.full(len(p), '', dtype=object)
    lo_r = np.full(len(p), np.nan); hi_r = np.full(len(p), np.nan)
    if (d, s, c) not in ref:
        return (out, loc, lo_r, hi_r) if detail else out
    x, y = ref[(d, s, c)]; ok = np.isfinite(p)
    out[ok] = np.clip(round_half_up(np.interp(p[ok], x, y)), 1, 100)
    if detail:
        i_hi = np.searchsorted(x, p[ok], side='left'); i_lo = np.searchsorted(x, p[ok], side='right') - 1
        below = i_lo < 0; above = i_hi >= len(x)
        rl = np.where(below, np.nan, y[np.clip(i_lo, 0, len(x) - 1)]); rh = np.where(above, np.nan, y[np.clip(i_hi, 0, len(x) - 1)])
        l = np.where(below | above, '범위 밖', np.where(rl == rh, '관측 구간 안', '순위 사이 빈 구간'))
        loc[ok] = l; lo_r[ok] = np.where(below, 1, rl); hi_r[ok] = np.where(above, 100, rh)
        return out, loc, lo_r, hi_r
    return out

lg = lambda p: np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))
ilg = lambda z: 1 / (1 + np.exp(-z))

class CW:
    """Monotone crosswalk old-model value -> July-model value for one disease x score x sex.
    identity   : all bridge pairs have identical values (only the rank table changed)
    isotonic   : >=5 pairs; isotonic regression on the logit (IRS/MRS) or raw (LRS/PRS) scale,
                 linear between knots, constant shift beyond the bridge range (extrap='shift') or end value (extrap='clip')
    none       : <5 pairs -> not validated, returns NaN"""
    def __init__(s, xo, xn, scale='logit', extrap='shift'):
        xo = np.asarray(xo, float); xn = np.asarray(xn, float); k = np.isfinite(xo) & np.isfinite(xn); xo, xn = xo[k], xn[k]
        s.scale, s.extrap, s.n = scale, extrap, len(xo)
        s.f = (lg, ilg) if scale == 'logit' else (lambda v: v, lambda v: v)
        if len(xo) >= 1 and np.allclose(xo, xn, atol=1e-12, rtol=0): s.kind = 'identity'
        elif len(xo) >= 5: s.kind = 'isotonic'
        else: s.kind = 'none'
        s.lo = s.hi = np.nan
        if len(xo): s.lo, s.hi = xo.min(), xo.max()
        if s.kind == 'isotonic':
            a, b = s.f[0](xo), s.f[0](xn); s.iso = IsotonicRegression(out_of_bounds='clip').fit(a, b)
            s.za, s.zb = a.min(), a.max(); s.fa, s.fb = s.iso.predict([s.za])[0], s.iso.predict([s.zb])[0]
            s.x, s.y = s.iso.X_thresholds_, s.iso.y_thresholds_
    label = property(lambda s: {'identity': '값 동일(순위표만 적용)', 'isotonic': '등위회귀 환산', 'none': '연결 쌍 부족(환산 안 함)'}[s.kind])
    def outside(s, p):
        p = np.asarray(p, float); return np.isfinite(p) & ((p < s.lo) | (p > s.hi))
    def __call__(s, p):
        p = np.asarray(p, float); out = np.full(len(p), np.nan); ok = np.isfinite(p)
        if not ok.any() or s.kind == 'none': return out          # empty or all-missing input
        if s.kind == 'identity': out[ok] = p[ok]; return out
        z = s.f[0](p[ok]); y = s.iso.predict(np.clip(z, s.za, s.zb))
        if s.extrap == 'shift': y = np.where(z < s.za, s.fa + (z - s.za), np.where(z > s.zb, s.fb + (z - s.zb), y))
        out[ok] = s.f[1](y); return out

def band(r, width=20, shift=0): return np.floor((np.asarray(r, float) - 1 + shift) / width)

_BV = {}
def bridge_values(R, BB, d, c):
    key = (id(R), id(BB), d, c)
    if key in _BV: return _BV[key]
    Rk = R[R.disease == d].set_index('seq')
    o = Rk.reindex(BB.seq_o); n = Rk.reindex(BB.seq_n)
    m = o[c + '_pn'].notna().values & n[c + '_pn'].notna().values & o[c + '_rn'].notna().values & n[c + '_rn'].notna().values  # positional, not index-aligned
    _BV[key] = (o[c + '_pn'].values, n[c + '_pn'].values, o[c + '_rn'].values, m)
    return _BV[key]

def folds(BB):
    """global 5-fold assignment of bridge users (sorted user ids -> GroupKFold); shared by cross-fitting and validation"""
    gid = {u: i for i, u in enumerate(sorted(BB.user_id.unique()))}; g = BB.user_id.map(gid).values
    F = np.full(len(BB), -1)
    for k, (tr, te) in enumerate(GroupKFold(5).split(BB, groups=g)): F[te] = k
    return F, g

def rank_conflicts(ref):
    """number of identical values carrying different ranks within a reference table"""
    n = 0
    for (d, s, c), (x, y) in ref.items():
        t = pd.DataFrame({'x': x, 'y': y}).groupby('x').y.nunique(); n += int((t > 1).sum())
    return n
