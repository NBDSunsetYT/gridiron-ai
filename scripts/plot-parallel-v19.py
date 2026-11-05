"""Scientific report figures, computed only from archived validation metrics."""
import sys,json,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from modeling.simulator import wilson
r=json.load((ROOT/'docs/reports/parallel-v19-results-v2.json').open());fig,axes=plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
for ax,s in zip(axes,['NFL','CFB','NBA']):
    candidates=r['leagues'][s]['fullGameComparisons'];candidate='recency_usage_eb' if s=='NBA' else 'oof_game_effect';ax.plot([0,1],[0,1],'--',color='#777',label='Ideal')
    for c,color,label in [('frozen_reference','#b45b56','Frozen reference'),(candidate,'#168a8d','Structural challenger')]:
        bins=candidates[c]['moneyline']['bins'];x=[b['meanPredicted'] for b in bins];y=[b['observed'] for b in bins];intervals=[wilson(round(b['observed']*b['n']),b['n']) for b in bins]
        ax.errorbar(x,y,yerr=[[v-lo for v,(lo,hi) in zip(y,intervals)],[hi-v for v,(lo,hi) in zip(y,intervals)]],fmt='o-',capsize=3,color=color,alpha=.8,label=label)
        for a,b,bin in zip(x,y,bins):ax.annotate('n='+str(bin['n']),(a,b),xytext=(4,4),textcoords='offset points',fontsize=7)
    ax.set(title=s+' · 9 validation games',xlabel='Raw predicted home-win probability',ylabel='Observed home wins',xlim=(-.03,1.03),ylim=(-.05,1.05));ax.grid(alpha=.18)
axes[0].legend(fontsize=8,loc='lower right');fig.suptitle('Raw probability reliability · Wilson 95% bin intervals · exploratory small samples',fontsize=11);fig.savefig(ROOT/'docs/reports/parallel-v19-reliability.png',dpi=160);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for ax,s in zip(axes,['NFL','CFB','NBA']):
    c='recency_usage_eb' if s=='NBA' else 'oof_game_effect';xs=[];ys=[]
    for p in (ROOT/'artifacts/parallel-v19/runs'/s/c).glob('*.official-evaluation-v2.json.gz'):
        g=json.loads(gzip.decompress(p.read_bytes()));xs.extend(v['mean'] for v in g['score']);ys.extend(v['actual'] for v in g['score'])
    low=min(xs+ys)-3;high=max(xs+ys)+3;ax.plot([low,high],[low,high],'--',color='#777');ax.scatter(xs,ys,c='#168a8d');ax.set(title=s+' · 18 team scores',xlabel='Predicted mean score',ylabel='Verified final score');ax.grid(alpha=.18)
fig.suptitle('Frozen structural forecasts versus verified outcomes · not untouched final-test results',fontsize=11);fig.savefig(ROOT/'docs/reports/parallel-v19-scores.png',dpi=160)
