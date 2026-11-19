# -*- coding: utf-8 -*-
"""All numbers quoted in the v4 workbook guide and methods document (comparison-set design) -> stats2.json."""
from xwlib import *
import json, platform, sklearn, openpyxl
from scipy.stats import norm
from scipy.optimize import brentq
R, I, D_old, BB = load(); REF = pd.read_pickle('REF.pkl'); DIS = pd.read_pickle('DIS.pkl')
D = pd.read_pickle('D2.pkl'); L = pd.read_pickle('L2.pkl'); MET = pd.read_pickle('MET.pkl'); CONF = pd.read_pickle('CONF.pkl'); REP = pd.read_pickle('REP.pkl')
X8B = json.load(open('x8b_extra.json')); X8C = json.load(open('x8c.json')); FL = json.load(open('x7b_flow.json')); OBJ = json.load(open('x7b_onboard.json')); ALT = json.load(open('x7b_alt.json'))
old = json.load(open('stats.json'))                     # bridge-level validation numbers (independent of the analysed cohort)
info = pd.read_csv('dis_info.csv').set_index('disease_id')
EXTRA_NM = {"cardiac_arrhythmia": "부정맥", "endometrial_cancer": "자궁내막암", "endometriosis": "자궁내막증", "polycystic_ovary_syndrome": "다낭성 난소 증후군"}
nm = lambda d: info.disease_nm.get(d, EXTRA_NM.get(d, d)); p = lambda v: f"{100*v:.1f}%"
q3 = lambda v: f"{v.median():.0f}({v.quantile(.25):.0f}~{v.quantile(.75):.0f})"
st = {k: old[k] for k in ['log_calcs', 'log_users', 'log_from', 'log_to', 'p0_calcs', 'p1_calcs', 'ref_calcs', 'ref_tables', 'ref_inv', 'early_calcs', 'batch_calcs', 'batch_users',
                          'batch_rows', 'batch_exact', 'batch_band', 'n_dis', 'n_exc', 'exc_names', 'exc_removed', 'bridge_pairs', 'bridge_users', 'bridge_bad', 'bridge_batch',
                          'bridge_geno', 'miss_key', 'gap_med', 'gap_iqr', 'gap_max', 'ident_lrs', 'ident_prs', 'clip_n', 'irs_np', 'mrs_np', 'lrs_np', 'prs_np', 'mrs_np_miss',
                          'pooled_irs', 'pooled_irs_diag', 'pooled_irs_adj', 'age_irs', 'age_mrs', 'htn_raw', 'htn_cw', 'irs_sex_min', 'ex_pool', 'ex_f', 'ex_m', 'sw',
                          'age_irs_0', 'age_irs_1', 'age_irs_2'] + [f'{c}_{k}' for c in SC for k in ['raw', 'cw', 'ind', 'kw_raw', 'kw_cw', 'raw_iqr', 'cw_iqr', 'sex_pass', 'pool_pass',
                          'stable', 'pass_unstable', 'lower', 'higher', 'rep_band', 'rep_exact']] if k in old}
st['sw'] = f"Python {platform.python_version()}, pandas {pd.__version__}, NumPy {np.__version__}, scikit-learn {sklearn.__version__}, openpyxl {openpyxl.__version__}"
st.update({f'flow_{k}': v for k, v in FL.items()})
# onboarding (common cohort) and alternative designs, from x7b.py
for c in ['meas', 'geno', 'comp']:
    o = OBJ[c]; st[f'ob_{c}_n'] = o['n']; st[f'ob_{c}_med'] = f"{o['med']:.0f}"; st[f'ob_{c}_q75'] = f"{o['q75']:.0f}"; st[f'ob_{c}_q90'] = f"{o['q90']:.0f}"
    st[f'ob_{c}_28'] = o['w28']; st[f'ob_{c}_56'] = o['w56']; st[f'ob_{c}_90'] = o['w90']
