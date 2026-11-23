import pandas as pd, numpy as np, json
END=pd.Timestamp('2026-11-17'); B0=pd.Timestamp('2026-07-01 10:00'); TS=pd.Timestamp('2026-07-01 15:00')
I=pd.read_pickle('I_final.pkl'); D=pd.read_pickle('D_final.pkl').reset_index(); L=pd.read_pickle('L.pkl')
U=pd.read_csv('users.csv'); U['site']=np.where(U.site_a_linked.notna(),'A',np.where(U.site_b_linked.notna(),'B',''))
Lg=pd.read_csv('login.csv',parse_dates=['d'])[['user_id','d']].drop_duplicates()
first=I.sort_values(['t','seq']).drop_duplicates('user_id',keep='first').set_index('user_id')[['seq','t']]
D=D.sort_values(['t_b','user_id']).reset_index(drop=True); D['sid']=['S%03d'%(i+1) for i in range(len(D))]
u=D.merge(U[['user_id','site','withdraw_dt']],on='user_id',how='left')
d0=Lg.groupby('user_id').d.min(); u['d0']=u.user_id.map(d0)
u['wd']=pd.to_datetime(u.withdraw_dt,utc=True).dt.tz_convert('Asia/Seoul').dt.tz_localize(None)
u['common']=np.where(u.d0.notna()&(u.d0+pd.Timedelta(days=28)<=END)&~(u.wd<=u.d0+pd.Timedelta(days=28)),'예','아니오')
x=Lg.merge(u[['user_id','d0','d_b','d_f']],on='user_id'); k=(x.d-x.d0).dt.days
a28=x[(k>=1)&(k<=28)].groupby('user_id').size(); u['act28']=np.where(u.d0.notna(),u.user_id.map(a28).fillna(0),np.nan)
bt=x[(x.d>x.d_b)&(x.d<=x.d_f)].groupby('user_id').size(); u['ldays']=u.user_id.map(bt).fillna(0)
u['first_t']=u.user_id.map(first.t); u['first_seq']=u.user_id.map(first.seq)
u['fu_type']=np.where((u.t_f>=B0)&(u.t_f<TS),'7/1 일괄 산출(10~15시)','개별 산출')
u['med_ch']=np.where(u.med_h_b!=u.med_h_f,'예','아니오'); u['life_ch']=np.where(u.life_h_b!=u.life_h_f,'예','아니오')
u['sex_k']=u.sex_b.map({'M':'남','F':'여'})
GENO={'1','4'}
u['geno_b']=np.where(u.mode_b.astype(str).isin(GENO),'포함','없음'); u['geno_f']=np.where(u.mode_f.astype(str).isin(GENO),'포함','없음')
u['mode_tr']=u.mode_b.astype(str)+'→'+u.mode_f.astype(str)
u['geno_ch']=np.where((u.geno_b=='포함')&(u.geno_f=='포함'),np.where(u.geno_h_b.astype(str)!=u.geno_h_f.astype(str),'예','아니오'),np.where(u.geno_b!=u.geno_f,'유전체 추가·삭제','해당 없음'))
u['comparable']=np.where((u.mode_b.astype(str)==u.mode_f.astype(str))&(u.geno_ch.isin(['아니오','해당 없음'])),'예','아니오')
u['sex_ok']=np.where(u.sex_b==u.sex_f,'예','아니오')
BB=pd.read_pickle('BB_final.pkl'); u['in_bridge']=np.where(u.user_id.isin(set(BB.user_id)),'예','아니오')
for c in ['age_b','age_f','mode_b','mode_f']: u[c]=pd.to_numeric(u[c],errors='coerce')
print(u[['sid','site','common','act28','ldays','fu_type','med_ch','life_ch']].describe(include='all').T[['count','unique','top','freq','mean']])
# checkup inputs
X=pd.read_csv('irs_inputs.csv').set_index('seq')
def med(s):
    try: return json.loads(X.med.get(s) or '{}')
    except Exception: return {}
mb=pd.DataFrame([med(s) for s in u.seq_b]); mf=pd.DataFrame([med(s) for s in u.seq_f])
print('med keys',sorted(set(mb.columns)|set(mf.columns)))
pd.to_pickle(dict(u=u,mb=mb,mf=mf),'XL_users.pkl')
