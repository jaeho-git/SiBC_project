# -*- coding: utf-8 -*-
"""v3 validation. OOF with the fixed reference table (main); held-out-table variant in which both the prediction and the
answer use the table built without the test fold; per-sex and pooled metrics, kappa, confusion; user-bootstrap intervals
(predictions fixed) per sex and pooled; pass stability that refits and re-applies the per-sex rule for all four scores;
reference-table reproduction; representativeness; counts for the flow table."""
from xwlib import *
from sklearn.metrics import cohen_kappa_score
import json
R, I, D, BB = load(); REF = pd.read_pickle('REF.pkl'); DIS = pd.read_pickle('DIS.pkl'); L = pd.read_pickle('L.pkl')
imode = I.set_index('seq')['mode'].astype(str); BB['mode_o'] = BB.seq_o.map(imode); GENO = {'1', '4'}
U = pd.read_csv('users.csv'); bad = set(U[(U.is_operator == 't') | (U.in_test_group == 't')].user_id)
FOLD, G = folds(BB); BB['fold'] = FOLD; BB['g'] = G; BB['pair'] = ['B%03d' % (i + 1) for i in range(len(BB))]
REFK = {k: build_ref(R, exclude_users=set(BB.user_id[BB.fold == k])) for k in range(5)}
rng = np.random.default_rng(20261119)

def masks(d, c):
    xo, xn, ro, m = bridge_values(R, BB, d, c)
    if c in ('irs', 'prs'): m = m & BB.mode_o.isin(GENO).values
    return xo, xn, ro, m

def oof(d, c, idx, rows_fold, ref_by_fold=None):
    """out-of-fold ranks for bridge rows idx; training excludes the test fold; ref_by_fold gives the table per test fold"""
    xo, xn, ro, m = masks(d, c); pred = np.full(len(idx), np.nan); sx = BB.sex_o.values[idx]
    for k in range(5):
        ref = ref_by_fold[k] if ref_by_fold else REF
        for s in SEXES:
            trs = np.where((rows_fold != k) & (sx == s))[0]; tes = np.where((rows_fold == k) & (sx == s))[0]
            if not len(tes): continue
            pred[tes] = to_rank(ref, CW(xo[idx[trs]], xn[idx[trs]], SCALE[c])(xo[idx[tes]]), d, s, c)
    return pred

def truth_of(d, c, idx, rows_fold, ref_by_fold=None):
    xo, xn, ro, m = masks(d, c); t = np.full(len(idx), np.nan); sx = BB.sex_o.values[idx]
    for k in range(5):
        for s in SEXES:
            j = (rows_fold == k) & (sx == s)
            if j.any(): t[j] = to_rank(ref_by_fold[k] if ref_by_fold else REF, xn[idx[j]], d, s, c)
    return t

def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; den = 1 + z * z / n; cen = (p + z * z / (2 * n)) / den; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return cen - h, cen + h
kap = lambda a, b, w: cohen_kappa_score(a.astype(int), b.astype(int), weights=w, labels=list(range(5))) if len(set(a) | set(b)) > 1 else np.nan

