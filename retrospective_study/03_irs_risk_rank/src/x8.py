# -*- coding: utf-8 -*-
"""v3 conversion: reference table, crosswalk with 5-fold cross-fitting (same folds as validation), row diagnostics from the
function actually applied, cross-fitted alternatives, bootstrap of the function estimate with the same cross-fitting rule."""
from xwlib import *
import json
R, I, D, BB = load()
U = pd.read_csv('users.csv'); bad = set(U[(U.is_operator == 't') | (U.in_test_group == 't')].user_id)
REF = build_ref(R)
inv = sum(int((np.diff(y) < 0).sum()) for (x, y) in REF.values())
DIS = sorted(set(R[R.seq.isin(D.seq_b) | R.seq.isin(D.seq_f)].dropna(subset=['irs_rn']).disease))
print('reference calcs', R[(R.t >= TS) & (R.t < B1)].seq.nunique(), 'tables', len(REF), 'inversions', inv, 'conflicts', rank_conflicts(REF), '| diseases', len(DIS))
imode = I.set_index('seq')['mode'].astype(str)
BB['mode_o'] = BB.seq_o.map(imode); BB['meas_o'] = BB.seq_o.map(I.set_index('seq').meas).astype(bool)
FOLD, G = folds(BB); BB['fold'] = FOLD
GENO = {'1', '4'}
ufold = BB.groupby('user_id').fold.first().to_dict()          # each bridge user sits in exactly one fold

def pair_mask(c, m):
    return m & BB.mode_o.isin(GENO).values if c in ('irs', 'prs') else m

VARIANTS = {'main': dict(keep=None, extrap='shift'), 'clip': dict(keep=None, extrap='clip'),
            'noop': dict(keep=~BB.user_id.isin(bad).values, extrap='shift'), 'meas': dict(keep=BB.meas_o.values, extrap='shift')}

def fns(d, c, s, keep=None, extrap='shift', rows=None):
    """full-sample function and the five fold-excluded functions; rows = optional bootstrap row index (with repeats)"""
    xo, xn, ro, m = bridge_values(R, BB, d, c); m = pair_mask(c, m) & (BB.sex_o.values == s)
    if keep is not None: m = m & keep
    idx = np.where(m)[0] if rows is None else rows[m[rows]]
    full = CW(xo[idx], xn[idx], SCALE[c], extrap)
    byk = {k: CW(xo[idx[FOLD[idx] != k]], xn[idx[FOLD[idx] != k]], SCALE[c], extrap) for k in range(5)}
    return full, byk

Dr = D.reset_index(); Dr['mode_b'] = Dr.mode_b.astype(str); Dr['fold'] = Dr.user_id.map(ufold)   # NaN = not a bridge user
rows = []; knots = []; meth = []
for d in DIS:
    Rk = R[R.disease == d].set_index('seq'); b = Rk.reindex(Dr.seq_b).reset_index(drop=True); f = Rk.reindex(Dr.seq_f).reset_index(drop=True)
    x = pd.DataFrame({'user_id': Dr.user_id, 'disease': d, 'sex': Dr.sex_b, 'mode_b': Dr.mode_b, 'fold': Dr.fold})
    for c in SC:
        x[c + '_p_b'] = b[c + '_pn'].values; x[c + '_r_b'] = b[c + '_rn'].values; x[c + '_p_f'] = f[c + '_pn'].values; x[c + '_r_f'] = f[c + '_rn'].values
        for k in ['_p_c', '_r_c', '_lo_c', '_hi_c', '_r_fs', '_lo_f', '_hi_f', '_r_full', '_r_clip', '_r_noop', '_r_meas', '_npairs']: x[c + k] = np.nan
        for k in ['_loc_c', '_loc_f', '_meth']: x[c + k] = ''
        x[c + '_extrap'] = False
        for s in SEXES:
            ix = np.where((x.sex == s).values)[0]
            if not len(ix): continue
            pb = x[c + '_p_b'].values[ix]; fo = x.fold.values[ix]
            for vname, kw in VARIANTS.items():
                full, byk = fns(d, c, s, **kw)
                if vname == 'main':
                    meth.append(dict(disease=d, score=c, sex=s, n_pairs=full.n, method=full.label, lo=full.lo, hi=full.hi))
                    for fit_name, fn_ in [('전체', full)] + [(f'겹{k + 1} 제외', byk[k]) for k in range(5)]:
                        if fn_.kind == 'isotonic':
                            for xk, yk in zip(fn_.x, fn_.y): knots.append(dict(disease=d, score=c, sex=s, fit=fit_name, n_pairs=fn_.n, scale=SCALE[c], old=fn_.f[1](xk), new=fn_.f[1](yk)))
                pc = np.full(len(ix), np.nan); ext = np.zeros(len(ix), bool); npr = np.full(len(ix), np.nan); lab = np.array([''] * len(ix), dtype=object)
                for j in range(len(ix)):
                    fn = full if np.isnan(fo[j]) else byk[int(fo[j])]            # cross-fitting: bridge users get their fold-excluded function
                    pc[j] = fn(pb[j:j + 1])[0]; ext[j] = bool(fn.outside(pb[j:j + 1])[0]); npr[j] = fn.n; lab[j] = fn.label
                r_ = to_rank(REF, pc, d, s, c, detail=(vname == 'main'))
                if vname == 'main':
                    r, loc, lo, hi = r_
                    x.loc[x.index[ix], c + '_p_c'] = pc; x.loc[x.index[ix], c + '_r_c'] = r; x.loc[x.index[ix], c + '_loc_c'] = loc
                    x.loc[x.index[ix], c + '_lo_c'] = lo; x.loc[x.index[ix], c + '_hi_c'] = hi; x.loc[x.index[ix], c + '_extrap'] = ext
                    x.loc[x.index[ix], c + '_meth'] = lab; x.loc[x.index[ix], c + '_npairs'] = npr
                    # full-sample (not cross-fitted) for comparison
                    x.loc[x.index[ix], c + '_r_full'] = to_rank(REF, full(pb), d, s, c)
                else:
                    x.loc[x.index[ix], c + '_r_' + vname] = r_
            rf, locf, lof, hif = to_rank(REF, x[c + '_p_f'].values[ix], d, s, c, detail=True)
            x.loc[x.index[ix], c + '_r_fs'] = rf; x.loc[x.index[ix], c + '_loc_f'] = locf; x.loc[x.index[ix], c + '_lo_f'] = lof; x.loc[x.index[ix], c + '_hi_f'] = hif
        nob = x[c + '_r_b'].isna().values
        if c in ('irs', 'prs'): nob = nob | ~x.mode_b.isin(GENO).values
        for k in ['_p_c', '_r_c', '_lo_c', '_hi_c', '_r_full', '_r_clip', '_r_noop', '_r_meas', '_npairs']: x.loc[nob, c + k] = np.nan
        x.loc[nob, c + '_loc_c'] = ''; x.loc[nob, c + '_extrap'] = False; x.loc[nob, c + '_meth'] = ''
        if c in ('irs', 'prs'): x.loc[x[c + '_r_b'].notna().values & ~x.mode_b.isin(GENO).values, c + '_meth'] = '유전체 없는 기준선(환산 안 함)'
        nof = x[c + '_r_f'].isna().values
        for k in ['_r_fs', '_lo_f', '_hi_f']: x.loc[nof, c + k] = np.nan
        x.loc[nof, c + '_loc_f'] = ''
    rows.append(x)
