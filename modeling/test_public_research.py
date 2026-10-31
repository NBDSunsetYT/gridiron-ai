"""SYNTHETIC boundaries for automatic research; real fetch/run is audited separately."""
from datetime import datetime, timezone
import io
import csv
import os
import gzip
import hashlib
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from modeling.service import app
from modeling.public_research import (ResearchUnavailable, validate_game, source_url,
    select_plays, current_rosters, injury_records, availability_labels,
    normalized_evidence, player_usage, verified_statistics, BoundedReader, analyze_public, fetch_dataset, stamp,automatic_feature_version)

NOW = datetime(2026,10,30,12,tzinfo=timezone.utc)
GAME = {'id':'2026_08_BAL_BUF','home':'BUF','away':'BAL','startTime':'2026-11-01T18:00:00Z','season':2026,'week':8}


class SyntheticDataset:
    def __init__(self, rows):
        self.value = rows
    def rows(self):
        return iter(self.value)


def play(identity='SYNTHETIC-GAME', at='2026-10-01T17:00:00Z', team='BUF', **extra):
    return {'season_type':'REG','season':'2026','week':'4','game_id':identity,'play_id':'1','posteam':team,'defteam':'BAL' if team=='BUF' else 'BUF',
            'play_type':'run','game_half':'Half1','game_seconds_remaining':'3570','down':'1','ydstogo':'10','yardline_100':'75',
            'time_of_day':at,'fixed_drive':'1','rusher_player_id':'SYNTHETIC-RB','rusher_player_name':'SYNTHETIC Runner','yards_gained':'5',**extra}


