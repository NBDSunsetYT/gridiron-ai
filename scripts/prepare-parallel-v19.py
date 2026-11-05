"""Metadata-only preregistration. No new model fitting or outcome-driven selection."""
import sys,json,hashlib,random
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.structural_v18.data import packets
from modeling.iterative_learning import freeze_json
OUT=ROOT/'artifacts/parallel-v19'
excluded=set()
for path,key in [('artifacts/engine-v15/selection.json','selection'),('artifacts/engine-v15/nba/selection.json','games'),('artifacts/learning-v16/protocol.json','selection')]:excluded.update(g['id'] for g in json.load(open(ROOT/path))[key])
previous=json.load(open(ROOT/'artifacts/structural-v18/protocol.json'))
for games in previous['selection'].values():excluded.update(g['id'] for g in games)
windows={s:[['2025-10-01','2025-10-15'],['2025-11-01','2025-11-15'],['2025-12-01','2025-12-15']] for s in ['NFL','CFB']};windows['NBA']=[['2025-11-01','2025-11-15'],['2026-01-01','2026-01-15'],['2026-02-01','2026-02-15']]
rng=random.Random(19005);selection={};eligible={}
for sport in ['NFL','CFB','NBA']:
    games=packets(sport);parts=[];ns=[]
    for cohort,(start,end) in enumerate(windows[sport]):
        candidates=[g for g in games if start<=g['at'][:10]<end and g['id'] not in excluded];rng.shuffle(candidates);ns.append(len(candidates));parts.extend({'sport':sport,'id':g['id'],'at':g['at'],'home':g['home'],'away':g['away'],'season':g['season'],'cohort':cohort} for g in candidates[:12])
    selection[sport]=sorted(parts,key=lambda g:(g['at'],g['id']));eligible[sport]=ns
protocol={'id':'parallel-reconstruction-19.0.0','seed':19005,'selection':selection,'eligiblePerWindow':eligible,'excludedIds':sorted(excluded),'windows':windows,'projectionTrainingCutoff':'2025-07-01','fullGameSubsetPerWindow':4,'trials':10000,'maxCpuSeconds':1800,'maxConcurrentLocalProcesses':2,'schedule':'NFL and CFB reconstruct/train before either is graded; round-robin NFL/CFB/NBA full-game tasks.','footballVariants':['frozen_reference','team_eb','team_eb_frailty'],'nbaVariants':['v18_joint_rotation','recency_usage_eb'],'hypotheses':['Separate player-opportunity accuracy and moneyline decisions.','Context-conditioned clock pools and empirical-Bayes team touchdown effects can improve team scoring without post-hoc probability transforms.','Game-level shared efficiency variation learned from earlier residuals may prevent overconfident favorite probabilities.','Recent minute-weighted, shrunk NBA usage/efficiency histories may generalize better than career pooling.'],'promotionGate':{'minGames':200,'minWindows':3,'maxImportantCategoryRegression':.03,'requirePairedImprovementCI':True,'maxBrierRegression':0,'maxLogLossRegression':0,'minVerifiedAvailabilityCoverage':.9},'registrySlots':[s+':'+p for s in ['NFL','CFB','NBA'] for p in ['player','moneyline']],'finalTest':previous['prospectiveFinal'],'sourceFiles':previous['sourceFiles'],'sourceVersion':'v18-owned-source-caches; additions versioned independently','automaticProductionPromotion':False}
freeze_json(OUT/'protocol.json',protocol);freeze_json(ROOT/'docs/reports/parallel-v19-protocol.json',protocol);print(json.dumps({'games':{s:len(v) for s,v in selection.items()},'eligible':eligible,'sha256':hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest()}))
