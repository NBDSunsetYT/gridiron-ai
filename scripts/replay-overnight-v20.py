"""Cold replay or quarantine of one exact preregistered validation forecast.
Only saved pregame inputs are used. No final box is opened in this command.
The full runner must be checkpointed first; the same campaign lease/budgets apply.
"""
import sys,os,argparse,copy,time,json,gzip,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.overnight_v20.state import Campaign,process_identity,digest,atomic
from modeling.overnight_v20.cohort import read,lineup
from modeling.overnight_v20.sources import protocol
from modeling.overnight_v20 import data,models,football,nba
from modeling.reconstruction_v19 import football_rules as football19,nba as nba19
from modeling.iterative_learning import freeze_json,unrealism_flags
p=argparse.ArgumentParser();p.add_argument('--sport',choices=['NFL','CFB','NBA'],required=True);p.add_argument('--event',required=True);p.add_argument('--variant',required=True);p.add_argument('--revision',default='r1');p.add_argument('--quarantine',action='store_true');args=p.parse_args();OUT=ROOT/'artifacts/overnight-v20';g=next(g for g in protocol()['selection'][args.sport] if g['id']==args.event and g['fullGame']);folder=OUT/'experiments'/args.revision/'cohorts'/(args.sport+'-'+str(g['cohort']));archive=folder/'forecasts'/args.variant/(g['id'].replace(':','_')+'.json.gz');trials=1000 if args.quarantine else 10000
key='diagnostic-'+args.revision+'-'+args.sport+'-'+g['id']+'-'+args.variant+('-quarantine' if args.quarantine else '-replay');dest=OUT/'diagnostics'/(key.replace(':','_')+'.json.gz')
if dest.exists():print(json.dumps({'alreadyFrozen':str(dest)}));sys.exit(0)
campaign=Campaign(OUT/'runtime')
with campaign.lease():
    campaign.begin();allowed,why=campaign.may_start(120)
    if not allowed:campaign.end(why);raise RuntimeError(why)
    import resource,signal
    resource.setrlimit(resource.RLIMIT_CPU,(int(time.process_time())+120,int(time.process_time())+125));signal.alarm(180)
    campaign.claim(key,process_identity(os.getpid()),120,{'event':g['id'],'variant':args.variant,'simulations':trials});before=time.process_time()
    try:
        base=read(folder/'simulation-model.json.gz');evidence=read(OUT/'evidence'/(args.sport+'-aligned-v3.json.gz'));lf=lineup(g,evidence);seed=int(hashlib.sha256(('v20:'+g['id']).encode()).hexdigest()[:10],16);opportunities=read(folder/'point-forecasts.json.gz')['opportunities'][g['id']]
        m=models.refresh_context(copy.deepcopy(base),data.archives(args.sport),g);m['forecastSeason']=g['season']
        if args.sport=='NBA':
            m['projectedMinutes']={t:{pid:stats['minutes'] for pid,stats in opportunities[t].items() if pid!='__team__' and 'minutes' in stats} for t in [g['home'],g['away']]};m['reboundVariant']=args.variant
            if args.variant!='v19_reference':m['version']=nba.VERSION
            engine=nba19 if args.variant=='v19_reference' else nba
        else:
            if args.variant!='v19_reference':
                m.update(version=football.VERSION,passRateShift=models.volume_shift(m,opportunities,[g['home'],g['away']]))
                if args.variant=='qb_mixture':m['qbPlans']=models.qb_plans(m,[g['home'],g['away']],lf)
            engine=football19 if args.variant=='v19_reference' else football
        m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});kwargs={'lineups':lf}
        if args.sport!='NBA':kwargs['representative_games']=0
        f=(engine.simulate_nba if args.sport=='NBA' else engine.simulate_football)(m,g['home'],g['away'],g['at'],trials,seed,**kwargs);flags=unrealism_flags(f);original=read(archive)['forecast'] if archive.exists() else None
        same=None if original is None else all(f[k]==original[k] for k in ['inputDataVersion','scoreDistributions','players','homeWinProbability','convergence'])
        output={'game':g,'variant':args.variant,'simulations':trials,'forecast':f,'exactDistributionReplay':same,'unrealismFlags':flags,'modelSha256':m['sha256'],'sharedModelSha256':base['sha256'],'lineups':lf,'finalOutcomesRead':False,'quarantined':args.quarantine,'productionEligible':False,'cpuSeconds':time.process_time()-before,'seed':seed}
        freeze_json(dest,output);campaign.finish(key,{'status':'completed','cpuSeconds':time.process_time()-before,'completeGamesSimulated':trials,'exactDistributionReplay':same,'unrealismFlags':flags,'artifact':str(dest.relative_to(ROOT))});print(json.dumps({k:output[k] for k in ['game','variant','simulations','exactDistributionReplay','unrealismFlags','cpuSeconds']},indent=2))
    except Exception as e:
        campaign.finish(key,{'status':'failed','error':str(e),'cpuSeconds':time.process_time()-before});raise
    finally:campaign.end('diagnostic_checkpoint')
