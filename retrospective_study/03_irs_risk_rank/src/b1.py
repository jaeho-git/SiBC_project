import pandas as pd, numpy as np
I=pd.read_pickle('I.pkl')
U=pd.read_csv('users.csv')
for c in ['is_operator','in_test_group']: U[c]=U[c]=='t'
U['site']=np.where(U.site_a_linked.notna(),'A',np.where(U.site_b_linked.notna(),'B','none')); coh=set(U[(U.site!='none')&~U.is_operator&~U.in_test_group].user_id)
I['per']=np.select([I.t<'2026-07-01',I.t<'2026-08-02',I.t<'2026-08-26',I.t<'2026-09-06',I.t<'2026-09-16'],['P0','P1','P2','P3','P4'],'P5')
isint=lambda s: s.notna()&(np.abs(s-np.round(s))<1e-9)
for c in ['sbp','dbp','fbg']: I[c+'n']=pd.to_numeric(I[c],errors='coerce')
I['meas']=isint(I.sbpn)&isint(I.dbpn)&isint(I.fbgn); I['d']=I.t.dt.normalize()
H=I[I.meas]  # no disease filter
base=H[H.per=='P0'].groupby('user_id').first(); F=H[H.per=='P1'].groupby('user_id').last(); J=base.join(F,lsuffix='_b',rsuffix='_f',how='inner'); sp=(J.d_f-J.d_b).dt.days
for th in [90,180]:
    ids=sp[sp>=th].index; print(f'design B, no disease filter, {th}d: all {len(ids)} cohort {len(set(ids)&coh)} | modes', (J.loc[ids].mode_b+'→'+J.loc[ids].mode_f).value_counts().to_dict())
ids=sp[sp>=90].index; seqs=set(J.loc[ids].seq_b)|set(J.loc[ids].seq_f)
inp=['mode','med_h','life_h','geno_h','sex','age']; I['key']=I[inp].fillna('x').agg('|'.join,axis=1)
A=I[I.per=='P0'].groupby(['user_id','key']).last(); B=I[I.per=='P1'].groupby(['user_id','key']).first(); BB=A.join(B,lsuffix='_o',rsuffix='_n',how='inner').reset_index()
seqs|=set(BB.seq_o)|set(BB.seq_n)
open('seqs_b.txt','w').write(','.join(str(int(s)) for s in seqs)); print('seqs to fetch',len(seqs),'bridge pairs',len(BB))
J.loc[ids,['seq_b','seq_f','mode_b','mode_f','sex_b']].to_csv('designB90.csv'); BB[['user_id','seq_o','seq_n','sex_o']].to_csv('bridgeB.csv',index=False)
J.loc[sp[sp>=180].index,['seq_b','seq_f']].to_csv('designB180.csv')
