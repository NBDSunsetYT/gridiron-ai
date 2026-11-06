"""Negative controls and the requested temporal-leakage rejection cases."""
import copy,unittest
from .accuracy_v25.leakage import source_fact_guard,feature_names_guard,shuffle_control,forecast_lineage_guard
from .accuracy_v25.evaluation import feature_guard


class LeakageControls(unittest.TestCase):
    cutoff='2024-01-10T18:00:00Z'
    def fact(self,kind='lineup'):
        return {'kind':kind,'eventId':'SYNTHETIC','source':'https://example.test/synthetic','sourceVersion':'SYNTHETIC','publishedAt':'2024-01-10T16:00:00Z','availableAt':'2024-01-10T16:00:00Z','editionPublishedAt':'2024-01-10T16:00:00Z','retrievedAt':'2024-01-10T17:00:00Z','sourceRole':'official_pregame_report','status':'uncertain'}
    def test_unknown_availability_never_becomes_healthy(self):
        r=source_fact_guard(self.fact('injury'),self.cutoff,'SYNTHETIC');self.assertEqual(r['availabilityStatus'],'uncertain');self.assertFalse(r['unconditionalForecastAuthorized'])
    def test_postgame_participation_and_final_rosters_rejected(self):
        for kind in ('participation','lineup','injury'):
            with self.assertRaises(ValueError):source_fact_guard(self.fact(kind)|{'sourceRole':'final_box'},self.cutoff,'SYNTHETIC')
    def test_future_same_day_results_rejected(self):
        f=self.fact('historical_statistics')|{'eventId':'OTHER','gameEndedAt':'2024-01-10T19:00:00Z'}
        with self.assertRaises(ValueError):source_fact_guard(f,self.cutoff,'SYNTHETIC')
        f['gameEndedAt']='2024-01-09T19:00:00Z';source_fact_guard(f,self.cutoff,'SYNTHETIC')
    def test_current_final_statistics_are_never_a_prior(self):
        f=self.fact('historical_statistics')|{'gameEndedAt':'2024-01-09T19:00:00Z'}
        with self.assertRaises(ValueError):source_fact_guard(f,self.cutoff,'SYNTHETIC')
    def test_closing_line_after_forecast_cutoff_rejected(self):
        f=self.fact('market')|{'product':'sportsbook','capturedAt':'2024-01-10T18:01:00Z'}
        with self.assertRaises(ValueError):source_fact_guard(f,self.cutoff,'SYNTHETIC')
        f['capturedAt']='2024-01-10T17:59:00Z';source_fact_guard(f,self.cutoff,'SYNTHETIC')
    def test_revised_edition_cannot_masquerade_as_original(self):
        f=self.fact()|{'editionPublishedAt':'2024-01-11T16:00:00Z'}
        with self.assertRaises(ValueError):source_fact_guard(f,self.cutoff,'SYNTHETIC')
    def test_late_retrieval_requires_verified_archived_edition(self):
        f=self.fact()|{'retrievedAt':'2026-01-01T00:00:00Z'}
        with self.assertRaises(ValueError):source_fact_guard(f,self.cutoff,'SYNTHETIC')
        source_fact_guard(f|{'originalEditionVerified':True},self.cutoff,'SYNTHETIC')
    def test_outcome_aliases_cannot_hide_in_feature_names(self):
        for name in ('actual_minutes','final_roster','homeFinalScore','finalInjuryStatus','y'):
            with self.assertRaises(ValueError):feature_names_guard(['prior_minutes',name])
        feature_names_guard(['prior_minutes','opponent_strength'])
    def test_research_ingress_cannot_skip_lineage_or_hide_an_outcome_alias(self):
        row={'gameId':'SYNTHETIC','team':'A','player':'p','stat':'rebounds','at':self.cutoff,'featureLastGame':'2024-01-01T00:00:00Z','sourceEditionVerified':True,'missingEvidence':[],'missingAvailability':False,'statisticsPublishedAt':'2024-01-09T00:00:00Z','injuryPublishedAt':'2024-01-09T00:00:00Z','lineupPublishedAt':'2024-01-09T00:00:00Z','participationPublishedAt':'2024-01-09T00:00:00Z'}
        with self.assertRaises(ValueError):forecast_lineage_guard([row],[],self.cutoff,'SYNTHETIC','2024-01-02T00:00:00Z')
        facts=[self.fact(k)|{'status':'confirmed'} for k in ('injury','lineup','participation')]+[self.fact('historical_statistics')|{'eventId':'EARLIER','gameEndedAt':'2024-01-08T00:00:00Z'}]
        self.assertTrue(forecast_lineage_guard([row],facts,self.cutoff,'SYNTHETIC','2024-01-02T00:00:00Z')['jointMechanicsCertificateStillRequired'])
        with self.assertRaises(ValueError):forecast_lineage_guard([row|{'actualMinutes':32}],facts,self.cutoff,'SYNTHETIC','2024-01-02T00:00:00Z')
        uncertain=[dict(f,status='uncertain') if f['kind']=='injury' else f for f in facts]
        with self.assertRaises(ValueError):forecast_lineage_guard([row],uncertain,self.cutoff,'SYNTHETIC','2024-01-02T00:00:00Z')
    def test_deterministic_shuffles_preserve_originals_and_reject_future_history(self):
        rows=[{'gameId':'SYNTHETIC-'+str(i),'team':'A','player':'p'+str(i),'stat':'rebounds','at':self.cutoff,'featureLastGame':'2024-01-01T00:00:00Z','x':[float(j+i) for j in range(26)]} for i in range(8)];before=copy.deepcopy(rows)
        for kind in ('player_identity','team_score_context'):
            self.assertEqual(shuffle_control(rows,kind),shuffle_control(rows,kind));self.assertEqual(rows,before)
        with self.assertRaises(ValueError):feature_guard(shuffle_control(rows,'future_history'),'2024-01-02T00:00:00Z',evidence_tier='conditional_corrected_history')
        with self.assertRaises(ValueError):shuffle_control(rows,'market')


if __name__=='__main__':unittest.main()