st['ob_comp_56_share'] = p(OBJ['comp']['w56'] / OBJ['comp']['n']); st['ob_comp_56_share_all'] = p(OBJ['comp']['w56'] / FL['common_cohort'])
st['n_w28'] = ALT['w28']; st['n_w90'] = ALT['w90']; st['n_w56_rescore'] = ALT['rescore']; st['n_nochange'] = ALT['no_change_required']; st['n_rescore_nochange'] = ALT['rescore_no_change']
# cohort
st['n'] = len(D); st['n_f'] = int((D.sex == 'F').sum()); st['n_m'] = int((D.sex == 'M').sum()); st['age'] = q3(D.age_b)
st['k_b'] = q3(D.k_b); st['k_b0'] = int((D.k_b == 0).sum()); st['k_b28'] = int((D.k_b <= 28).sum())
st['gap'] = q3(D.gap); st['ge180'] = int((D.gap >= 180).sum())
st['n_p1'] = int((D.model_f == 'P1').sum()); st['n_p0'] = int((D.model_f == 'P0').sum())
st['n_batch'] = int(((D.t_f >= B0) & (D.t_f < TS)).sum())
st['life_ch'] = int((D.life_ch == '예').sum()); st['core_ch'] = q3(D.n_core_changed)
st['act28'] = q3(D.act28); st['act_pre'] = q3(D.act_pre); st['act28_med'] = f"{D.act28.median():.0f}"
st['n_rows'] = len(L); st['first_not_base'] = int((D.first_seq != D.seq_b).sum())
st['bridge_overlap'] = int(len(set(BB.user_id) & set(D.index))); st['bridge_overlap_p1'] = int(len(set(BB.user_id) & set(D.index[D.model_f == 'P1']))); st['bridge_overlap_p0'] = st['bridge_overlap'] - st['bridge_overlap_p1']
st['sex_mismatch'] = int((D.sex != D.sex_f).sum())
# conversion diagnostics (P1 rows)
P1 = L.model_f == 'P1'
for c in SC:
    ok = L[c + '_r_c'].notna() & P1
    st[f'{c}_conv_rows'] = int(ok.sum()); st[f'{c}_extrap'] = p(L.loc[ok, c + '_extrap'].mean())
    st[f'{c}_cross'] = p((band(L.loc[ok, c + '_bs_lo']) != band(L.loc[ok, c + '_bs_hi'])).mean())
    gl = L.loc[ok & (L[c + '_loc_c'] == '순위 사이 빈 구간')]; st[f'{c}_gap_amb'] = p((band(gl[c + '_lo_c']) != band(gl[c + '_hi_c'])).sum() / ok.sum())
    for alt, key in [('_r_full', 'full'), ('_r_clip', 'clip'), ('_r_noop', 'noop'), ('_r_meas', 'meas')]:
        st[f'{c}_sens_{key}'] = p((band(L.loc[ok, c + '_r_c']) == band(L.loc[ok, c + alt])).mean())
sm = (L.model_f == 'P0') & L.irs_r_c.notna() & L.irs_r_fs.notna() & L.irs_rj_b.notna() & L.irs_rj_f.notna()
st['same_model_rows'] = int(sm.sum())
st['same_model_dir'] = p((np.sign(band(L.irs_r_fs[sm]) - band(L.irs_r_c[sm])) == np.sign(band(L.irs_rj_f[sm]) - band(L.irs_rj_b[sm]))).mean())
cov = {c: 1 - L.loc[L[c + '_r_c'].notna() & P1, c + '_extrap'].mean() for c in SC}; st['cov_irs'] = p(cov['irs']); st['cov_mrs'] = p(cov['mrs'])
# representativeness: bridge vs analysed
Ii = I.set_index('seq'); sbp = pd.to_numeric(Ii.sbp, errors='coerce')
st['repr_age_bridge'] = q3(pd.to_numeric(Ii.loc[BB.seq_o, 'age'], errors='coerce')); st['repr_age_anal'] = q3(D.age_b)
st['repr_sbp_bridge'] = q3(sbp.reindex(BB.seq_o).dropna()); st['repr_sbp_anal'] = q3(sbp.reindex(D.seq_b).dropna())
Rr = R.set_index('seq')
for c in ['irs', 'mrs']:
    st[f'repr_{c}_bridge'] = q3(pd.to_numeric(Rr.loc[Rr.index.isin(BB.seq_o), c + '_rn'], errors='coerce').dropna())
    st[f'repr_{c}_anal'] = q3(pd.to_numeric(Rr.loc[Rr.index.isin(D.seq_b), c + '_rn'], errors='coerce').dropna())
st['repr_geno_bridge'] = p(BB.seq_o.map(Ii['mode'].astype(str)).isin({'1', '4'}).mean()); st['repr_meas_bridge'] = p(BB.seq_o.map(Ii.meas).astype(bool).mean())
# validated disease sets (per-sex rule)
Sx = MET[MET.sex != 'all']; A = MET[MET.sex == 'all']
PASS = {c: set(Sx[Sx.score == c].pivot(index='disease', columns='sex', values='rate').pipe(lambda q: q.index[(q.fillna(1) >= .95).all(axis=1)])) for c in SC}
pd.to_pickle(PASS, 'PASS.pkl')
for c in SC: st[f'{c}_pass_names'] = ', '.join(sorted(nm(d) for d in PASS[c]))
# blinded sample-adequacy analysis (IRS primary)
za, zb = norm.ppf(.975), norm.ppf(.8)
def power2p(p1, p2, n1, n2):
    pb = (p1 * n1 + p2 * n2) / (n1 + n2); se0 = np.sqrt(pb * (1 - pb) * (1 / n1 + 1 / n2)); se1 = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return norm.cdf((abs(p2 - p1) - za * se0) / se1)
