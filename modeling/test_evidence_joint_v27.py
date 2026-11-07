"""Synthetic regression checks, never predictive-accuracy evidence."""
import unittest,copy,runpy,tempfile,pickle,hashlib
from unittest.mock import patch
import numpy as np
from pathlib import Path
from .accuracy_v20.quality import assess
from .dynamic_v24.football import PlayKernel
from .fullgame_v23.replay import nba_book_players
from .fullgame_v23.nba_replay import replay
from .fullgame_v23.modes import context,Mode

class EditionTests(unittest.TestCase):
    cutoff='2024-09-23T23:30:00Z'
    def row(self):return {'classification':'confirmed','complete':True,'publishedAt':'2024-09-23T21:59:00Z','retrievedAt':'2026-11-07T01:00:00Z','source':'https://official.example.test/primary','sourceVersion':'synthetic'}
    def audit(self,row):return assess('NFL','synthetic',self.cutoff,{'injury':row})['components']['injury']
    def test_original_primary_timestamp_can_precede_later_retrieval(self):self.assertTrue(self.audit(self.row())['eligibleBeforeCutoff'])
    def test_future_revision_cannot_hide_behind_original_date(self):
        for key in ('modifiedAt','dateModified','availableAt'):
            self.assertFalse(self.audit(self.row()|{key:'2024-09-24T01:00:00Z'})['eligibleBeforeCutoff'])
    def test_equal_publication_is_not_strictly_before_cutoff(self):self.assertFalse(self.audit(self.row()|{'publishedAt':self.cutoff})['eligibleBeforeCutoff'])
    def test_equal_receipt_is_not_strictly_before_cutoff(self):
        r=self.row();r.pop('publishedAt');r.update(immutableReceipt=True,retrievedAt=self.cutoff)
        self.assertFalse(self.audit(r)['eligibleBeforeCutoff'])
    def test_old_receipt_remains_conditional_without_publication(self):
        r=self.row();r.pop('publishedAt');r.update(immutableReceipt=True)
        self.assertFalse(self.audit(r)['eligibleBeforeCutoff'])
    def test_missing_health_never_becomes_confirmed(self):self.assertFalse(assess('NBA','synthetic',self.cutoff,{})['missingMeansHealthy'])

class KernelBindingTests(unittest.TestCase):
    def kernel(self,owners):
        rows=[{'o':t,'kind':'rush','elapsed':30,'runner':t+'p'} for t in ('H','A') for _ in range(30)]
        return PlayKernel('NFL',['H','A'],rows,owners)
    def test_participant_ownership_is_part_of_exact_input_binding(self):
        self.assertNotEqual(self.kernel({'Hp':'H','Ap':'A'}).input_hash,self.kernel({'Hp':'A','Ap':'H'}).input_hash)
    def test_owner_dictionary_order_does_not_change_binding(self):self.assertEqual(self.kernel({'Hp':'H','Ap':'A'}).input_hash,self.kernel({'Ap':'A','Hp':'H'}).input_hash)
    def test_clock_candidate_never_mixes_completed_and_stopped_pass_intervals(self):
        from .fullgame_v23.rules import RegulationClock
        rows=[{'o':t,'kind':'pass','quarter':1,'clock':3500,'elapsed':elapsed,'complete':complete,'yards':5,'field':70} for t in ('H','A') for complete,elapsed in [(True,35),(False,5)] for _ in range(15)]
        kernel=PlayKernel('NFL',['H','A'],rows,{},condition_clock=True);rng=np.random.default_rng(27);clock=RegulationClock('NFL',2024)
        for _ in range(30):
            self.assertEqual(kernel.charge(rng,rows[0],clock,clock_stop=False)[0],35)
            self.assertEqual(kernel.charge(rng,rows[-1],clock,clock_stop=True)[0],5)
        self.assertNotEqual(kernel.input_hash,PlayKernel('NFL',['H','A'],rows,{}).input_hash)
    def test_missing_stopped_regime_is_withheld_not_given_running_time(self):
        from .fullgame_v23.rules import RegulationClock
        rows=[{'o':t,'kind':'rush','quarter':1,'clock':3500,'elapsed':35,'yards':5,'field':70} for t in ('H','A') for _ in range(30)]
        kernel=PlayKernel('NFL',['H','A'],rows,{},condition_clock=True)
        with self.assertRaises(ValueError):kernel.charge(np.random.default_rng(1),rows[0],RegulationClock('NFL',2024),clock_stop=True)