VR = []; MET = []; CONF = []; NP = []
for d in DIS:
    for c in SC:
        xo, xn, ro, m0 = bridge_values(R, BB, d, c); xo, xn, ro, m = masks(d, c); idx = np.where(m)[0]
        NP.append(dict(disease=d, score=c, all_pairs=len(BB), valid=int(m0.sum()), used=int(m.sum()), dropped_missing=int(len(BB) - m0.sum()), dropped_nogeno=int(m0.sum() - m.sum())))
        if len(idx) < 30: continue
        fo = FOLD[idx]; sx = BB.sex_o.values[idx]
        truth = truth_of(d, c, idx, fo); pred = oof(d, c, idx, fo)
        truth_h = truth_of(d, c, idx, fo, REFK); pred_h = oof(d, c, idx, fo, REFK)
        raw = ro[idx]
        VR.append(pd.DataFrame({'pair': BB.pair.values[idx], 'g': BB.g.values[idx], 'fold': fo, 'disease': d, 'score': c, 'sex': sx,
                                'truth': truth, 'raw': raw, 'pred': pred, 'truth_h': truth_h, 'pred_h': pred_h}))
        bt, bp, br = band(truth), band(pred), band(raw); bth, bph = band(truth_h), band(pred_h)
        for s in SEXES + ['all']:
            k = np.isfinite(truth) & np.isfinite(pred) & ((sx == s) if s != 'all' else True)
            n = int(k.sum())
            if n == 0: continue
            ag = int((bt[k] == bp[k]).sum()); lo, hi = wilson(ag, n); kh = k & np.isfinite(truth_h) & np.isfinite(pred_h)
            MET.append(dict(disease=d, score=c, sex=s, n_pairs=n, n_users=len(set(BB.g.values[idx][k])), agree=ag, rate=ag / n, w_lo=lo, w_hi=hi,
                            raw_agree=int((bt[k] == br[k]).sum()), raw_rate=(bt[k] == br[k]).mean(), ind_rate=(bth[kh] == bph[kh]).mean(),
                            within2=(np.abs(truth[k] - pred[k]) <= 2).mean(), raw_within2=(np.abs(truth[k] - raw[k]) <= 2).mean(),
                            k_raw=kap(bt[k], br[k], None), k_cw=kap(bt[k], bp[k], None), kw_raw=kap(bt[k], br[k], 'quadratic'), kw_cw=kap(bt[k], bp[k], 'quadratic'),
                            to_lower=(bp[k] < bt[k]).mean(), to_higher=(bp[k] > bt[k]).mean()))
            if s != 'all':
                ct = pd.crosstab(bt[k].astype(int) + 1, bp[k].astype(int) + 1).reindex(index=range(1, 6), columns=range(1, 6), fill_value=0)
                for a in range(1, 6):
                    for b in range(1, 6): CONF.append(dict(disease=d, score=c, sex=s, truth_band=a, conv_band=b, n=int(ct.loc[a, b])))
VR = pd.concat(VR, ignore_index=True); MET = pd.DataFrame(MET); CONF = pd.DataFrame(CONF); NP = pd.DataFrame(NP)

# user-bootstrap intervals with predictions fixed (per sex and pooled)
ci = {}
for (d, c), g in VR.groupby(['disease', 'score']):
    for s in SEXES + ['all']:
        gs = g if s == 'all' else g[g.sex == s]
        if not len(gs): continue
        same = (band(gs.truth.values) == band(gs.pred.values)); gg = gs.g.values
        grp = {u: np.where(gg == u)[0] for u in np.unique(gg)}; uu = np.array(list(grp))
        vals = [same[np.concatenate([grp[u] for u in rng.choice(uu, len(uu))])].mean() for _ in range(1000)]
        ci[(d, c, s)] = (np.percentile(vals, 2.5), np.percentile(vals, 97.5))
MET['bs_lo'] = [ci.get((r.disease, r.score, r.sex), (np.nan, np.nan))[0] for r in MET.itertuples()]
MET['bs_hi'] = [ci.get((r.disease, r.score, r.sex), (np.nan, np.nan))[1] for r in MET.itertuples()]

# pass stability: resample users (B=200), refit inside the same fold scheme, apply the per-sex rule (and the pooled rule)
B = 200; ug = np.unique(BB.g); st_sex = {}; st_pool = {}
for bi in range(B):
    cnt = pd.Series(rng.choice(ug, len(ug))).value_counts(); w = pd.Series(BB.g).map(cnt).fillna(0).astype(int).values
    rep = np.repeat(np.arange(len(BB)), w)
    for d in DIS:
        for c in SC:
            xo, xn, ro, m = masks(d, c); idx = rep[m[rep]]
            if len(idx) < 30: continue
            fo = FOLD[idx]; sx = BB.sex_o.values[idx]
            truth = truth_of(d, c, idx, fo); pred = oof(d, c, idx, fo); ok = np.isfinite(truth) & np.isfinite(pred)
            same = band(truth) == band(pred)
            rates = [same[ok & (sx == s)].mean() for s in SEXES if (ok & (sx == s)).any()]
            st_sex.setdefault((d, c), []).append(min(rates) >= 0.95); st_pool.setdefault((d, c), []).append(same[ok].mean() >= 0.95)
