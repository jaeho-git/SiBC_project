# -*- coding: utf-8 -*-
"""v4 conversion for the comparison-set design. Follow-up on the July model (P1): baseline converted with the 5-fold cross-fitted
crosswalk, follow-up re-ranked with the July reference table. Follow-up on the pre-July model (P0): no conversion (same model);
a July-scale version of both ranks is kept as a sensitivity analysis."""
from xwlib import *
R, I, D_old, BB = load(); D = pd.read_pickle('D2.pkl')
U = pd.read_csv('users.csv'); bad = set(U[(U.is_operator == 't') | (U.in_test_group == 't')].user_id)
REF = build_ref(R); print('ref tables', len(REF), 'inversions', sum(int((np.diff(y) < 0).sum()) for x, y in REF.values()), 'conflicts', rank_conflicts(REF))
DIS = pd.read_pickle('DIS.pkl')
imode = I.set_index('seq')['mode'].astype(str); BB['mode_o'] = BB.seq_o.map(imode); BB['meas_o'] = BB.seq_o.map(I.set_index('seq').meas).astype(bool)
FOLD, G = folds(BB); BB['fold'] = FOLD; ufold = BB.groupby('user_id').fold.first().to_dict(); GENO = {'1', '4'}
def pair_mask(c, m): return m & BB.mode_o.isin(GENO).values if c in ('irs', 'prs') else m
VARIANTS = {'main': dict(keep=None, extrap='shift'), 'clip': dict(keep=None, extrap='clip'),
            'noop': dict(keep=~BB.user_id.isin(bad).values, extrap='shift'), 'meas': dict(keep=BB.meas_o.values, extrap='shift')}
def fns(d, c, s, keep=None, extrap='shift', rows=None):
    xo, xn, ro, m = bridge_values(R, BB, d, c); m = pair_mask(c, m) & (BB.sex_o.values == s)
    if keep is not None: m = m & keep
    idx = np.where(m)[0] if rows is None else rows[m[rows]]
    return CW(xo[idx], xn[idx], SCALE[c], extrap), {k: CW(xo[idx[FOLD[idx] != k]], xn[idx[FOLD[idx] != k]], SCALE[c], extrap) for k in range(5)}
def apply(full, byk, p, fo):
    out = np.full(len(p), np.nan); ext = np.zeros(len(p), bool); npr = np.full(len(p), np.nan); lab = np.array([''] * len(p), dtype=object)
    for j in range(len(p)):
        fn = full if np.isnan(fo[j]) else byk[int(fo[j])]
        out[j] = fn(p[j:j + 1])[0]; ext[j] = bool(fn.outside(p[j:j + 1])[0]); npr[j] = fn.n; lab[j] = fn.label
    return out, ext, npr, lab
Dr = D.reset_index(); Dr['fold'] = Dr.user_id.map(ufold)
rows = []; knots = []; meth = []
for d in DIS:
    Rk = R[R.disease == d].set_index('seq'); b = Rk.reindex(Dr.seq_b).reset_index(drop=True); f = Rk.reindex(Dr.seq_f).reset_index(drop=True)
    x = pd.DataFrame({'user_id': Dr.user_id, 'disease': d, 'sex': Dr.sex, 'model_f': Dr.model_f, 'fold': Dr.fold})
    same = (Dr.model_f == 'P0').values
    for c in SC:
        x[c + '_p_b'] = b[c + '_pn'].values; x[c + '_r_b'] = b[c + '_rn'].values; x[c + '_p_f'] = f[c + '_pn'].values; x[c + '_r_f'] = f[c + '_rn'].values
        for k in ['_p_c', '_r_c', '_lo_c', '_hi_c', '_r_fs', '_lo_f', '_hi_f', '_r_full', '_r_clip', '_r_noop', '_r_meas', '_npairs', '_rj_b', '_rj_f']: x[c + k] = np.nan
        for k in ['_loc_c', '_loc_f', '_meth']: x[c + k] = ''
        x[c + '_extrap'] = False
        for s in SEXES:
            ix = np.where((x.sex == s).values)[0]
            if not len(ix): continue
            pb = x[c + '_p_b'].values[ix]; pf = x[c + '_p_f'].values[ix]; fo = x.fold.values[ix]; sm = same[ix]
            for vname, kw in VARIANTS.items():
                full, byk = fns(d, c, s, **kw)
                if vname == 'main':
                    meth.append(dict(disease=d, score=c, sex=s, n_pairs=full.n, method=full.label))
                    for fit_name, fn_ in [('전체', full)] + [(f'겹{k + 1} 제외', byk[k]) for k in range(5)]:
                        if fn_.kind == 'isotonic':
                            for xk, yk in zip(fn_.x, fn_.y): knots.append(dict(disease=d, score=c, sex=s, fit=fit_name, n_pairs=fn_.n, scale=SCALE[c], old=fn_.f[1](xk), new=fn_.f[1](yk)))
                pc, ext, npr, lab = apply(full, byk, pb, fo)
                if vname == 'main':
                    r, loc, lo, hi = to_rank(REF, pc, d, s, c, detail=True)
                    # July-scale ranks for every row (used directly for P1 follow-ups, as sensitivity for same-model rows)
                    x.loc[x.index[ix], c + '_rj_b'] = r
                    rf, locf, lof, hif = to_rank(REF, pf, d, s, c, detail=True)
                    # July-scale follow-up: previous-model follow-ups (same-model rows) are converted; July-model follow-ups are only re-ranked
                    pcf, _, _, _ = apply(full, byk, pf, fo); x.loc[x.index[ix], c + '_rj_f'] = np.where(sm, to_rank(REF, pcf, d, s, c), rf)
                    # main comparison: P1 follow-up -> converted baseline vs re-ranked follow-up; P0 follow-up -> service ranks (same model)
                    x.loc[x.index[ix], c + '_p_c'] = np.where(sm, pb, pc); x.loc[x.index[ix], c + '_r_c'] = np.where(sm, x[c + '_r_b'].values[ix], r)
                    x.loc[x.index[ix], c + '_loc_c'] = np.where(sm, '같은 모델(환산 없음)', loc); x.loc[x.index[ix], c + '_lo_c'] = np.where(sm, np.nan, lo); x.loc[x.index[ix], c + '_hi_c'] = np.where(sm, np.nan, hi)
                    x.loc[x.index[ix], c + '_extrap'] = np.where(sm, False, ext); x.loc[x.index[ix], c + '_npairs'] = np.where(sm, np.nan, npr)
                    x.loc[x.index[ix], c + '_meth'] = np.where(sm, '같은 모델(환산 없음)', lab)
                    x.loc[x.index[ix], c + '_r_fs'] = np.where(sm, x[c + '_r_f'].values[ix], rf); x.loc[x.index[ix], c + '_loc_f'] = np.where(sm, '같은 모델(서비스 순위)', locf)
                    x.loc[x.index[ix], c + '_lo_f'] = np.where(sm, np.nan, lof); x.loc[x.index[ix], c + '_hi_f'] = np.where(sm, np.nan, hif)
                    x.loc[x.index[ix], c + '_r_full'] = np.where(sm, np.nan, to_rank(REF, full(pb), d, s, c))
                else:
                    x.loc[x.index[ix], c + '_r_' + vname] = np.where(sm, np.nan, to_rank(REF, pc, d, s, c))
        nob = x[c + '_r_b'].isna().values; nof = x[c + '_r_f'].isna().values
        for k in ['_p_c', '_r_c', '_lo_c', '_hi_c', '_r_full', '_r_clip', '_r_noop', '_r_meas', '_npairs', '_rj_b']: x.loc[nob, c + k] = np.nan
        x.loc[nob, [c + '_loc_c', c + '_meth']] = ''; x.loc[nob, c + '_extrap'] = False
        for k in ['_r_fs', '_lo_f', '_hi_f', '_rj_f']: x.loc[nof, c + k] = np.nan
        x.loc[nof, c + '_loc_f'] = ''
    rows.append(x)