class PrimaryBookTests(unittest.TestCase):
    def table(self):
        lines=[]
        for side in ('VISITOR','HOME'):
            lines.append(side+': synthetic')
            for i in range(5):lines.append(str(i+1)+' Synthetic '+side+str(i)+' 48:00 '+' '.join('0' for _ in range(16)))
        return '\n'.join(lines)
    def test_layout_newline_never_merges_quarter_rows(self):
        for gap in ('','\n     ','   \n\t'):
            text=self.table()+"\nOFFICIAL SCORER'S REPORT"+gap+'1st QUARTER ONLY\n'+self.table().replace('48:00','12:00')
            players=nba_book_players(text,'A','H')
            self.assertEqual(len(players),10);self.assertTrue(all(p['seconds']==2880 for p in players))
    def test_duplicate_final_reference_is_rejected(self):
        with self.assertRaises(ValueError):nba_book_players(self.table()+'\n'+self.table(),'A','H')
    def alias_replay(self,ambiguous=False):
        players=[];bounds={}
        for side,team in [('VISITOR','A'),('HOME','H')]:
            for i in range(5):
                pid=team+str(i);name='Synthetic '+side+str(i)
                if pid=='H0':name='Jimmy Butler III'
                if pid=='H1' and ambiguous:name='Jimmy Butler Jr.'
                players.append({'athlete_id':str(len(players)+1),'team_id':team,'athlete_display_name':name,'minutes':48});bounds[str(len(players))]={'minuteBounds':[48,48]}
        game={'id':'synthetic','teams':{'A':{'team_home_away':'away','team_score':0},'H':{'team_home_away':'home','team_score':0}},'players':players};event={'id':'end','period_number':4,'clock_display_value':'0:00','type_text':'end','text':'end'}
        exposure={'eventCourts':[],'players':bounds,'allEventLineupsIdentified':True}
        with patch('modeling.fullgame_v23.nba_replay.game_exposures',return_value=exposure),patch('modeling.fullgame_v23.nba_replay.canonical_order',return_value=[event]):
            return replay(game,[event],self.table().replace('Synthetic HOME0','Jimmy Butler'),context(Mode.MECHANICS,'NBA','synthetic',[{'source':'https://source.example.test','sourceVersion':'synthetic'}]))
    def test_unique_same_team_suffix_alias_has_an_audit_record(self):
        r=self.alias_replay();self.assertEqual(len(r['officialNameAliases']),1);self.assertFalse(r['unmappedOfficialPlayers']);self.assertTrue(r['minuteBudgetReconciled'])
    def test_ambiguous_suffix_is_not_silently_joined(self):
        r=self.alias_replay(True);self.assertTrue(any(x['name']=='Jimmy Butler' for x in r['unmappedOfficialPlayers']));self.assertFalse(r['completeAccountingReplay'])

class SourceReaderTests(unittest.TestCase):
    def test_oversize_response_returns_no_partial_evidence(self):
        script=Path(__file__).resolve().parents[1]/'scripts/v26-capture.py';ns=runpy.run_path(str(script));get=ns['get'];gl=get.__globals__
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'X'*n
        with tempfile.TemporaryDirectory() as tmp,patch.dict(gl,{'OUT':Path(tmp),'urlopen':lambda *a,**k:Response()}):
            body,receipt=get('https://source.example.test/oversize.pdf')
            self.assertIsNone(body);self.assertNotIn('sourceVersion',receipt);self.assertNotIn('object',receipt)
            self.assertEqual(receipt['error'],'ValueError')

class OwnedBankTests(unittest.TestCase):
    def test_clock_certificate_uses_existing_ledger_tolerance_without_masking_errors(self):
        ns=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/v27-report.py'))
        self.assertTrue(ns['nba_time_valid'](2879.9999999999995,0));self.assertTrue(ns['nba_time_valid'](3180.,1))
        self.assertFalse(ns['nba_time_valid'](2879.,0));self.assertFalse(ns['nba_time_valid'](float('nan'),0))
    def test_league_qualified_roster_identity_prevents_cross_sport_id_collision(self):
        ns=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/v27-bank-shadow.py'))
        football='https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/4/roster?season=2026';nba='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/4/roster?season=2027'
        self.assertEqual(ns['nba_roster_source']([{'source':football},{'source':nba}],'4'),nba)
        with self.assertRaises(ValueError):ns['nba_roster_source']([{'source':football}],'4')
    def test_shared_owned_artifacts_resolve_both_sides_without_allowing_escape(self):
        from .dynamic_v24.completion.bank import HeadBank
        from .dynamic_v24.stat_models import StatModel
        from .overnight_v20.state import digest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);owned=root/'owner/artifacts/dynamic-v24';owned.mkdir(parents=True);work=root/'worktree';work.mkdir();(work/'artifacts').symlink_to(root/'owner/artifacts',target_is_directory=True)
            model=StatModel('rolling5','receptions');p=owned/'test.pickle';p.write_bytes(pickle.dumps(model));entry={'modelPath':'artifacts/dynamic-v24/test.pickle','modelSHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'stat':'receptions'};manifest={'heads':[entry]};manifest['sha256']=digest(manifest);bank=HeadBank(manifest,work)
            self.assertEqual(bank.load(entry).stat,'receptions')
            outside=root/'outside.pickle';outside.write_bytes(p.read_bytes());(owned/'escape.pickle').symlink_to(outside)
            with self.assertRaises(ValueError):bank.load(entry|{'modelPath':'artifacts/dynamic-v24/escape.pickle'})

if __name__=='__main__':unittest.main()
