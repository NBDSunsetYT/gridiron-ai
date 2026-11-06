"""Replay frozen predictions, then plot diagnostic calibration. No refitting."""
import sys,json,gzip,pickle,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from modeling.dynamic_v24.io import OUT
from modeling.dynamic_v24.runtime import job
from modeling.dynamic_v24.completion.data import packets,enrich_packets,features_only
from modeling.dynamic_v24.completion.efficient_data import records
from modeling.dynamic_v24.completion.additional_data import packets as nfl_history
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import read,atomic,digest
CASES=[('NFL','completion-nfl-extension-r2',['passingYards']),('NFL','completion-nfl-games-r1',['moneyline']),('CFB','completion-cfb-extension-r1',['passingYards']),('NBA','completion-nba-clean-r1',['minutes','rebounds','points'])]

def run():
    checked=[];curves=[]
    for sport,folder,stats in CASES:
        p=OUT/folder;spec=read(p/'protocol.json');windows=spec['selection'][sport];selected={g for w in windows for g in w['games']};gs=nfl_history('NFL') if sport=='NFL' else packets(sport)
        if sport=='NFL':gs=[g for g in gs if g['at']<'2022-01-01']
        bad={r['gameId'] for r in spec.get('sourceRejectedGames',[])};gs=enrich_packets([g for g in gs if g['id'] not in bad and g['at']<max(w['end'] for w in windows)],sport);rr=records(gs,sport,selected)
        for wi,w in enumerate(windows):
            report=read(p/sport/str(wi)/'results.json');ids=set(w['games'])
            for stat in stats:
                future=[r for r in rr if r['stat']==stat and r['gameId'] in ids];x=features_only(future);grade=np.array([i for i,r in enumerate(future) if r['y'] is not None]);y=np.array([future[i]['y'] for i in grade]);families=sorted({'rolling5',*report[stat]['selected'].values()})
                for family in families:
                    artifact=report[stat]['modelArtifacts'][family];model_path=ROOT/artifact['path'];raw=model_path.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=artifact['sha256']:raise ValueError('Model artifact checksum changed')
                    model=pickle.loads(raw);snapshot=json.loads(gzip.decompress((model_path.parent/(family+'-forecast.json.gz')).read_bytes()));pred=model.predict(x)
                    if digest(x)!=snapshot['featureInputHash']:raise ValueError('Reconstructed historical features differ from frozen input hash')
                    np.testing.assert_allclose(pred,snapshot['pointEstimate'],rtol=1e-12,atol=1e-12);checked.append({'sport':sport,'stat':stat,'window':wi,'family':family,'forecastRows':len(x),'gradedObservations':len(grade),'inputHashEqual':True,'predictionEqualTolerance':1e-12,'sourceModelSHA256':artifact['sha256']})
                    if family not in {'rolling5',report[stat]['selected']['distribution']}:continue
                    sample=model.samples(x,240241,128)[grade];thresholds=report[stat]['candidates'][family]['thresholds']
                    if stat=='moneyline':prob=pred[grade];truth=y
                    else:prob=np.stack([(np.sum(sample<=line,axis=1)+.5)/129 for line in thresholds],axis=1).ravel();truth=np.stack([y<=line for line in thresholds],axis=1).ravel()
                    bins=np.minimum(9,(np.clip(prob,0,1)*10).astype(int));curve=[{'count':int(np.sum(bins==b)),'predicted':float(np.mean(prob[bins==b])),'observed':float(np.mean(truth[bins==b]))} for b in range(10) if np.any(bins==b)];curves.append({'sport':sport,'stat':stat,'window':wi,'family':family,'games':len({future[i]['gameId'] for i in grade}),'bins':curve,'scope':'Raw moneyline probability' if stat=='moneyline' else 'Training-quantile diagnostic CDF, not historical market lines'})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,3,figsize=(13,8));panels=[('NFL','passingYards'),('NFL','moneyline'),('CFB','passingYards'),('NBA','minutes'),('NBA','rebounds'),('NBA','points')]
    for ax,(sport,stat) in zip(axes.flat,panels):
        ax.plot([0,1],[0,1],color='#999',linestyle='--',linewidth=1)
        for c in curves:
            if c['sport']==sport and c['stat']==stat:ax.plot([b['predicted'] for b in c['bins']],[b['observed'] for b in c['bins']],marker='.',alpha=.75,label=('Reference' if c['family']=='rolling5' else c['family'])+' w'+str(c['window']+1))
        ax.set(title=sport+' '+stat,xlim=(0,1),ylim=(0,1),xlabel='Forecast probability',ylabel='Observed frequency');ax.legend(fontsize=6)
    fig.suptitle('V24 conditional historical reliability — no approved calibrator or strict pregame claim');fig.tight_layout();chart=ROOT/'docs/research/charts/specialized-v24-reliability.png';chart.parent.mkdir(exist_ok=True);fig.savefig(chart,dpi=160);plt.close(fig)
    result={'checks':checked,'curves':curves,'refits':0,'gameSimulations':0,'strictForecasts':0,'protectedFinalOutcomesUsed':False,'allSelectedInputHashesEqual':True,'allFrozenPointForecastsReplayed':True};atomic(OUT/'completion-final/replay-verification.json',result);atomic(ROOT/'docs/research/specialized-v24-replay.json',result);return {'modelForecastsReplayed':len(checked),'forecastRowsChecked':sum(c['forecastRows'] for c in checked),'refits':0,'inputHashesEqual':True,'strictForecasts':0}

if __name__=='__main__':
    if '--register' in sys.argv:freeze_json(OUT/'specs/specialized-replay-r1.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'modeling/dynamic_v24/completion').glob('*.py'))]},'operation':'Read/replay frozen models; never fit or change model selection'})
    else:print(json.dumps(job('specialized-replay-r1',run,cpu=240,wall=360),indent=2))
