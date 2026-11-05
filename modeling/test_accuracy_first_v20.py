"""Synthetic audit invariants only; these tests are not accuracy measurements."""
import unittest,tempfile,copy,os,subprocess
from pathlib import Path
from .accuracy_v20.quality import assess,DOMAINS
from .accuracy_v20.attribution import factor_attribution,opportunity_efficiency,nba_rebound_attribution
from .accuracy_v20.snapshots import ResearchSnapshots
def evidence():return {k:{'eventId':'g','source':'https://example.com/synthetic','sourceVersion':'fixture-v1','publishedAt':'2024-01-01T10:00:00Z','retrievedAt':'2024-01-01T11:00:00Z','classification':'confirmed','complete':True} for k in (*DOMAINS,'weather')}
class EvidenceTests(unittest.TestCase):
 def test_unknown_injury_is_never_healthy(self):
  e=evidence();e['injury']={};q=assess('CFB','g','2024-01-01T12:00:00Z',e)
  self.assertIn('injury',q['missingDomains']);self.assertFalse(q['missingMeansHealthy']);self.assertEqual(q['decision'],'withhold_unconditional_forecast');self.assertLess(q['pointInTimeEvidenceScore'],100)
 def test_postcutoff_and_wrong_identity_are_withheld(self):
  e=evidence();e['lineup']['publishedAt']='2024-01-01T13:00:00Z';e['injury']['playerId']='wrong';q=assess('NFL','g','2024-01-01T12:00:00Z',e,'correct');self.assertFalse(q['conditionalResearchAllowed']);self.assertIn('lineup',q['missingDomains']);self.assertEqual(q['components']['injury']['failure'],'player_identity_mismatch')
 def test_data_coverage_is_not_model_validation(self):
  q=assess('NBA','g','2024-01-01T12:00:00Z',evidence());self.assertEqual(q['pointInTimeEvidenceScore'],100);self.assertEqual(q['decision'],'withhold_unconditional_forecast');self.assertFalse(q['productionPromotion']);self.assertIn('model_uncertainty_not_quantified',q['warnings'])
 def test_naive_timestamp_rejected(self):
  with self.assertRaises(ValueError):assess('NFL','g','2024-01-01T12:00:00',evidence())
 def test_actual_pre_cutoff_capture_proves_availability_without_backdating_publication(self):
  e=evidence();e['historical_statistics'].update(publishedAt=None,immutableReceipt=True);q=assess('NBA','g','2024-01-01T12:00:00Z',e)
  self.assertIn('historical_statistics',q['verifiedDomains']);self.assertIsNone(q['components']['historical_statistics']['publishedAt']);self.assertEqual(q['components']['historical_statistics']['availabilityEstablishedBy'],'2024-01-01T11:00:00Z')
 def test_excessive_parameter_uncertainty_withholds_even_complete_evidence(self):
  q=assess('NBA','g','2024-01-01T12:00:00Z',evidence(),model_uncertainty={'validated':True,'sourceVersion':'synthetic-model-interval','probabilityInterval95':[.05,.95]});self.assertEqual(q['decision'],'withhold_unconditional_forecast');self.assertIn('model_uncertainty_exceeds_predeclared_width_policy',q['warnings'])
class AttributionTests(unittest.TestCase):
 def test_interactions_reconcile_to_signed_and_absolute_error(self):
  r=factor_attribution({'minutes':30,'volume':.5,'efficiency':2},{'minutes':24,'volume':.4,'efficiency':3},28.8,30)
  self.assertAlmostEqual(sum(r['signedContributions'].values()),1.2);self.assertAlmostEqual(sum(r['absoluteErrorContributions'].values()),1.2);self.assertIsNone(r['distributionAssumptionContribution'])
 def test_zero_opportunities_have_no_invented_efficiency(self):
  r=opportunity_efficiency(10,0,50,0);self.assertIsNone(r['observedEfficiency']);self.assertAlmostEqual(r['signedContributions']['efficiency'],0);self.assertAlmostEqual(r['signedContributions']['opportunity_volume'],50)
 def test_missing_opportunity_withholds_attribution(self):
  self.assertFalse(opportunity_efficiency(0,4,0,20)['available'])
 def test_nba_minutes_and_rebounds_reconcile(self):
  r=nba_rebound_attribution(30,25,48,48,80,70,10,7);self.assertTrue(r['exposureIsMinutesProxy']);self.assertAlmostEqual(sum(r['signedContributions'].values()),3);self.assertIn('true_on_court_missed_shots',r['unidentifiedComponents'])