L = pd.concat(rows, ignore_index=True)
L = L[L[[c + '_r_b' for c in SC] + [c + '_r_f' for c in SC]].notna().any(axis=1)].reset_index(drop=True)
print('long rows', len(L), 'users', L.user_id.nunique(), 'diseases', L.disease.nunique())

# bootstrap of the function estimate (resample bridge users, B=200), same cross-fitting rule; conditional on the fixed reference table
B = 200; rng = np.random.default_rng(20261119); users = BB.user_id.unique(); bs = {c: np.full((len(L), B), np.nan) for c in SC}
Lsex = L.sex.values; Ldis = L.disease.values; Lfold = L.fold.values
for bi in range(B):
    cnt = pd.Series(rng.choice(users, len(users))).value_counts(); w = BB.user_id.map(cnt).fillna(0).astype(int).values
    rep = np.repeat(np.arange(len(BB)), w)
    for d in DIS:
        for c in SC:
            for s in SEXES:
                ix = np.where((Ldis == d) & (Lsex == s) & L[c + '_r_c'].notna().values)[0]
                if not len(ix): continue
                full, byk = fns(d, c, s, rows=rep); pb = L[c + '_p_b'].values[ix]; fo = Lfold[ix]; pc = np.full(len(ix), np.nan)
                nb_ = np.isnan(fo); pc[nb_] = full(pb[nb_])
                for k in range(5):
                    kk = fo == k
                    if kk.any(): pc[kk] = byk[k](pb[kk])
                bs[c][ix, bi] = to_rank(REF, pc, d, s, c)
for c in SC:
    L[c + '_bs_lo'] = np.nanpercentile(bs[c], 2.5, axis=1); L[c + '_bs_hi'] = np.nanpercentile(bs[c], 97.5, axis=1)
    L.loc[L[c + '_r_c'].isna(), [c + '_bs_lo', c + '_bs_hi']] = np.nan

M = pd.DataFrame(meth); K = pd.DataFrame(knots)
L.to_pickle('L.pkl'); M.to_pickle('M.pkl'); K.to_pickle('K.pkl'); pd.to_pickle(REF, 'REF.pkl'); pd.to_pickle(DIS, 'DIS.pkl')
for c in SC:
    ok = L[c + '_r_c'].notna()
    print(c, 'converted', ok.sum(), '| vs full', (band(L.loc[ok, c + '_r_c']) == band(L.loc[ok, c + '_r_full'])).mean().round(4),
          '| clip', (band(L.loc[ok, c + '_r_c']) == band(L.loc[ok, c + '_r_clip'])).mean().round(4), '| noop', (band(L.loc[ok, c + '_r_c']) == band(L.loc[ok, c + '_r_noop'])).mean().round(4),
          '| meas', (band(L.loc[ok, c + '_r_c']) == band(L.loc[ok, c + '_r_meas'])).mean().round(4), '| extrap', L.loc[ok, c + '_extrap'].mean().round(4),
          '| bs crossing', (band(L.loc[ok, c + '_bs_lo']) != band(L.loc[ok, c + '_bs_hi'])).mean().round(3))
