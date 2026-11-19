# -*- coding: utf-8 -*-
"""v5 design (2026-11-19, after Codex review): exact selection rules for the comparison-set design, alternative designs and onboarding
statistics computed in one place. Times are KST-naive (source offsets +09; login dates cut in Asia/Seoul).
Rules
- cohort: site-linked, not operator/test, first login exists, first login + 28 days <= 2026-11-17 and no withdrawal on or before that date
- complete IRS: genome mode 1/4 AND measured checkup (SBP, DBP, fasting glucose all integers) AND lifestyle answers present
- baseline: among complete IRS with 0 <= (calc date - first login date) <= WIN, the earliest (ties: smaller seq); must be pre-July model
- follow-up: complete IRS with (calc date - baseline date) >= 90, genotype hash equal to the baseline's (both non-missing), at least one of
  14 measured checkup items present at both times with a different value (|diff| > 1e-9), calculated before 2026-08-02; earliest one
Writes D2.pkl, x7b_flow.json, x7b_alt.json, x7b_onboard.json."""
import pandas as pd, numpy as np, json
B0 = pd.Timestamp('2026-07-01 10:00'); B1 = pd.Timestamp('2026-08-02'); END = pd.Timestamp('2026-11-17'); DATA_END = pd.Timestamp('2026-11-20'); GAP = 90
CORE = ['SBP', 'DBP', 'FastingGlucose', '2_TCHL', '2_HDL', '2_TG', 'WEIGHT', 'HEIGHT', '2_WAIST', '2_HB', '2_AST', '2_ALT', '2_R_GTP', '2_CREATINE']

I = pd.read_pickle('I_final.pkl'); I['mode'] = I['mode'].astype(str); I = I.sort_values(['t', 'seq']).reset_index(drop=True)
I['d'] = I.t.dt.normalize(); I['model'] = np.where(I.t < B0, 'P0', np.where(I.t < B1, 'P1', '이후'))
I['geno'] = I['mode'].isin(['1', '4']); I['complete'] = I.geno & I.meas.astype(bool) & I.life_h.notna()
U = pd.read_csv('users.csv')
for c in ['is_operator', 'in_test_group']: U[c] = U[c] == 't'
U['site'] = np.where(U.ulsan_linked.notna(), '울산', np.where(U.jeju_linked.notna(), '제주', ''))
Lg = pd.read_csv('login.csv', parse_dates=['d'])[['user_id', 'd']].drop_duplicates(); d0 = Lg.groupby('user_id').d.min()
X = pd.read_csv('irs_inputs.csv').set_index('seq'); parse_fail = set()
def core(seq):
    raw = X.med.get(seq)
    try: m = json.loads(raw) if isinstance(raw, str) else {}
    except Exception: parse_fail.add(seq); m = {}
    if not isinstance(m, dict) or not m: parse_fail.add(seq); m = {}
    return pd.to_numeric(pd.Series([m.get(k) for k in CORE], index=CORE), errors='coerce').values
_cache = {}
def C_(seq):
    if seq not in _cache: _cache[seq] = core(seq)
    return _cache[seq]
def changed(sa, sb):
    a, b = C_(sa), C_(sb)
    if sa in parse_fail or sb in parse_fail: return False
    both = np.isfinite(a) & np.isfinite(b)
    return bool((np.abs(a[both] - b[both]) > 1e-9).any())

# ---------- cohort ----------
flow = {}
site = U[U.site != '']; flow['site_users'] = len(site)
C = site[~site.is_operator & ~site.in_test_group].copy(); flow['excl_operator_test'] = len(site) - len(C)
C['d0'] = C.user_id.map(d0); flow['no_login'] = int(C.d0.isna().sum()); C = C[C.d0.notna()].copy()
C['wdd'] = pd.to_datetime(C.withdraw_dt, utc=True).dt.tz_convert('Asia/Seoul').dt.tz_localize(None).dt.normalize()    # withdrawal date (KST)
C['common'] = (C.d0 + pd.Timedelta(days=28) <= END) & ~(C.wdd <= C.d0 + pd.Timedelta(days=28))
flow['not_common'] = int((~C.common).sum()); C = C[C.common].set_index('user_id'); flow['common_cohort'] = len(C)
Ic = I[I.user_id.isin(C.index)].copy(); Ic['k'] = (Ic.d - Ic.user_id.map(C.d0)).dt.days
flow['with_any_irs'] = int(Ic.user_id.nunique()); comp = Ic[Ic.complete]
flow['with_complete_irs'] = int(comp.user_id.nunique()); flow['complete_before_registration'] = int((comp.k < 0).sum())

# ---------- onboarding (common cohort) ----------
ob = {}
for name, sub in [('meas', Ic[Ic.meas.astype(bool)]), ('geno', Ic[Ic.geno]), ('comp', comp)]:
    k = sub[sub.k >= 0].groupby('user_id').k.min()
    ob[name] = dict(n=int(len(k)), med=float(k.median()), q75=float(k.quantile(.75)), q90=float(k.quantile(.9)), w28=int((k <= 28).sum()), w56=int((k <= 56).sum()), w90=int((k <= 90).sum()))
