"""Bitwise equivalence: vectorised WhittleIndexScheduler vs the scalar (per-band python loop) one.
Run from a folder containing whittle_index.py, scan_scheduler_v2.py, scan_scheduler_whittle.py
and scan_scheduler_whittle_scalar.py:   python3 scan_scheduler_whittle_equiv_test.py"""
import sys, time, random, math, numpy as np
from scan_scheduler_whittle import WhittleIndexScheduler as VE
from scan_scheduler_whittle_scalar import WhittleIndexScheduler as SC
NB=36
class MarkovEnv:
    def __init__(self,seed,sparse):
        r=random.Random(seed); self.r=r
        self.p01=[10**r.uniform(-3.5,-0.5) if sparse else r.uniform(0.01,0.5) for _ in range(NB)]
        self.p11=[r.uniform(0.05,0.98) for _ in range(NB)]
        self.s=[r.random()<0.2 for _ in range(NB)]
    def step(self):
        r=self.r
        for b in range(NB):
            self.s[b]= (r.random()<self.p11[b]) if self.s[b] else (r.random()<self.p01[b])
        return {b:self.s[b] for b in range(NB)}
def run(cls,env_seed,sparse,n,k,seed,prio,warm):
    random.seed(seed); env=MarkovEnv(env_seed,sparse)
    s=cls(NB,ucb_c=0.5,priority=prio,warmup_steps=warm,warmup_dwell_steps=2,warmup_dwell_jitter=1)
    picks=[]; 
    for t in range(n):
        st=env.step(); b=s.choose_bands(k); picks.append(tuple(b))
        for x in b: s.update(x,st[x])
    return picks,s
cfgs=[(1,True,6000,1,None,0),(2,False,6000,2,None,0),(3,True,6000,4,'rand',0),(4,False,6000,1,'rand',400),(5,True,6000,3,'rand',250),(6,False,6000,8,None,0)]
allok=True
for (es,sp,n,k,pr,warm) in cfgs:
    prio=None if pr is None else [random.Random(es).uniform(0.5,3.0) for _ in range(NB)]
    ts=time.perf_counter(); pa,sa=run(SC,es,sp,n,k,7,prio,warm); ts=time.perf_counter()-ts
    tv=time.perf_counter(); pb,sb=run(VE,es,sp,n,k,7,prio,warm); tv=time.perf_counter()-tv
    same_picks = pa==pb
    same_state = all(getattr(sa,a)==getattr(sb,a) for a in ('belief','scan_count','off_on','off_tot','on_on','on_tot','t'))
    ntab=sum(t is not None for t in sb._tables)
    ok=same_picks and same_state; allok&=ok
    print(f"env{es} sparse={sp!s:5} k={k} prio={'rand' if prio else '1.0 '} warmup={warm:3d}: picks identical={same_picks} state identical={same_state}  tables={ntab}/36  scalar {ts:5.2f}s  vec {tv:5.2f}s")
# bitwise score check on live state
random.seed(9); env=MarkovEnv(11,True); v=VE(NB,ucb_c=0.5,priority=[random.uniform(.5,3) for _ in range(NB)]); bad=0; checks=0
for t in range(5000):
    st=env.step(); b=v.choose_bands(2)
    if t%7==0:
        vec=v._prio*v._lookup_all(np.array(v.belief))+v.ucb_c*np.sqrt(__import__('math').log(v.t+1)/v._cnt1)
        sca=np.array([v.priority[x]*v._lookup(x,v.belief[x])+v.ucb_c*__import__('math').sqrt(__import__('math').log(v.t+1)/(v.scan_count[x]+1)) for x in range(NB)])
        checks+=1; bad+= not np.array_equal(vec,sca)
    for x in b: v.update(x,st[x])
print(f"bitwise score check (vector vs scalar formula) at {checks} live states: {bad} mismatches")
print("ALL EQUIVALENT" if allok and bad==0 else "MISMATCH FOUND")
