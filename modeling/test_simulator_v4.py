"""Explicit SYNTHETIC mechanics tests; never packaged as NFL evidence."""
import csv
import io
import json
import unittest
from datetime import timedelta
from modeling.fit import fit_csv,utc,VERSION,ENHANCED_VERSION
from modeling.simulator import simulate,simulate_game,Evidence
from modeling.test_simulator import fixture_csv,MechanicalEvidence
import random


def eight_games(with_provenance=False):
    original=list(csv.DictReader(io.StringIO(fixture_csv())))
    fields=list(original[0])+['epa','success']
    if with_provenance:fields+=['available_at','collected_at','source_version','reliability']
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    for repeat in (0,1):
        for r in original:
            row={**r,'game_id':r['game_id']+('-SECOND' if repeat else ''),'played_at':(utc(r['played_at'])+timedelta(days=repeat*4)).isoformat(),'epa':.25,'success':1}
            if with_provenance:row.update(available_at='2024-01-10T00:00:00Z',collected_at='2024-01-11T00:00:00Z',source_version='SYNTHETIC-V1',reliability='verified')
            writer.writerow(row)
    return stream.getvalue()


class EnhancedSimulationTests(unittest.TestCase):
    def test_legacy_artifact_version_preserved_and_enhanced_fit_declares_features(self):
        old=fit_csv(fixture_csv(),'SYNTHETIC ONLY','2024-02-01T00:00:00Z')['model']
        self.assertEqual(old['version'],VERSION)
        result=fit_csv(eight_games(),'SYNTHETIC ONLY','2024-02-01T00:00:00Z',options={'recencyHalfLifeDays':180,'conditionalShrinkage':True})
        self.assertEqual(result['model']['version'],ENHANCED_VERSION)
        self.assertIn(result['model']['shrinkageFit']['priorPlays'],[5,20,50])
        research=result['model']['teamResearch']['SYNTH-A']
        self.assertAlmostEqual(research['historicalOffenseEPA']['value'],.25)
        self.assertIsNone(research['routeParticipation']);self.assertIsNone(research['snapShares'])
        self.assertFalse(result['model']['dataAvailabilityVerified'])

    def test_strict_availability_gates_unknown_or_future_evidence(self):
        with self.assertRaisesRegex(ValueError,'Strict availability'):
            fit_csv(eight_games(),'SYNTHETIC','2024-02-01T00:00:00Z',options={'strictAvailability':True})
        fitted=fit_csv(eight_games(True),'SYNTHETIC','2024-02-01T00:00:00Z',options={'strictAvailability':True})
        self.assertTrue(fitted['model']['dataAvailabilityVerified'])
        with self.assertRaisesRegex(ValueError,'availability'):
            fit_csv(eight_games(True).replace('2024-01-10T00:00:00Z','2024-03-01T00:00:00Z'),'SYNTHETIC','2024-02-01T00:00:00Z')

    def test_parameter_interval_separate_and_unchanged_by_base_game_count(self):
        model=fit_csv(eight_games(),'SYNTHETIC ONLY','2024-02-01T00:00:00Z')['model']
        options={'replicates':10,'gamesPerReplicate':100}
        a=simulate(model,'SYNTH-A','SYNTH-B',100,12,'2024-03-01T00:00:00Z',parameter_uncertainty=options)
        b=simulate(model,'SYNTH-A','SYNTH-B',200,12,'2024-03-01T00:00:00Z',parameter_uncertainty=options)
        self.assertEqual(a['uncertainty']['parameterBootstrap'],b['uncertainty']['parameterBootstrap'])
        self.assertEqual(a['uncertainty']['parameterBootstrap']['completeGames'],1000)
        self.assertIsNotNone(a['uncertainty']['modelInterval'])
        self.assertIn('noise',a['uncertainty']['parameterBootstrap']['method'])

    def test_parameter_work_is_rejected_early_when_not_identifiable(self):
        model=fit_csv(fixture_csv(),'SYNTHETIC ONLY','2024-02-01T00:00:00Z')['model']
        with self.assertRaisesRegex(ValueError,'8 historical'):
            simulate(model,'SYNTH-A','SYNTH-B',10000,12,'2024-03-01T00:00:00Z',parameter_uncertainty={'replicates':10,'gamesPerReplicate':100})
        with self.assertRaisesRegex(ValueError,'10..40'):
            simulate(model,'SYNTH-A','SYNTH-B',10000,12,'2024-03-01T00:00:00Z',parameter_uncertainty={'replicates':1,'gamesPerReplicate':100})

    def test_representative_trace_retains_shared_event_identities(self):
        model=fit_csv(eight_games(),'SYNTHETIC ONLY','2024-02-01T00:00:00Z')['model']
        result=simulate(model,'SYNTH-A','SYNTH-B',2,4,'2024-03-01T00:00:00Z',representative_games=1)
        game=result['representativeGames'][0]
        self.assertGreater(len(game['plays']),40)
        passes=[p for p in game['plays'] if p['kind']=='pass']
        self.assertTrue(all(p['passerId'] and p['receiverId'] and p['historicalGameId'] for p in passes))
        for team in ['SYNTH-A','SYNTH-B']:
            self.assertEqual(game['players'][team+'-QB']['passingYards'],game['players'][team+'-WR']['receivingYards'])

    def test_spike_is_an_official_passing_attempt(self):
        score,players,environment,_=simulate_game(MechanicalEvidence('spike'),random.Random(1),['SYNTH-A','SYNTH-B'])
        self.assertEqual(sum(p['passingAttempts'] for p in players.values()),environment['plays'])
        self.assertEqual(sum(p['completions'] for p in players.values()),0)

    def test_overtime_safety_trace_includes_the_deciding_play_and_score(self):
        score,_,environment,trace=simulate_game(MechanicalEvidence('sack',-99),random.Random(1),['SYNTH-A','SYNTH-B'],trace=True)
        self.assertEqual(len(trace),environment['plays'])
        self.assertEqual(trace[-1]['score'],score)
        self.assertTrue(trace[-1]['safety'])
        self.assertTrue(trace[-1]['overtime'])


if __name__=='__main__':unittest.main()
