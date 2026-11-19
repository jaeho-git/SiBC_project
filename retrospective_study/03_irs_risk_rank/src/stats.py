# -*- coding: utf-8 -*-
"""Collects every number quoted in the workbook guide and the methods document into stats.json."""
from xwlib import *
import json, platform, sklearn, openpyxl
R, I, D, BB = load(); REF = pd.read_pickle('REF.pkl'); DIS = pd.read_pickle('DIS.pkl'); L = pd.read_pickle('L.pkl')
MET = pd.read_pickle('MET.pkl'); CONF = pd.read_pickle('CONF.pkl'); REP = pd.read_pickle('REP.pkl'); REPR = pd.read_pickle('REPR.pkl')
X8B = json.load(open('x8b_extra.json')); X8C = json.load(open('x8c.json')); u = pd.read_pickle('XL_users.pkl')['u']
info = pd.read_csv('dis_info.csv').set_index('disease_id')
EXTRA_NM = {"cardiac_arrhythmia": "부정맥", "endometrial_cancer": "자궁내막암", "endometriosis": "자궁내막증", "polycystic_ovary_syndrome": "다낭성 난소 증후군"}
nm = lambda d: info.disease_nm.get(d, EXTRA_NM.get(d, d))
U = pd.read_csv('users.csv'); bad = set(U[(U.is_operator == 't') | (U.in_test_group == 't')].user_id)
st = {}
st['log_calcs'] = int(len(I)); st['log_users'] = int(I.user_id.nunique()); st['log_from'] = str(I.t.min().date()); st['log_to'] = str(I.t.max().date())
st['p0_calcs'] = int((I.t < B0).sum()); st['p1_calcs'] = int(((I.t >= B0) & (I.t < B1)).sum())
T = R[(R.t >= TS) & (R.t < B1)]; st['ref_calcs'] = int(T.seq.nunique())
st['ref_tables'] = int(sum(1 for (d, s, c) in REF if d in DIS)); st['ref_inv'] = int(sum((np.diff(y) < 0).sum() for (d, s, c), (x, y) in REF.items()))
E = R[(R.t >= pd.Timestamp('2026-07-01')) & (R.t < B0)]; st['early_calcs'] = int(E.seq.nunique())
Bt = R[(R.t >= B0) & (R.t < TS)]; st['batch_calcs'] = int(Bt.seq.nunique()); st['batch_users'] = int(Bt.user_id.nunique())
ex, bd = [], []
for c in SC:
    for (d, s), g in Bt.groupby(['disease', 'sex']):
        g = g[g[c + '_pn'].notna() & g[c + '_rn'].notna()]
        if (d, s, c) not in REF or not len(g): continue
        t = to_rank(REF, g[c + '_pn'].values, d, s, c); ex += list(t == g[c + '_rn'].values); bd += list(band(t) == band(g[c + '_rn'].values))