class PublicResearchTests(unittest.TestCase):
    def test_game_must_be_future_real_team_pair_and_no_guest_urls(self):
        self.assertEqual(validate_game(GAME,NOW)['home'],'BUF')
        with self.assertRaisesRegex(ValueError,'Kickoff'):
            validate_game({**GAME,'startTime':'2026-10-29T00:00:00Z'},NOW)
        with self.assertRaisesRegex(ValueError,'recognized NFL'):
            validate_game({**GAME,'home':'http://169.254.169.254/'},NOW)
        with self.assertRaisesRegex(ValueError,'distinct'):
            validate_game({**GAME,'away':'BUF'},NOW)
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            source_url('https://untrusted.invalid/secret',2026)
        self.assertEqual(source_url('pbp',2026),'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz')

    def test_no_future_plays_or_missing_event_timestamps_are_invented(self):
        rows=[play('SYNTH-OLD'),play('SYNTH-NEW','2026-10-02T17:00:00Z'),play('SYNTH-FUTURE','2026-11-02T17:00:00Z'),play('SYNTH-UNKNOWN','')]
        selected,names=select_plays(SyntheticDataset(rows),{'BUF','BAL'},NOW,max_games=1)
        self.assertEqual({row['game_id'] for row in selected},{'SYNTH-NEW'})
        self.assertEqual(names['SYNTHETIC-RB'],'SYNTHETIC Runner')

    def test_current_roster_uses_actual_latest_snapshot_for_each_team(self):
        roster,week=current_rosters([
            {'team':'BUF','week':'8','gsis_id':'SYNTH-BUF'},
            {'team':'BUF','week':'7','gsis_id':'SYNTH-OLD'},
            {'team':'BAL','week':'7','gsis_id':'SYNTH-BAL'},
            {'team':'BAL','week':'9','gsis_id':'SYNTH-FUTURE'}],{'BUF','BAL'},8)
        self.assertEqual(set(roster),{'SYNTH-BUF','SYNTH-BAL'})
        self.assertEqual(week,7)

    def test_questionable_is_not_assumed_active_and_publication_is_unknown(self):
        source={'url':'https://example.invalid/SYNTHETIC','sourceUpdatedAt':'2026-10-30T00:00:00Z','checkedAt':'2026-10-30T12:00:00Z'}
        rows=injury_records([
            {'team':'BUF','week':'8','gsis_id':'SYNTH-Q','full_name':'SYNTHETIC Q','report_status':'Questionable','practice_status':'Limited Participation in Practice'},
            {'team':'BAL','week':'8','gsis_id':'SYNTH-O','full_name':'SYNTHETIC O','report_status':'Out'},
            {'team':'BUF','week':'7','gsis_id':'SYNTH-OLD','report_status':'Out'}],{'BUF','BAL'},8,source)
        self.assertEqual(len(rows),2)
        self.assertIsNone(rows[0]['availability'])
        self.assertIsNone(rows[0]['publicationAt'])
        self.assertFalse(rows[1]['confirmedInactive'])
        self.assertEqual(rows[1]['availability']['out'],1)

    def test_historical_inactive_labels_require_explicit_out_and_conflicts_are_not_silently_accepted(self):
        raw=[play(),play(play_id='2',rusher_player_id='SYNTH-ACTIVE')]
        roster={'SYNTH-SNAP':{'pfr_id':'SYNTH-PFR'}}
        injuries=[{'season':'2026','week':'4','team':'BUF','gsis_id':'SYNTH-OUT','report_status':'Out'},
                  {'season':'2026','week':'4','team':'BUF','gsis_id':'SYNTH-ACTIVE','report_status':'Out'},
                  {'season':'2026','week':'4','team':'BUF','gsis_id':'SYNTH-UNKNOWN','report_status':'Questionable'}]
        snaps=[{'game_id':'SYNTHETIC-GAME','pfr_player_id':'SYNTH-PFR','offense_snaps':'5'},
               {'game_id':'SYNTHETIC-GAME','pfr_player_id':'SYNTH-NOT-MAPPED','offense_snaps':'9'}]
        labels,conflicts=availability_labels(raw,injuries,snaps,roster)
        self.assertEqual(labels['SYNTHETIC-GAME'],{'SYNTH-SNAP':'active','SYNTH-OUT':'inactive'})
        self.assertEqual(conflicts,1)
        self.assertNotIn('SYNTH-UNKNOWN',labels['SYNTHETIC-GAME'])
        self.assertNotIn('SYNTH-NOT-MAPPED',labels['SYNTHETIC-GAME'])

    def test_collection_provenance_does_not_rewrite_event_time(self):
        raw=[play(),play(play_id='2',game_seconds_remaining='3530')]
        text,report=normalized_evidence(raw,{'SYNTHETIC-GAME':{'SYNTH-OUT':'inactive'}},'SYNTHETIC-source-v1','2026-10-30T12:00:00Z')
        rows=list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(rows[0]['played_at'],'2026-10-01T17:00:00Z')
        self.assertEqual(rows[0]['available_at'],'2026-10-30T12:00:00Z')
        self.assertEqual(rows[0]['availability'],'{"SYNTH-OUT":"inactive"}')
        self.assertIn('Missing data never means inactive',report['availabilityProvenance'])

    def test_feature_fingerprint_ignores_collection_clocks_and_report_order_but_preserves_material_changes(self):
        reports=[{'playerId':'SYNTH-Q','team':'BUF','status':'questionable','practiceParticipation':'limited','injury':'ankle','week':8,'checkedAt':'2026-10-30T12:00:00Z'},
                 {'playerId':'SYNTH-WR','team':'BAL','status':'out','week':8,'checkedAt':'2026-10-30T12:00:00Z'}]
        roster={'SYNTH-Q':{'team':'BUF','status':'ACT'},'SYNTH-WR':{'team':'BAL','status':'ACT'}}
        original=automatic_feature_version('SYNTH-SOURCE-V1',None,reports,roster,[])
        refreshed=[{**row,'checkedAt':'2026-10-31T12:00:00Z','sourceUpdatedAt':'2026-10-31T12:00:00Z'} for row in reversed(reports)]
        self.assertEqual(original,automatic_feature_version('SYNTH-SOURCE-V1',None,refreshed,roster,[]))
        self.assertNotEqual(original,automatic_feature_version('SYNTH-SOURCE-V2',None,reports,roster,[]))
        self.assertNotEqual(original,automatic_feature_version('SYNTH-SOURCE-V1',None,[{**reports[0],'status':'out'},reports[1]],roster,[]))
        self.assertNotEqual(original,automatic_feature_version('SYNTH-SOURCE-V1',None,reports,{**roster,'SYNTH-Q':{'team':'BUF','status':'RES'}},[]))

    def test_reported_injury_and_nonactive_roster_player_predictions_are_withheld(self):
        model={'rows':[{'qb':'SYNTH-Q','receiver':'SYNTH-WR','runner':'','o':'BUF','at':'2026-10-01T17:00:00Z','game':'SYNTH-G'}],
               'teamResearch':{'BUF':{'targetShares':{'SYNTH-WR':1},'carryShares':{}}}}
        roster={'SYNTH-Q':{'team':'BUF','position':'QB','status':'ACT','full_name':'SYNTHETIC Q'},'SYNTH-WR':{'team':'BUF','position':'WR','status':'RES','full_name':'SYNTHETIC WR'}}
        usage,withheld=player_usage(model,roster,[],[{'playerId':'SYNTH-Q','status':'questionable','availabilityAssessment':'Uncertain SYNTHETIC fixture'}],{}, {'BUF','BAL'})
        self.assertTrue(usage['SYNTH-Q']['projectionWithheld'])
        self.assertTrue(usage['SYNTH-WR']['projectionWithheld'])
        self.assertIsNone(usage['SYNTH-WR']['routeParticipation'])
        self.assertEqual(set(withheld),{'SYNTH-Q','SYNTH-WR'})

    def test_weekly_statistics_keep_future_week_out_and_shares_use_observed_team_totals(self):
        player=[{'player_id':'SYNTH-WR','player_display_name':'SYNTHETIC WR','team':'BUF','season_type':'REG','week':'7','targets':'8','receptions':'6','receiving_yards':'80'},
                {'player_id':'SYNTH-WR','team':'BUF','season_type':'REG','week':'8','targets':'99','receptions':'99','receiving_yards':'999'}]
        team=[{'team':'BUF','season_type':'REG','week':'7','targets':'40','carries':'20'},
              {'team':'BUF','season_type':'REG','week':'8','targets':'99','carries':'99'}]
        observed,teams=verified_statistics(player,team,{'BUF','BAL'},8)
        self.assertEqual(observed['SYNTH-WR']['totals']['receiving_yards'],80)
        self.assertEqual(observed['SYNTH-WR']['targetShare'],.2)
        self.assertEqual(teams['BUF']['totals']['targets'],40)
        self.assertEqual(observed['SYNTH-WR']['games'],1)
        self.assertIsNone(observed['SYNTH-WR']['totals']['passing_yards'])

    def test_automatic_source_failure_never_substitutes_a_fit_or_probability(self):
        def unavailable(kind,season):
            raise ResearchUnavailable('SYNTHETIC upstream unavailable')
        with patch('modeling.public_research.fit_csv') as fit:
            with self.assertRaisesRegex(ValueError,'upstream unavailable'):
                analyze_public({'game':GAME},fetcher=unavailable,now=NOW)
            fit.assert_not_called()

    def test_unsupported_guest_counts_and_dataset_payloads_fail_before_fetching(self):
        with patch('modeling.public_research.fetch_dataset') as source:
            for count in (True,10000.0,999,100001):
                with self.assertRaisesRegex(ValueError,'complete games'):
                    analyze_public({'game':GAME,'simulations':count},fetcher=source,now=NOW)
            with self.assertRaisesRegex(ValueError,'trusted game'):
                analyze_public({'game':GAME,'csv':'SYNTHETIC CSV cannot be submitted through automatic research'},fetcher=source,now=NOW)
            source.assert_not_called()

    def test_download_expansion_bound_is_enforced_before_unlimited_allocation(self):
        with patch('modeling.public_research.MAX_EXPANDED',8):
            reader=BoundedReader(io.BytesIO(b'SYNTHETIC source larger than declared bound'))
            with self.assertRaisesRegex(ValueError,'expansion bound'):
                reader.readinto(bytearray(32))

    def test_cached_asset_change_downloads_new_bytes_before_publishing(self):
        class Response(io.BytesIO):
            def __init__(self, body, etag):
                super().__init__(body)
                self.headers = {'ETag':etag}
        url = source_url('rosters',2026)
        key = hashlib.sha256(url.encode()).hexdigest()
        old = gzip.compress(b'team,week,gsis_id,pfr_id,status,full_name\nBUF,8,SYNTH-OLD,old,ACT,SYNTHETIC Old\n')
        current = gzip.compress(b'team,week,gsis_id,pfr_id,status,full_name\nBUF,8,SYNTH-NEW,new,ACT,SYNTHETIC New\n')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'GRIDIRON_PUBLIC_CACHE_DIR':directory}):
            root = Path(directory)
            (root/(key+'.csv.gz')).write_bytes(old)
            (root/(key+'.json')).write_text(json.dumps({'schemaVerified':True,'checkedAt':stamp(),'etag':'SYNTH-OLD'}))
            with patch('modeling.public_research.urllib.request.urlopen',side_effect=[Response(b'','SYNTH-NEW'),Response(current,'SYNTH-NEW')]) as upstream:
                result = fetch_dataset('rosters',2026)
                self.assertEqual(next(result.rows())['gsis_id'],'SYNTH-NEW')
                self.assertEqual(result.metadata['etag'],'SYNTH-NEW')
                self.assertEqual(upstream.call_count,2)
                self.assertEqual(upstream.call_args_list[0].args[0].method,'HEAD')

    def test_cached_matching_asset_is_verified_without_another_download(self):
        class Response(io.BytesIO):
            headers = {'ETag':'SYNTH-SAME'}
        url = source_url('rosters',2026)
        key = hashlib.sha256(url.encode()).hexdigest()
        content = gzip.compress(b'team,week,gsis_id,pfr_id,status,full_name\nBUF,8,SYNTH-SAME,same,ACT,SYNTHETIC Same\n')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'GRIDIRON_PUBLIC_CACHE_DIR':directory}):
            root = Path(directory)
            (root/(key+'.csv.gz')).write_bytes(content)
            (root/(key+'.json')).write_text(json.dumps({'schemaVerified':True,'checkedAt':stamp(),'etag':'SYNTH-SAME'}))
            with patch('modeling.public_research.urllib.request.urlopen',return_value=Response(b'')) as upstream:
                result = fetch_dataset('rosters',2026)
                self.assertEqual(next(result.rows())['gsis_id'],'SYNTH-SAME')
                self.assertIn('lastCheckedAt',result.metadata)
                upstream.assert_called_once()
                self.assertEqual(upstream.call_args.args[0].method,'HEAD')

    def test_private_automatic_endpoint_rejects_guests_and_preserves_authenticated_dispatch(self):
        with patch.dict(os.environ,{'SIMULATION_SERVICE_TOKEN':'SYNTHETIC-PUBLIC-SERVICE-KEY-0123456789'}),TestClient(app) as client:
            self.assertEqual(client.post('/public/analyze',json={'game':GAME}).status_code,401)
            with patch('modeling.public_research.analyze_public',return_value={'result':{'simulations':10000},'requiresDatasetUpload':False}) as calculate:
                response=client.post('/public/analyze',json={'game':GAME},headers={'Authorization':'Bearer SYNTHETIC-PUBLIC-SERVICE-KEY-0123456789'})
                self.assertEqual(response.status_code,200)
                self.assertFalse(response.json()['requiresDatasetUpload'])
                calculate.assert_called_once_with({'game':GAME})


if __name__=='__main__':
    unittest.main()