json.dump(ob, open('x7b_onboard.json', 'w'))

def design(win=56, upto=B1, base_models=('P0',), require_change=True, record=False):
    w = comp[(comp.k >= 0) & (comp.k <= win)]
    base = w.drop_duplicates('user_id', keep='first').set_index('user_id')            # earliest within the window (sorted t, seq)
    out = dict(within_window=len(base))
    base = base[base.model.isin(base_models)]; out['baseline_model_ok'] = len(base)
    why = dict(no_complete_90d=0, genotype_unverifiable=0, genotype_differs=0, no_new_checkup=0, new_checkup_only_later=0)
    rows = []
    for u, b in base.iterrows():
        cand = comp[(comp.user_id == u) & ((comp.d - b.d).dt.days >= GAP)]
        if not len(cand): why['no_complete_90d'] += 1; continue
        if pd.isna(b.geno_h) or cand.geno_h.isna().all(): why['genotype_unverifiable'] += 1; continue
        cand = cand[cand.geno_h == b.geno_h]
        if not len(cand): why['genotype_differs'] += 1; continue
        if require_change:
            cand = cand[np.array([changed(s, b.seq) for s in cand.seq], dtype=bool)]
            if not len(cand): why['no_new_checkup'] += 1; continue
        now = cand[cand.t < upto]
        if not len(now): why['new_checkup_only_later'] += 1; continue
        f = now.iloc[0]
        if record:
            a, c = C_(b.seq), C_(f.seq); both = np.isfinite(a) & np.isfinite(c)
            rows.append(dict(user_id=u, sex=b.sex, d0=C.d0[u], site=C.site[u], seq_b=b.seq, t_b=b.t, k_b=int(b.k), mode_b=b['mode'], model_b=b.model,
                             age_b=pd.to_numeric(b.age, errors='coerce'), seq_f=f.seq, t_f=f.t, mode_f=f['mode'], model_f=f.model, age_f=pd.to_numeric(f.age, errors='coerce'),
                             sex_f=f.sex, gap=int((f.d - b.d).days), n_core_changed=int((np.abs(a[both] - c[both]) > 1e-9).sum()), n_core_missing_change=int((np.isfinite(a) != np.isfinite(c)).sum()),
                             life_ch=('예' if f.life_h != b.life_h else '아니오'), geno_same=True, med_h_b=b.med_h, med_h_f=f.med_h, life_h_b=b.life_h, life_h_f=f.life_h))
    out.update(why); out['final'] = len(base) - sum(why.values())
    return (out, pd.DataFrame(rows).set_index('user_id')) if record else out

main, D2 = design(record=True)
flow.update(main); flow['parse_fail_seqs'] = len(parse_fail)
flow['excl_no_irs'] = flow['common_cohort'] - flow['with_any_irs']; flow['excl_no_complete'] = flow['with_any_irs'] - flow['with_complete_irs']
flow['excl_after_window'] = flow['with_complete_irs'] - flow['within_window']; flow['excl_post_july_baseline'] = flow['within_window'] - flow['baseline_model_ok']
alt = {'w28': design(28)['final'], 'w90': design(90)['final'], 'no_change_required': design(require_change=False)['final'],
       'rescore': design(base_models=('P0', 'P1', '이후'), upto=DATA_END)['final'], 'rescore_no_change': design(base_models=('P0', 'P1', '이후'), upto=DATA_END, require_change=False)['final']}
json.dump(alt, open('x7b_alt.json', 'w'))
# exposure and covariates
fany = Ic.drop_duplicates('user_id', keep='first').set_index('user_id')
D2['first_seq'] = fany.seq.reindex(D2.index); D2['first_t'] = fany.t.reindex(D2.index); D2['first_k'] = fany.k.reindex(D2.index)
x = Lg.merge(D2[['t_b', 'd0', 't_f']].reset_index(), on='user_id'); kk = (x.d - x.t_b.dt.normalize()).dt.days
D2['act28'] = x[(kk >= 1) & (kk <= 28)].groupby('user_id').size().reindex(D2.index).fillna(0).astype(int)
D2['act_pre'] = x[(x.d >= x.d0) & (kk < 0)].groupby('user_id').size().reindex(D2.index).fillna(0).astype(int)      # days strictly before the baseline day
D2['ldays'] = x[(kk >= 1) & (x.d <= x.t_f.dt.normalize())].groupby('user_id').size().reindex(D2.index).fillna(0).astype(int)
D2 = D2.sort_values(['t_b', 'seq_b']); D2['sid'] = ['S%03d' % (i + 1) for i in range(len(D2))]
D2.to_pickle('D2.pkl'); json.dump(flow, open('x7b_flow.json', 'w'), ensure_ascii=False)
print(json.dumps(flow, ensure_ascii=False)); print('alt', alt); print('onboard comp', ob['comp'])
print('final', len(D2), D2.sex.value_counts().to_dict(), D2.model_f.value_counts().to_dict(), '| missing-status changes among final', int((D2.n_core_missing_change > 0).sum()))