st['batch_rows'] = len(ex); st['batch_exact'] = f"{100*np.mean(ex):.1f}%"; st['batch_band'] = f"{100*np.mean(bd):.1f}%"
FL = json.load(open('x7_flow.json')); st['n_all'] = FL['design_site']; st['n_excl_op'] = FL['excl_operator']; st['n_excl_test'] = FL['excl_test_only']; st['n_users'] = int(L.user_id.nunique()); st['n_rows'] = int(len(L)); st['n_dis'] = len(DIS)
exc = sorted(set(R.disease) - set(DIS), key=nm); st['n_dis_all'] = int(R.disease.nunique())
st['exc_removed'] = '·'.join(nm(d) for d in exc if not ((R.disease == d) & (R.t >= B0) & (R.t < B1)).any())
st['n_exc'] = len(exc); st['exc_names'] = '·'.join(nm(d) for d in exc)
nsex = L.groupby('disease').user_id.nunique(); st['sex_dis'] = ', '.join(f"{nm(d)} {nsex[d]}명" for d in DIS if nsex[d] < len(u))
st['n_f'] = int((u.sex_b == 'F').sum()); st['n_m'] = int((u.sex_b == 'M').sum())
st['geno_added'] = int((u.comparable == '아니오').sum()); st['comparable'] = int((u.comparable == '예').sum())
st['batch_fu'] = int((u.fu_type != '개별 산출').sum()); st['ge180'] = int(((u.t_f.dt.normalize() - u.t_b.dt.normalize()).dt.days >= 180).sum())
kk = (u.t_b.dt.normalize() - u.d0).dt.days; st['base_before_reg'] = int((kk < 0).sum()); st['base_regday'] = int((kk == 0).sum()); st['base_in_window'] = int(((kk >= 1) & (kk <= 28)).sum()); st['base_after_window'] = int((kk > 28).sum()); st['base_not_first'] = int((u.first_seq != u.seq_b).sum())
st['bridge_pairs'] = int(len(BB)); st['bridge_users'] = int(BB.user_id.nunique()); st['bridge_bad'] = int(len(set(BB.user_id) & bad))
st['bridge_batch'] = int(((BB.t_n >= B0) & (BB.t_n < TS)).sum()); st['bridge_overlap'] = int(len(set(BB.user_id) & set(u.user_id)))
st['bridge_geno'] = int(BB.mode_o.astype(str).isin({'1', '4'}).sum()); st['miss_key'] = X8B['miss_key']
st['gap_med'] = f"{X8B['gap_days_median']:.1f}"; st['gap_iqr'] = f"{X8B['gap_days_q1']:.1f}~{X8B['gap_days_q3']:.1f}"; st['gap_max'] = f"{X8B['gap_days_max']:.0f}"
st['ident_lrs'] = f"{100*X8B['ident']['lrs']:.1f}%"; st['ident_prs'] = f"{100*X8B['ident']['prs']:.1f}%"; st['clip_n'] = int(sum(X8B['clip'].values()))
NP = pd.read_pickle('NP.pkl'); g = NP.groupby('score')
for c in SC: st[f'{c}_np'] = int(g.used.median()[c]); st[f'{c}_np_miss'] = int(g.dropped_missing.median()[c]); st[f'{c}_np_nogeno'] = int(g.dropped_nogeno.median()[c])
st['cov_irs'] = f"{100*X8B['cov']['irs']:.1f}%"; st['cov_mrs'] = f"{100*X8B['cov']['mrs']:.1f}%"
# follow-up table rank vs service rank
Lf = L.merge(u[['user_id', 'fu_type']], on='user_id'); nb = Lf.fu_type == '개별 산출'; ok = Lf.irs_r_f.notna()
st['fu_nonbatch_exact'] = f"{100*(Lf.irs_r_f[ok & nb] == Lf.irs_r_fs[ok & nb]).mean():.1f}%"
st['fu_batch_exact'] = f"{100*(Lf.irs_r_f[ok & ~nb] == Lf.irs_r_fs[ok & ~nb]).mean():.1f}%"; st['fu_batch_band'] = f"{100*(band(Lf.irs_r_f[ok & ~nb]) == band(Lf.irs_r_fs[ok & ~nb])).mean():.1f}%"
A = MET[MET.sex == 'all']; Sx = MET[MET.sex != 'all']
p = lambda v: f"{100*v:.1f}%"
for c in SC:
    a = A[A.score == c]
    st[f'{c}_raw'] = p(a.raw_rate.median()); st[f'{c}_cw'] = p(a.rate.median()); st[f'{c}_ind'] = p(a.ind_rate.median())
    st[f'{c}_kw_raw'] = f"{a.kw_raw.median():.3f}"; st[f'{c}_kw_cw'] = f"{a.kw_cw.median():.3f}"; st[f'{c}_k_cw'] = f"{a.k_cw.median():.3f}"
    st[f'{c}_pool_pass'] = int((a.rate >= .95).sum()); st[f'{c}_ndis'] = int(len(a))
    piv = Sx[Sx.score == c].pivot(index='disease', columns='sex', values='rate'); st[f'{c}_sex_pass'] = int((piv.fillna(1) >= .95).all(axis=1).sum())
    st[f'{c}_stable'] = int((a.pass_share >= .8).sum()); st[f'{c}_stable_pool'] = int((a.pass_share_pool >= .8).sum()); st[f'{c}_share_med'] = p(a.pass_share.median())
    st[f'{c}_raw_iqr'] = f"{p(a.raw_rate.median())} ({p(a.raw_rate.quantile(.25))}~{p(a.raw_rate.quantile(.75))})"; st[f'{c}_cw_iqr'] = f"{p(a.rate.median())} ({p(a.rate.quantile(.25))}~{p(a.rate.quantile(.75))})"
    st[f'{c}_cw_min'] = p(a.rate.min()); st[f'{c}_pairs'] = int(a.n_pairs.median())
    st[f'{c}_lower'] = p(a.to_lower.median()); st[f'{c}_higher'] = p(a.to_higher.median())
    st[f'{c}_rep_exact'] = p(REP.loc[c, 'exact_rate']); st[f'{c}_rep_band'] = p(REP.loc[c, 'same_rate'])
    okc = L[c + '_r_c'].notna()
    for alt, key in [('_r_full', 'full'), ('_r_clip', 'clip'), ('_r_noop', 'noop'), ('_r_meas', 'meas')]:  # alternatives are cross-fitted like the main conversion
        st[f'{c}_sens_{key}'] = p((band(L.loc[okc, c + '_r_c']) == band(L.loc[okc, c + alt])).mean())
    st[f'{c}_extrap'] = p(L.loc[okc, c + '_extrap'].mean()); st[f'{c}_cross'] = p((band(L.loc[okc, c + '_bs_lo']) != band(L.loc[okc, c + '_bs_hi'])).mean())
    st[f'{c}_gap'] = p((L.loc[okc, c + '_loc_c'] == '순위 사이 빈 구간').mean())
    gl = L.loc[okc & (L[c + '_loc_c'] == '순위 사이 빈 구간')]; st[f'{c}_gap_amb'] = p((band(gl[c + '_lo_c']) != band(gl[c + '_hi_c'])).sum() / okc.sum())
    st[f'{c}_out'] = p((L.loc[okc, c + '_loc_c'] == '범위 밖').mean())