L = pd.concat(rows, ignore_index=True)
L = L[L[[c + '_r_b' for c in SC] + [c + '_r_f' for c in SC]].notna().any(axis=1)].reset_index(drop=True)
print('long rows', len(L), 'users', L.user_id.nunique(), 'diseases', L.disease.nunique())
# bootstrap range of the conversion function (P1 rows only), same cross-fitting rule
B = 200; rng = np.random.default_rng(20261119); users = BB.user_id.unique(); bs = {c: np.full((len(L), B), np.nan) for c in SC}
Lsex = L.sex.values; Ldis = L.disease.values; Lfold = L.fold.values; P1 = (L.model_f == 'P1').values
for bi in range(B):
    cnt = pd.Series(rng.choice(users, len(users))).value_counts(); w = BB.user_id.map(cnt).fillna(0).astype(int).values; rep = np.repeat(np.arange(len(BB)), w)
    for d in DIS:
        for c in SC:
            for s in SEXES:
                ix = np.where((Ldis == d) & (Lsex == s) & P1 & L[c + '_r_c'].notna().values)[0]
                if not len(ix): continue
                full, byk = fns(d, c, s, rows=rep); pc, _, _, _ = apply(full, byk, L[c + '_p_b'].values[ix], Lfold[ix])
                bs[c][ix, bi] = to_rank(REF, pc, d, s, c)
for c in SC:
    L[c + '_bs_lo'] = np.nanpercentile(bs[c], 2.5, axis=1); L[c + '_bs_hi'] = np.nanpercentile(bs[c], 97.5, axis=1)
    L.loc[~P1 | L[c + '_r_c'].isna(), [c + '_bs_lo', c + '_bs_hi']] = np.nan
L.to_pickle('L2.pkl'); pd.DataFrame(meth).to_pickle('M2.pkl'); pd.DataFrame(knots).to_pickle('K2.pkl')
for c in SC:
    ok = L[c + '_r_c'].notna() & P1
    print(c, 'P1 converted', ok.sum(), '| vs full', (band(L.loc[ok, c + '_r_c']) == band(L.loc[ok, c + '_r_full'])).mean().round(4), '| noop', (band(L.loc[ok, c + '_r_c']) == band(L.loc[ok, c + '_r_noop'])).mean().round(4),
          '| extrap', L.loc[ok, c + '_extrap'].mean().round(4), '| bs crossing', (band(L.loc[ok, c + '_bs_lo']) != band(L.loc[ok, c + '_bs_hi'])).mean().round(3))
sm = (L.model_f == 'P0') & L.irs_r_c.notna() & L.irs_r_fs.notna() & L.irs_rj_b.notna() & L.irs_rj_f.notna()
print('same-model rows: band movement identical on July scale', ((np.sign(band(L.irs_r_fs[sm]) - band(L.irs_r_c[sm]))) == np.sign(band(L.irs_rj_f[sm]) - band(L.irs_rj_b[sm]))).mean().round(3))