MET['pass_share'] = [np.mean(st_sex[(r.disease, r.score)]) if (r.sex == 'all' and (r.disease, r.score) in st_sex) else np.nan for r in MET.itertuples()]
MET['pass_share_pool'] = [np.mean(st_pool[(r.disease, r.score)]) if (r.sex == 'all' and (r.disease, r.score) in st_pool) else np.nan for r in MET.itertuples()]

# reference-table reproduction: stable-period calcs, user-grouped 5 folds, table from the other users vs service rank
T = R[(R.t >= TS) & (R.t < B1)]; usr = T.user_id.unique(); rep_rows = []
fold_of = {u: k for k, part in enumerate(np.array_split(rng.permutation(usr), 5)) for u in part}; T = T.assign(fold=T.user_id.map(fold_of))
for k in range(5):
    ref = build_ref(R, exclude_users=set(T[T.fold == k].user_id)); te = T[T.fold == k]
    for (d, s), g in te.groupby(['disease', 'sex']):
        if d not in DIS: continue
        for c in SC:
            gg = g[g[c + '_pn'].notna() & g[c + '_rn'].notna()]
            if not len(gg): continue
            p = to_rank(ref, gg[c + '_pn'].values, d, s, c); o = gg[c + '_rn'].values; ok = np.isfinite(p)
            rep_rows.append(dict(score=c, n=int(ok.sum()), exact=int((p[ok] == o[ok]).sum()), same=int((band(p[ok]) == band(o[ok])).sum())))
REP = pd.DataFrame(rep_rows).groupby('score').sum(); REP['exact_rate'] = REP.exact / REP.n; REP['same_rate'] = REP.same / REP.n

# representativeness and flow counts
Ii = I.set_index('seq'); rows = []
for s in SEXES:
    bo = BB[BB.sex_o == s]; db = D[D.sex_b == s]
    a1 = pd.to_numeric(Ii.loc[bo.seq_o, 'age'], errors='coerce'); a2 = pd.to_numeric(Ii.loc[db.seq_b, 'age'], errors='coerce')
    rows.append(dict(sex=s, bridge_pairs=len(bo), bridge_users=bo.user_id.nunique(), analysed=len(db),
                     age_bridge=f"{a1.median():.0f} ({a1.quantile(.25):.0f}–{a1.quantile(.75):.0f})", age_anal=f"{a2.median():.0f} ({a2.quantile(.25):.0f}–{a2.quantile(.75):.0f})",
                     geno_bridge=Ii.loc[bo.seq_o, 'mode'].astype(str).isin(GENO).mean(), geno_anal=Ii.loc[db.seq_b, 'mode'].astype(str).isin(GENO).mean(),
                     meas_bridge=Ii.loc[bo.seq_o, 'meas'].mean(), meas_anal=1.0, op_bridge=bo.user_id.isin(bad).mean(), overlap=len(set(bo.user_id) & set(db.index))))