st['irs_conv_rows'] = int(L.irs_r_c.notna().sum()); st['irs_noconv_rows'] = int((L.irs_r_b.notna() & L.irs_r_c.isna()).sum())
wk = A[A.score == 'irs'].sort_values('rate'); st['irs_weak'] = ', '.join(f"{nm(r.disease)} {p(r.rate)}" for r in wk.head(6).itertuples())
ws = Sx[Sx.score == 'irs'].nsmallest(3, 'rate'); st['irs_weak_sex'] = ', '.join(f"{nm(r.disease)}({'여' if r.sex == 'F' else '남'}) {p(r.rate)}" for r in ws.itertuples())
ht = A[(A.score == 'irs') & (A.disease == 'hypertension')].iloc[0]; st['htn_raw'] = p(ht.raw_rate); st['htn_cw'] = p(ht.rate)
C = CONF[CONF.score == 'irs'].groupby(['truth_band', 'conv_band']).n.sum().unstack(fill_value=0); st['pooled_irs'] = C.values.tolist()
st['pooled_irs_diag'] = p(np.trace(C.values) / C.values.sum()); st['pooled_irs_adj'] = p((np.trace(C.values) + sum(C.values[i, i + 1] + C.values[i + 1, i] for i in range(4))) / C.values.sum())
st['age_irs'] = f"{100*X8C['irs']['base']:.1f}% → {100*X8C['irs']['age']:.1f}%"; st['age_mrs'] = f"{100*X8C['mrs']['base']:.1f}% → {100*X8C['mrs']['age']:.1f}%"
st['age_better'] = X8C['irs']['better'] + X8C['mrs']['better']; st['age_worse'] = X8C['irs']['worse'] + X8C['mrs']['worse']
r = REPR.set_index('sex'); st['repr_age_bF'] = r.loc['F', 'age_bridge']; st['repr_age_aF'] = r.loc['F', 'age_anal']; st['repr_age_bM'] = r.loc['M', 'age_bridge']; st['repr_age_aM'] = r.loc['M', 'age_anal']
st['repr_meas'] = p((r.meas_bridge * r.bridge_pairs).sum() / r.bridge_pairs.sum())
st['sw'] = f"Python {platform.python_version()}, pandas {pd.__version__}, NumPy {np.__version__}, scikit-learn {sklearn.__version__}, openpyxl {openpyxl.__version__}"
st['flow_eligible_irs'] = int((L.irs_r_c.notna() & L.irs_r_fs.notna()).sum()); st['flow_eligible_mrs'] = int((L.mrs_r_c.notna() & L.mrs_r_fs.notna()).sum())
for c in SC:
    piv = Sx[Sx.score == c].pivot(index='disease', columns='sex', values='rate'); okd = set(piv.index[(piv.fillna(1) >= .95).all(axis=1)])
    el = L[c + '_r_c'].notna() & L[c + '_r_fs'].notna() & L.disease.isin(okd)
    if c in ('irs', 'prs'): el = el & L.user_id.map(dict(zip(u.user_id, u.comparable))).eq('예')
    st[f'{c}_elig_rows'] = int(el.sum()); st[f'{c}_sex_min'] = p(Sx[Sx.score == c].rate.min())
    aa = A[A.score == c]; st[f'{c}_pass_unstable'] = int(((aa.pass_share < .8) & aa.disease.isin(okd)).sum())
E = X8B
for k, v in E['dist'].items(): st['dist_' + k] = v
for k, v in E['byage'].items():
    c, g = k.split('|'); st[f'age_{c}_{["50세 미만", "50~64세", "65세 이상"].index(g)}'] = p(v['rate'])
st['sex_mismatch'] = E['sex_mismatch']
ox = MET[(MET.disease == 'osteoporosis') & (MET.score == 'irs')].set_index('sex').rate
st['ex_pool'] = p(ox['all']); st['ex_f'] = p(ox['F']); st['ex_m'] = p(ox['M'])
st['abstract'] = (f"모델 교체(2026-07-01 10:00)를 사이에 둔 IRS 위험 순위를 같은 척도에서 비교하기 위한 환산 방법을 기술한다. 교체 직전과 직후에 같은 사용자가 같은 입력으로 산출받은 연결 쌍 {st['bridge_pairs']}개로 "
                  f"질환·점수·성별마다 이전 모델 값을 7월 모델 값으로 바꾸는 단조 함수를 만들고, 안정기 산출 {st['ref_calcs']:,}건의 순위기준표로 순위를 부여했다. 사용자 단위 교차검증에서 같은 20순위 구간에 들어간 비율의 질환별 중앙값은 "
                  f"IRS {st['irs_raw']}→{st['irs_cw']}, MRS {st['mrs_raw']}→{st['mrs_cw']}였고, 성별 모두 95% 이상인 질환은 IRS {st['irs_sex_pass']}개, MRS {st['mrs_sex_pass']}개였다. 다만 기준 근처의 판정은 재표집에서 불안정했다. 작성일 2026-11-19.")
json.dump(st, open('stats.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(st, ensure_ascii=False)[:3000])