def mdd(pbar, n1, n2): return brentq(lambda d: power2p(pbar - d / 2, pbar + d / 2, n1, n2) - 0.8, 1e-4, min(2 * pbar, 2 * (1 - pbar)) - 1e-4)
hi = int((D.act28 >= D.act28.median()).sum()); lo = len(D) - hi; st['grp_hi'] = hi; st['grp_lo'] = lo
for c in ['irs', 'mrs']:
    e = L[L.disease.isin(PASS[c]) & L[c + '_r_c'].notna() & L[c + '_r_fs'].notna()].copy()
    e['bb'] = band(e[c + '_r_c']); e['bf'] = band(e[c + '_r_fs']); e = e[e.bb > 0]; e['down'] = (e.bf < e.bb).astype(int)
    pr = e.groupby('disease').down.mean(); nper = e.groupby('disease').user_id.nunique()
    st[f'{c}_ad_ndis'] = int(e.disease.nunique()); st[f'{c}_ad_nper'] = f"{int(nper.median())}({int(nper.min())}~{int(nper.max())})"
    st[f'{c}_ad_rate'] = f"{p(pr.median())}({p(pr.min())}~{p(pr.max())})"; st[f'{c}_ad_rows'] = int(len(e)); st[f'{c}_ad_events'] = int(e.down.sum())
    ul = e.groupby('user_id').down.agg(['mean', 'size']); st[f'{c}_ad_users'] = int(len(ul)); st[f'{c}_ad_umean'] = p(ul['mean'].mean()); st[f'{c}_ad_usd'] = f"{ul['mean'].std():.3f}"
    st[f'{c}_ad_kper'] = f"{ul['size'].median():.0f}"
    g = e.groupby('user_id').down; n_i = g.size(); k0 = (n_i.sum() - (n_i ** 2).sum() / n_i.sum()) / (len(n_i) - 1)
    msb = (n_i * (g.mean() - e.down.mean()) ** 2).sum() / (len(n_i) - 1); msw = ((e.down - e.user_id.map(g.mean())) ** 2).sum() / (n_i.sum() - len(n_i))
    icc = (msb - msw) / (msb + (k0 - 1) * msw); st[f'{c}_ad_icc'] = f"{icc:.2f}"
    m = len(e) / len(ul); de = 1 + (m - 1) * icc; mi = ul['size'].values; de2 = 1 + ((mi ** 2).sum() / mi.sum() - 1) * icc
    st[f'{c}_ad_de2'] = f"{de2:.1f}"; neff2 = len(e) / de2; st[f'{c}_ad_neff2'] = f"{neff2:.0f}"
    neff = len(e) / de; pbar = e.down.mean(); dd = mdd(pbar, neff / 2, neff / 2); st[f'{c}_ad_mdd_rows2'] = f"{100*mdd(pbar, neff2/2, neff2/2):.1f}%p"
    st[f'{c}_ad_de'] = f"{de:.1f}"; st[f'{c}_ad_neff'] = f"{neff:.0f}"; st[f'{c}_ad_mdd_rows'] = f"{100*dd:.1f}%p"
    dstd = (za + zb) * np.sqrt(1 / (len(ul) * hi / len(D)) + 1 / (len(ul) * lo / len(D))); st[f'{c}_ad_dstd'] = f"{dstd:.2f}"; st[f'{c}_ad_mdd_user'] = f"{100*dstd*ul['mean'].std():.1f}%p"
    if c == 'irs':
        h = e[e.disease == 'hypertension']; n = h.user_id.nunique(); ph = h.down.mean(); ev = int(h.down.sum())
        st['ad_htn_n'] = n; st['ad_htn_rate'] = p(ph); st['ad_htn_events'] = ev; st['ad_htn_mdd'] = f"{100*mdd(ph, n*hi/len(D), n*lo/len(D)):.1f}%p"
        st['ad_htn_pow'] = f"{power2p(.20, .35, n*hi/len(D), n*lo/len(D)):.2f}"; st['ad_htn_epv'] = ev // 10
        typ = int(nper.median()); ptyp = float(pr.median()); st['ad_typ_mdd'] = f"{100*mdd(ptyp, typ*hi/len(D), typ*lo/len(D)):.1f}%p"; st['ad_typ_events'] = int(round(typ * ptyp))
