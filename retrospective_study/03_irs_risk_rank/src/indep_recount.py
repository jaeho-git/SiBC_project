# Independent recount of the comparison-set design from a fresh DB extraction (different code path: vectorized merges).
# Input contract (see sql/indep_cohort.sql, sql/indep_calcs.sql): d0 and wd are KST dates cut in SQL; t is KST local time; is_op/is_test are SQL booleans;
# life_ok = lifestyleLog is a non-empty JSON object; checkup values are the 14 raw medicalRecord keys; gh = md5 of the genotypes JSON text (NULL when absent).
import pandas as pd, numpy as np, sys
D = sys.argv[1]
END = pd.Timestamp('2026-11-17'); SWITCH = pd.Timestamp('2026-07-01 10:00'); NEXT = pd.Timestamp('2026-08-02')
C = pd.read_csv(f'{D}/cohort.csv', parse_dates=['d0', 'wd'])
C['is_op'] = C.is_op.astype(str).str.lower().isin(['t', 'true']); C['is_test'] = C.is_test.astype(str).str.lower().isin(['t', 'true'])
step = {'site': len(C)}
C = C[~C.is_op & ~C.is_test]; step['non_operator'] = len(C)
C = C[C.d0.notna()]; step['with_login'] = len(C)
C = C[(C.d0 + pd.Timedelta(days=28) <= END) & ~(C.wd.notna() & (C.wd <= C.d0 + pd.Timedelta(days=28)))]; step['common'] = len(C)
K = pd.read_csv(f'{D}/calcs.csv', dtype=str)
assert K.seq.is_unique and C.user_id.is_unique, 'duplicate keys'
K['seq'] = K.seq.astype(int); K['t'] = pd.to_datetime(K.t); K['day'] = K.t.dt.floor('D')
num = ['sbp', 'dbp', 'fbg', 'tc', 'hdl', 'tg', 'wt', 'ht', 'waist', 'hb', 'ast', 'alt', 'gtp', 'cr']
for c in num: K[c] = pd.to_numeric(K[c], errors='coerce')
integer = lambda v: v.notna() & (v == v.round())
K['measured'] = integer(K.sbp) & integer(K.dbp) & integer(K.fbg)
K['genome'] = K['mode'].isin(['1', '4']); K['life_ok'] = K.life_ok.astype(str).str.lower().isin(['t', 'true'])
K['complete'] = K.genome & K.measured & K.life_ok
K = K[K.user_id.isin(C.user_id)].merge(C[['user_id', 'd0']], on='user_id')
K['k'] = (K.day - K.d0).dt.days
comp = K[K.complete].sort_values(['user_id', 't', 'seq'])
step['complete'] = comp.user_id.nunique()
base = comp[(comp.k >= 0) & (comp.k <= 56)].groupby('user_id', as_index=False).head(1)   # window first, then earliest (whole row)
step['within56'] = len(base)
base = base[base.t < SWITCH]; step['pre_july'] = len(base)
m = comp.merge(base[['user_id', 'seq', 'day', 'gh'] + num].rename(columns={'seq': 'bseq', 'day': 'bday', 'gh': 'bgh', **{c: 'b_' + c for c in num}}), on='user_id')
m = m[((m.day - m.bday).dt.days >= 90)]
has90 = set(m.user_id)
geno_ok = m.gh.notna() & m.bgh.notna() & (m.gh == m.bgh); step['genotype_unverifiable_or_differs'] = len(has90 - set(m[geno_ok].user_id)); m = m[geno_ok]; hasgeno = set(m.user_id)
diff = np.zeros(len(m), bool)
for c in num:
    a, b = m[c].values, m['b_' + c].values
    diff |= np.isfinite(a) & np.isfinite(b) & (np.abs(a - b) > 1e-9)
m = m[diff]; hasnew = set(m.user_id)
m = m[m.t < NEXT].sort_values(['user_id', 't', 'seq'])
fu = m.groupby('user_id', as_index=False).head(1)
step['no_calc_90d'] = len(set(base.user_id) - has90); step['no_new_checkup'] = len(hasgeno - hasnew); step['only_after_aug1'] = len(hasnew - set(fu.user_id)); step['final'] = len(fu)
fu[['user_id', 'bseq', 'seq']].rename(columns={'seq': 'fseq'}).to_csv(f'{D}/recount_users.csv', index=False)
print(step)
