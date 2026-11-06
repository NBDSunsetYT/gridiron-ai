"""Export measured research charts; no fabricated accuracy curves."""
import sys,json,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
OUT=ROOT/'artifacts/dynamic-v24';report=json.load(open(OUT/'analysis/summary.json'));figdir=OUT/'figures';figdir.mkdir(exist_ok=True)
plt.rcParams.update({'figure.facecolor':'#0b1419','axes.facecolor':'#101f27','axes.edgecolor':'#4b6674','text.color':'#d9e7eb','axes.labelcolor':'#aec6ce','xtick.color':'#aec6ce','ytick.color':'#aec6ce','font.size':9})
fig,axs=plt.subplots(2,3,figsize=(14,7),layout='constrained')
for col,sport in enumerate(['NFL','CFB','NBA']):
 windows=report['sequential'][sport];task='actions';task2='shots' if sport=='NBA' else 'drives'
 for row,name in enumerate([task,task2]):
  ax=axs[row,col];rows=[w['tasks'][name] for w in windows if w['tasks'].get(name,{}).get('status')=='evaluated'];colors=['#718d99','#36d1a6','#42cce4'];vals=[sum(t['metrics'][v]['logLoss']*t['events'] for t in rows)/sum(t['events'] for t in rows) for v in ['A','B','C']];ax.bar(['A prior','B state','C dynamic'],vals,color=colors);ax.set_title(sport+' / '+name+' / '+str(sum(t['events'] for t in rows))+' events');ax.set_ylabel('Conditional next-event log loss');ax.grid(axis='y',alpha=.12)
  for i,value in enumerate(vals):ax.text(i,value+.01,f'{value:.4f}',ha='center',fontsize=8)
fig.suptitle('V24 next-event research — lower log loss is better; not full-game prediction accuracy',fontsize=13);fig.savefig(figdir/'event-comparison.png',dpi=180);plt.close(fig)
fig,axs=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
for ax,sport,stat in zip(axs,['NFL','CFB','NBA'],['passingYards','passingYards','rebounds']):
 h=next(r for r in report['leaderboard'] if r['sport']==sport and r['stat']==stat);windows=h.get('windows',[]);x=np.arange(len(windows));a=[w['baseline']['mae'] for w in windows];b=[w['candidate']['mae'] for w in windows];ax.bar(x-.18,a,.35,label='Rolling5',color='#718d99');ax.bar(x+.18,b,.35,label=h.get('bestFirstWindowFamily'),color='#36d1a6');ax.set_xticks(x,['Earlier window','Confirmation']);ax.set_title(sport+' / '+stat);ax.set_ylabel('Player-stat MAE');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.12)
fig.suptitle('Selected family fixed from earlier window; errors may not generalize',fontsize=12);fig.savefig(figdir/'passing-and-rebounds.png',dpi=180);plt.close(fig)
fig,axs=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
for ax,sport in zip(axs,['NFL','CFB','NBA']):
 heads=[h for h in report['leaderboard'] if h['sport']==sport and h['status']=='conditional_evaluated'];labels=[h['stat'] for h in heads];base=[h['windows'][-1]['baseline']['interval90Coverage'] for h in heads];candidate=[h['windows'][-1]['candidate']['interval90Coverage'] for h in heads];ax.plot(labels,base,'o',color='#718d99',label='Rolling residual law');ax.plot(labels,candidate,'x',color='#42cce4',label='Candidate marginal law');ax.axhline(.9,color='#d1b86e',ls='--');ax.set_ylim(0,1.03);ax.set_title(sport+' / interval coverage');ax.tick_params(axis='x',rotation=90,labelsize=6);ax.set_ylabel('Observed 90% interval coverage');ax.legend(fontsize=7)
fig.suptitle('Distribution coverage is evaluated separately from point error',fontsize=12);fig.savefig(figdir/'interval-coverage.png',dpi=180);plt.close(fig)
with (OUT/'leaderboard.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['sport','stat','status','family','estimand','window','games','observations','baseline_MAE','candidate_MAE','RMSE','bias','CRPS','interval90_coverage','zero_event_Brier','point_candidate','production_promotion'])
 for h in report['leaderboard']:
  for i,m in enumerate(h.get('windows',[{}])):
   b=m.get('baseline',{});c=m.get('candidate',{});w.writerow([h['sport'],h['stat'],h['status'],h.get('bestFirstWindowFamily'),h.get('pointEstimand'),i,c.get('games'),c.get('observations'),b.get('mae'),c.get('mae'),c.get('rmse'),c.get('bias'),c.get('crps'),c.get('interval90Coverage'),c.get('zeroEventBrier'),h.get('pointResearchCandidate',False),False])
print('Three measured charts and complete category leaderboard exported')