Lf = L.merge(D[['t_f']].reset_index(), on='user_id'); okf = (Lf.model_f == 'P1') & Lf.irs_r_f.notna(); bt = (Lf.t_f >= B0) & (Lf.t_f < TS)
st['fu_nonbatch_exact'] = p((Lf.irs_r_f[okf & ~bt] == Lf.irs_r_fs[okf & ~bt]).mean()); st['fu_batch_exact'] = p((Lf.irs_r_f[okf & bt] == Lf.irs_r_fs[okf & bt]).mean())
st['fu_batch_band'] = p((band(Lf.irs_r_f[okf & bt]) == band(Lf.irs_r_fs[okf & bt])).mean())
eall = L[L.disease.isin(PASS['irs']) & L.irs_r_c.notna() & L.irs_r_fs.notna()].copy(); eall['down'] = band(eall.irs_r_fs) < band(eall.irs_r_c)
st['irs_umean_all'] = p(eall.groupby('user_id').down.mean().mean())
sm_ = L[(L.model_f == 'P0') & L.disease.isin(PASS['irs'])].copy()
def ushare(df, b, f):
    q = df[df[b].notna() & df[f].notna()].copy(); q = q[band(q[b]) > 0]; q['down'] = band(q[f]) < band(q[b]); return q.groupby('user_id').down.agg(['size', 'mean'])
a0 = ushare(sm_, 'irs_r_c', 'irs_r_fs'); a1 = ushare(sm_, 'irs_rj_b', 'irs_rj_f'); J = a0.join(a1, lsuffix='_p0', rsuffix='_jul', how='outer')
dif = (J.mean_jul - J.mean_p0); st['sm_users'] = int(len(J)); st['sm_same_share'] = int((dif.abs() < 1e-12).sum()); st['sm_dif'] = f"{100*dif.median():.1f}%p({100*dif.quantile(.25):.1f}~{100*dif.quantile(.75):.1f})"
st['sm_dif_max'] = f"{100*dif.abs().max():.1f}%p"; st['sm_den_changed'] = int((J.size_p0 != J.size_jul).sum())
st['sm_mean_p0'] = p(J.mean_p0.mean()); st['sm_mean_jul'] = p(J.mean_jul.mean())
st['n_dis_f'] = int(len([d for d in PASS['irs'] if L[(L.disease == d) & (L.sex == 'F')].shape[0] > 0])); st['n_dis_m'] = int(len([d for d in PASS['irs'] if L[(L.disease == d) & (L.sex == 'M')].shape[0] > 0]))
for k_ in ['excl_no_irs', 'excl_no_complete', 'excl_after_window', 'excl_post_july_baseline']: st['flow_' + k_] = FL[k_]
st['abstract'] = (f"모델 교체(2026-07-01 10:00)를 사이에 둔 IRS 위험 순위를 같은 척도에서 비교하기 위한 기준선 정의와 환산 방법을 기술한다. 기준선은 앱 등록 후 56일 이내의 첫 완성 IRS(유전·의학·생활습관 점수를 모두 포함)로 정하고, "
                  f"분석 시작점을 기준선 날짜에 두었다. 대상은 {st['n']}명이며, {st['n_p1']}명은 교체 전후 같은 입력의 연결 쌍 {st['bridge_pairs']}개로 만든 단조 환산과 안정기 순위기준표로 두 시점을 하나의 척도에 놓았고, "
                  f"{st['n_p0']}명은 같은 모델끼리 비교했다. 환산의 질환별 구간 일치율 중앙값은 IRS {st['irs_raw']}→{st['irs_cw']}였고, 성별 모두 95% 이상인 IRS 질환은 {st['irs_sex_pass']}개였다. 작성일 2026-11-19.")
json.dump(st, open('stats2.json', 'w'), ensure_ascii=False, indent=1)
for k in ['flow_final', 'n_f', 'n_m', 'age', 'k_b', 'k_b0', 'gap', 'ge180', 'n_p1', 'n_p0', 'n_batch', 'life_ch', 'core_ch', 'act28', 'act_pre', 'n_rows', 'first_not_base', 'bridge_overlap',
          'irs_extrap', 'irs_cross', 'irs_sens_full', 'irs_sens_noop', 'same_model_dir', 'cov_irs', 'repr_age_bridge', 'repr_age_anal', 'repr_sbp_bridge', 'repr_sbp_anal', 'repr_irs_bridge', 'repr_irs_anal',
          'irs_ad_ndis', 'irs_ad_nper', 'irs_ad_rate', 'irs_ad_rows', 'irs_ad_events', 'irs_ad_users', 'irs_ad_umean', 'irs_ad_usd', 'irs_ad_icc', 'irs_ad_de', 'irs_ad_neff', 'irs_ad_mdd_rows',
          'irs_ad_dstd', 'irs_ad_mdd_user', 'ad_htn_n', 'ad_htn_rate', 'ad_htn_events', 'ad_htn_mdd', 'ad_htn_pow', 'ad_typ_mdd', 'grp_hi', 'grp_lo', 'n_w28', 'n_w90', 'n_w56_rescore']: print(k, '=', st[k])
