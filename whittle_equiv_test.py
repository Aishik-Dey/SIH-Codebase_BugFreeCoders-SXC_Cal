"""Randomized check that solve_whittle_indices(fast=True) == fast=False."""
import time, random, numpy as np
from whittle_index import solve_whittle_indices
random.seed(1); bad=[]; tf=ts=0; N=300; used=0
for _ in range(N):
    p01=10**random.uniform(-4.5,-0.1); p11=random.choice([random.uniform(0.001,0.999),10**random.uniform(-3,-0.1)])
    if abs(p11-p01)<1e-3: continue
    used+=1
    t=time.time(); _,o1,w1=solve_whittle_indices(p01,p11,fast=False); ts+=time.time()-t
    t=time.time(); _,o2,w2=solve_whittle_indices(p01,p11,fast=True); tf+=time.time()-t
    if not (np.array_equal(o1,o2) and np.array_equal(w1,w2)): bad.append((p01,p11,float(np.abs(w1-w2).max())))
print(f"cases {used}  mismatches {len(bad)}  full {ts:.2f}s  fast {tf:.2f}s  speedup {ts/tf:.1f}x")
for b in bad[:5]: print("  mismatch p01=%.4g p11=%.4g maxdiff=%.3g"%b)
