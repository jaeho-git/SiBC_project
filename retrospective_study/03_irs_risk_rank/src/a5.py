import pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width',250); pd.set_option('display.max_columns',40); pd.set_option('display.max_rows',200)
I=pd.read_csv('irs_full.csv',dtype=str); I['seq']=I.seq.astype(int)
I['t']=pd.to_datetime(I.create_date,utc=True).dt.tz_convert('Asia/Seoul').dt.tz_localize(None); I=I.sort_values(['user_id','seq'])
for c in ['irs_p','mrs_p','lrs_p','prs_p','irs_r','mrs_r','lrs_r','prs_r']: I[c+'n']=pd.to_numeric(I[c],errors='coerce')
print('versions:', I.ver.fillna('null').value_counts().to_dict(), '| aver', I.aver.fillna('null').value_counts().to_dict(), '| ever', I.ever.fillna('null').value_counts().to_dict())
inp=['mode','med_h','life_h','geno_h','sex','age']
for c in inp+['ver','irs_p','mrs_p','lrs_p','prs_p','irs_r','mrs_r','lrs_r','prs_r','t']: I['p_'+c]=I.groupby('user_id')[c].shift()
same=I[I.p_mode.notna()].copy()
same=same[np.logical_and.reduce([(same[c].fillna('x')==same['p_'+c].fillna('x')) for c in inp])]
for c in ['irs','mrs','lrs','prs']:
    same[c+'_pch']=same[c+'_p'].fillna('x')!=same['p_'+c+'_p'].fillna('x'); same[c+'_rch']=same[c+'_r'].fillna('x')!=same['p_'+c+'_r'].fillna('x')
same['day']=same.t.dt.normalize()
ch=same[same.irs_rch|same.mrs_rch|same.lrs_rch|same.irs_pch|same.mrs_pch|same.lrs_pch]
print('same-input consecutive pairs',len(same),'| any hypertension prob/rank change',len(ch))
print('change by day (first 40):'); g=ch.groupby('day').agg(n=('seq','size'),mrs_p=('mrs_pch','sum'),mrs_r=('mrs_rch','sum'),lrs_p=('lrs_pch','sum'),lrs_r=('lrs_rch','sum'),irs_p=('irs_pch','sum'),irs_r=('irs_rch','sum'),prs_p=('prs_pch','sum'),prs_r=('prs_rch','sum')); print(g.head(60))
# total same-input pairs per day around change days to see if all pairs changed (regime switch) or sporadic
tot=same.groupby('day').size(); g2=pd.DataFrame({'pairs':tot,'changed':ch.groupby('day').size()}).fillna(0); print(g2[g2.changed>0])
same.to_pickle('same.pkl'); I.to_pickle('I.pkl')