REPR = pd.DataFrame(rows)
# input / previous-score distributions (bridge old side vs analysed baseline) and agreement by age group
sbp = pd.to_numeric(Ii.sbp, errors='coerce'); q = lambda v: f"{v.median():.0f} ({v.quantile(.25):.0f}–{v.quantile(.75):.0f})"
Rr = R.set_index('seq'); irs_o = pd.to_numeric(Rr.loc[Rr.index.isin(BB.seq_o), 'irs_rn'], errors='coerce'); irs_b = pd.to_numeric(Rr.loc[Rr.index.isin(D.seq_b), 'irs_rn'], errors='coerce')
mrs_o = pd.to_numeric(Rr.loc[Rr.index.isin(BB.seq_o), 'mrs_rn'], errors='coerce'); mrs_b = pd.to_numeric(Rr.loc[Rr.index.isin(D.seq_b), 'mrs_rn'], errors='coerce')
dist = dict(sbp_bridge=q(sbp.reindex(BB.seq_o).dropna()), sbp_anal=q(sbp.reindex(D.seq_b).dropna()), irs_bridge=q(irs_o.dropna()), irs_anal=q(irs_b.dropna()),
            mrs_bridge=q(mrs_o.dropna()), mrs_anal=q(mrs_b.dropna()))
age_o = pd.to_numeric(Ii.loc[BB.seq_o, 'age'], errors='coerce').values; pair_age = dict(zip(BB.pair, age_o))
VR['age'] = VR.pair.map(pair_age); VR['ageg'] = pd.cut(VR.age, [-1, 49, 64, 200], labels=['50세 미만', '50~64세', '65세 이상'])
byage = {}
for c in ['irs', 'mrs']:
    v = VR[(VR.score == c) & VR.truth.notna() & VR.pred.notna()]
    for gname, g in v.groupby('ageg', observed=True): byage[f'{c}|{gname}'] = dict(n=int(len(g)), pairs=int(g.pair.nunique()), rate=float((band(g.truth) == band(g.pred)).mean()), raw=float((band(g.truth) == band(g.raw)).mean()))
gap_h = (BB.t_n - BB.t_o).dt.total_seconds() / 86400
ident = {}
for c in ['lrs', 'prs', 'irs', 'mrs']:
    tot = 0; same = 0
    for d in DIS:
        xo, xn, ro, m = bridge_values(R, BB, d, c); tot += int(m.sum()); same += int(np.isclose(xo[m], xn[m], atol=1e-12, rtol=0).sum())
    ident[c] = same / tot
pr = R[R.seq.isin(set(BB.seq_o) | set(BB.seq_n) | set(D.seq_b) | set(D.seq_f))]
clip = {c: int(((pr[c + '_pn'] < 1e-9) | (pr[c + '_pn'] > 1 - 1e-9)).sum()) for c in ['irs', 'mrs']}
extra = dict(cov={c: float(1 - L.loc[L[c + '_r_c'].notna(), c + '_extrap'].mean()) for c in SC}, miss_key=int(BB.key.str.contains(r'(^|\|)x(\||$)').sum()),
             gap_days_median=float(gap_h.median()), gap_days_q1=float(gap_h.quantile(.25)), gap_days_q3=float(gap_h.quantile(.75)), gap_days_max=float(gap_h.max()),
             ident={k: float(v) for k, v in ident.items()}, clip=clip, dist=dist, byage=byage, sex_mismatch=int((D.sex_b != D.sex_f).sum()))
VR.to_pickle('VR.pkl'); MET.to_pickle('MET.pkl'); CONF.to_pickle('CONF.pkl'); REP.to_pickle('REP.pkl'); REPR.to_pickle('REPR.pkl'); NP.to_pickle('NP.pkl')
json.dump(extra, open('x8b_extra.json', 'w'))
A = MET[MET.sex == 'all']
print(A.groupby('score')[['raw_rate', 'rate', 'ind_rate', 'kw_cw', 'pass_share', 'pass_share_pool']].median().round(3))
print('stable (per-sex rule >=0.8):', {c: int((A[A.score == c].pass_share >= .8).sum()) for c in SC})
print('pairs per score (median used):', NP.groupby('score').used.median().to_dict(), '| dropped missing', NP.groupby('score').dropped_missing.median().to_dict())
print(REP.round(4)); print(extra)