class SnapshotTests(unittest.TestCase):
 def body(self):return {'eventId':'g','eventStart':'2024-01-01T18:00:00Z','predictionAsOf':'2024-01-01T12:00:00Z','modelVersion':'synthetic-v1','inputHash':'abc','phase':'historical_replay','playerIds':['p'],'probability':.5}
 def fact(self,status='out',hour=13):return {'eventId':'g','playerId':'p','source':'https://example.com/synthetic','sourceVersion':str(hour),'publishedAt':f'2024-01-01T{hour:02d}:00:00Z','retrievedAt':'2024-01-02T00:00:00Z','verified':True,'kind':'injury','value':{'status':status}}
 def test_persistence_immutability_and_safe_update_queue(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'research.sqlite';s=ResearchSnapshots(p);body=self.body();ident=s.freeze(body);self.assertEqual(s.freeze(body),ident);r=s.verified_update(self.fact(),body['eventStart']);self.assertEqual(r['queued'],1);self.assertEqual(r['runsStarted'],0);self.assertTrue(s.get(ident)['stale']);self.assertEqual(s.get(ident)['snapshot'],body);self.assertEqual(s.verified_update(self.fact(),body['eventStart'])['queued'],0);s.close();s=ResearchSnapshots(p);self.assertEqual(s.get(ident)['snapshot'],body);s.backup(Path(d)/'backup.sqlite');s.close();backup=ResearchSnapshots(Path(d)/'backup.sqlite');self.assertTrue(backup.get(ident)['stale']);backup.close()
 def test_postkickoff_fact_cannot_rewrite_pregame(self):
  with tempfile.TemporaryDirectory() as d:
   s=ResearchSnapshots(Path(d)/'a.sqlite');ident=s.freeze(self.body());r=s.verified_update(self.fact(hour=19),self.body()['eventStart']);self.assertFalse(r['accepted']);self.assertFalse(s.get(ident)['stale']);s.close()
 def test_status_cycle_revives_one_job_and_old_delivery_does_not_override(self):
  with tempfile.TemporaryDirectory() as d:
   s=ResearchSnapshots(Path(d)/'a.sqlite');s.freeze(self.body());s.verified_update(self.fact('out',13),self.body()['eventStart']);s.verified_update(self.fact('available',14),self.body()['eventStart']);r=s.verified_update(self.fact('out',15),self.body()['eventStart']);self.assertEqual(r['queued'],1);self.assertEqual(s.db.execute("select count(*) from refresh_jobs where state='queued'").fetchone()[0],1);self.assertEqual(s.verified_update(self.fact('available',14),self.body()['eventStart'])['queued'],0);s.close()
 def test_cannot_backdate_a_prospective_forecast(self):
  with tempfile.TemporaryDirectory() as d:
   s=ResearchSnapshots(Path(d)/'a.sqlite');body=self.body();body['phase']='prospective_pregame'
   with self.assertRaises(ValueError):s.freeze(body,recorded_at='2024-01-02T00:00:00Z')
   s.close()
 def test_conflicting_reports_block_work_until_newer_verified_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   s=ResearchSnapshots(Path(d)/'a.sqlite');ident=s.freeze(self.body());s.verified_update(self.fact('out',13),self.body()['eventStart']);r=s.verified_update(self.fact('available',13),self.body()['eventStart']);self.assertFalse(r['accepted']);self.assertTrue(s.get(ident)['stale']);self.assertEqual(s.db.execute("select count(*) from refresh_jobs where state='queued'").fetchone()[0],0);self.assertEqual(s.verified_update(self.fact('out',14),self.body()['eventStart'])['queued'],1);s.close()
class InfrastructureTests(unittest.TestCase):
 def test_exited_unreaped_process_is_not_live_work(self):
  from .overnight_v20.state import alive,process_identity
  p=subprocess.Popen(['python','-c','pass']);identity=process_identity(p.pid)
  try:os.waitid(os.P_PID,p.pid,os.WEXITED|os.WNOWAIT);self.assertFalse(alive(identity))
  finally:p.wait()
class SeparateModelTests(unittest.TestCase):
 def test_leagues_and_training_cutoffs_cannot_mix(self):
  from .accuracy_v20.projections import LeagueOpportunityModels
  with self.assertRaisesRegex(ValueError,'Future'):LeagueOpportunityModels('CFB').fit([{'at':'2025-01-01T00:00:00Z'}],'2024-01-01T00:00:00Z')
  with self.assertRaisesRegex(ValueError,'pool'):LeagueOpportunityModels('NFL').fit([{'at':'2023-01-01T00:00:00Z','sport':'CFB'}],'2024-01-01T00:00:00Z')
 def test_prediction_never_reads_the_current_final_label(self):
  from .accuracy_v20.projections import LeagueOpportunityModels
  rows=[]
  for i in range(150):
   op=0 if i%4==0 else 10+i%7;rows.append({'sport':'NFL','at':'2023-01-01T00:00:00Z','featureNames':['passingAttempts_mean5','opponent_allowed_passingYards'],'x':[10+i%7,200+i%3],'y':op*6.,'opportunity':op,'stat':'passingYards','player':'SYNTHETIC','team':'SYNTHETIC','baseline':60.})
  m=LeagueOpportunityModels('NFL').fit(rows,'2024-01-01T00:00:00Z');r={**rows[1],'at':'2024-01-02T00:00:00Z'};a=m.predict('passingYards',[r]);r['y']=999999;self.assertEqual(float(a[0]),float(m.predict('passingYards',[r])[0]))
def nba_final_fixture():
 labels=['MIN','PTS','FG','3PT','FT','REB','AST','TO','STL','BLK','OREB','DREB','PF'];teams=[];players=[];competitors=[]
 for team in ['1','2']:
  points=6 if team=='1' else 5;free='1-1' if team=='1' else '0-0';competitors.append({'homeAway':'home' if team=='1' else 'away','team':{'id':team},'score':str(points*5)})
  rows=[{'athlete':{'id':str(int(team)*100+i)},'didNotPlay':False,'stats':['48',str(points),'2-4','1-2',free,'4','2','1','1','0','1','3','2']} for i in range(5)];players.append({'team':{'id':team},'statistics':[{'labels':labels,'athletes':rows}]});teams.append({'team':{'id':team},'statistics':[{'name':k,'displayValue':str(v)} for k,v in [('totalRebounds',20),('offensiveRebounds',5),('defensiveRebounds',15),('assists',10),('turnovers',5),('steals',5),('blocks',0)]]})
 return {'header':{'id':'99','competitions':[{'status':{'type':{'completed':True}},'competitors':competitors}]},'boxscore':{'teams':teams,'players':players}}
class NBAOutcomeTests(unittest.TestCase):
 def test_event_identity_and_stat_accounting(self):
  from .accuracy_v20.outcomes import normalize_nba_final
  d=nba_final_fixture();box=normalize_nba_final(d,'nba:espn:99','1','2');self.assertTrue(box['notForPregameFeatures']);self.assertIn('rebounds',box['supportedStatisticsByTeam']['1'])
  with self.assertRaisesRegex(ValueError,'identity'):normalize_nba_final(d,'nba:espn:100','1','2')
 def test_unknown_minutes_are_withheld_without_discarding_verified_counts(self):
  from .accuracy_v20.outcomes import normalize_nba_final
  d=nba_final_fixture();d['boxscore']['players'][0]['statistics'][0]['athletes'].append({'athlete':{'shortName':'UNMAPPED_SYNTHETIC'},'didNotPlay':False,'stats':['--','0','0-0','0-0','0-0','0','0','0','0','0','0','0','0']});box=normalize_nba_final(d,'nba:espn:99','1','2');self.assertNotIn('minutes',box['supportedStatisticsByTeam']['1']);self.assertIn('rebounds',box['supportedStatisticsByTeam']['1']);self.assertEqual(len(box['unmapped']),1);self.assertFalse(box['unmapped'][0]['identityResolved'] if 'identityResolved' in box['unmapped'][0] else False)
 def test_unmapped_nonzero_categories_are_not_fabricated_as_player_zeros(self):
  from .accuracy_v20.outcomes import normalize_nba_final
  d=nba_final_fixture();d['header']['competitions'][0]['competitors'][0]['score']='32';d['boxscore']['players'][0]['statistics'][0]['athletes'].append({'athlete':{'shortName':'UNMAPPED_SYNTHETIC'},'didNotPlay':False,'stats':['--','2','0-0','0-0','2-2','0','0','0','0','0','0','0','0']});box=normalize_nba_final(d,'nba:espn:99','1','2');self.assertNotIn('points',box['supportedStatisticsByTeam']['1']);self.assertIn('rebounds',box['supportedStatisticsByTeam']['1']);self.assertEqual(sum(p['stats']['points'] for p in box['players'].values() if p['team']=='1'),30)
if __name__=='__main__':unittest.main()
