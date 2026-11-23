import pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
B0=pd.Timestamp('2026-07-01 10:00'); TS=pd.Timestamp('2026-07-01 15:00'); B1=pd.Timestamp('2026-08-02')
I=pd.read_pickle('I.pkl'); inp=['mode','med_h','life_h','geno_h','sex','age']; I['key']=I[inp].fillna('x').astype(str).agg('|'.join,axis=1)
isint=lambda s: s.notna()&(np.abs(s-np.round(s))<1e-9)
for c in ['sbp','dbp','fbg']: I[c+'n']=pd.to_numeric(I[c],errors='coerce')
I['meas']=isint(I.sbpn)&isint(I.dbpn)&isint(I.fbgn); I['d']=I.t.dt.normalize()
I['per']=np.where(I.t<B0,'P0',np.where(I.t<B1,'P1','later'))
I=I.sort_values(['user_id','t','seq'])
U=pd.read_csv('users.csv')
for c in ['is_operator','in_test_group']: U[c]=U[c]=='t'
U['site']=np.where(U.site_a_linked.notna(),'A',np.where(U.site_b_linked.notna(),'B','none')); coh=set(U[(U.site!='none')&~U.is_operator&~U.in_test_group].user_id)
H=I[I.meas]
pick=lambda df,keys,keep: df.sort_values(['t','seq']).drop_duplicates(keys,keep=keep).set_index(keys)  # whole-row selection
base=pick(H[H.per=='P0'],'user_id','first'); F=pick(H[H.per=='P1'],'user_id','last')
J=base.join(F,lsuffix='_b',rsuffix='_f',how='inner'); J['gap']=(J.d_f-J.d_b).dt.days
D=J[J.gap>=90].copy(); print('design B90 (boundary 7/1 10:00): all',len(D),'cohort',D.index.isin(coh).sum())
old=pd.read_csv('designB90.csv').set_index('user_id'); Dc=D[D.index.isin(coh)]
print('vs previous design (designB90.csv): same users',len(set(Dc.index)&set(old.index)&coh),'| changed follow-up seq',(Dc.seq_f!=old.reindex(Dc.index).seq_f).sum(),'| changed baseline',(Dc.seq_b!=old.reindex(Dc.index).seq_b).sum())
print('180d cohort', (Dc.gap>=180).sum(), '| modes', (Dc.mode_b.astype(str)+'→'+Dc.mode_f.astype(str)).value_counts().to_dict())
print('follow-up in 7/1 10-15h batch',((Dc.t_f>=B0)&(Dc.t_f<TS)).sum())
# bridge pairs
A=pick(I[I.per=='P0'],['user_id','key'],'last'); Bn=pick(I[I.per=='P1'],['user_id','key'],'first')
BB=A.join(Bn,lsuffix='_o',rsuffix='_n',how='inner').reset_index(); print('bridge pairs',len(BB),'users',BB.user_id.nunique(),'| new side in batch',((BB.t_n>=B0)&(BB.t_n<TS)).sum())
need=set(Dc.seq_b)|set(Dc.seq_f)|set(BB.seq_o)|set(BB.seq_n)
have=set(pd.read_csv('res_b.csv',usecols=['seq']).seq)|set(pd.read_csv('res_p1.csv',usecols=['seq']).seq)
miss=need-have; print('seqs needed',len(need),'missing',len(miss)); open('seqs_miss.txt','w').write(','.join(map(str,sorted(miss))))
import json as _j
_site = set(U[U.site != 'none'].user_id); _op = set(U[U.is_operator].user_id); _te = set(U[U.in_test_group].user_id)
_all = set(D.index); _s = _all & _site
_j.dump(dict(design_all=len(_all), design_site=len(_s), excl_operator=len(_s & _op), excl_test_only=len((_s & _te) - _op), final=len(Dc), excl_nosite=len(_all - _site)), open('x7_flow.json', 'w'))
print('flow', open('x7_flow.json').read())
Dc.to_pickle('D_final.pkl'); BB.to_pickle('BB_final.pkl'); I.to_pickle('I_final.pkl')
