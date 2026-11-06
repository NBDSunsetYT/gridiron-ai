"""V26 regressions for actual pregame source failures, no accuracy claim."""
import unittest
from unittest.mock import patch,MagicMock
from .fullgame_v23.evidence import nba_rows
from .accuracy_v25.leakage import source_fact_guard
from .accuracy_v25.evaluation import feature_guard
from .overnight_v20.state import digest


class ReportRecovery(unittest.TestCase):
    def test_wrapped_not_submitted_reason_never_becomes_available(self):
        labels=['GameDate','GameTime','Matchup','Team','PlayerName','CurrentStatus','Reason']
        words=[{'text':k,'x0':i*100.,'top':70.,'bottom':80.} for i,k in enumerate(labels)]
        for text,x,top in [('11/06/2026',0,100),('BOS@CHA',200,100),('Boston',300,100),('NOTYETSUBMITTED',400,100),('report pending',600,120)]:
            words.append({'text':text,'x0':float(x),'top':float(top),'bottom':float(top+8)})
        page=MagicMock();page.extract_text.return_value='Injury Report: 11/06/26 06:15 PM';page.extract_words.return_value=words;page.width=800
        pdf=MagicMock();pdf.__enter__.return_value.pages=[page]
        with patch('modeling.fullgame_v23.evidence.pdfplumber.open',return_value=pdf):rows,issued=nba_rows(b'SYNTHETIC')
        self.assertEqual(issued,'2026-11-06T23:15:00+00:00');self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'not_yet_submitted');self.assertNotIn('name',rows[0]);self.assertEqual(rows[0]['reason'],'report pending')

    def fact(self):
        receipt={'url':'https://example.test/prospective','sourceVersion':'SYNTHETIC','httpStatus':200,'immutableReceipt':True,'requestStartedAt':'2026-11-06T20:00:00Z','retrievedAt':'2026-11-06T20:00:01Z'}
        receipt|={'sha256':digest(receipt)}
        return {'source':receipt['url'],'sourceVersion':receipt['sourceVersion'],'retrievedAt':receipt['retrievedAt'],'captureReceipt':receipt,'kind':'historical_statistics','eventId':'OLD','teamId':'A','gameStatus':'final','gameCompletedObservedAt':receipt['retrievedAt']}

    def test_actual_pre_cutoff_capture_proves_availability_without_fake_publication(self):
        f=self.fact();r=source_fact_guard(f,'2026-11-06T21:00:00Z','FUTURE')
        self.assertEqual(r['availabilityEvidence'],'immutable_pre_cutoff_capture');self.assertNotIn('publishedAt',f)
        self.assertFalse(r['unconditionalForecastAuthorized'])

    def test_receipt_after_historical_cutoff_and_tampering_are_rejected(self):
        f=self.fact()
        with self.assertRaises(ValueError):source_fact_guard(f,'2026-11-05T21:00:00Z','FUTURE')
        f['captureReceipt']['httpStatus']=403
        with self.assertRaises(ValueError):source_fact_guard(f,'2026-11-06T21:00:00Z','FUTURE')

    def test_known_recent_history_needs_real_proof_not_a_feature_flag(self):
        row={'gameId':'FUTURE','team':'A','player':'p','stat':'rebounds','at':'2026-11-06T21:00:00Z','featureLastGame':'2026-11-06T01:00:00Z','featureLastGameId':'OLD'}
        with self.assertRaises(ValueError):feature_guard([row],'2026-10-01T00:00:00Z',evidence_tier='conditional_corrected_history')
        p=source_fact_guard(self.fact(),row['at'],'FUTURE')
        feature_guard([row],'2026-10-01T00:00:00Z',evidence_tier='conditional_corrected_history',availability_proofs=[p])
        with self.assertRaises(ValueError):feature_guard([row|{'featureLastGameId':'UNRELATED'}],'2026-10-01T00:00:00Z',evidence_tier='conditional_corrected_history',availability_proofs=[p])
        with self.assertRaises(ValueError):feature_guard([row|{'featureLastGame':row['at']}],'2026-10-01T00:00:00Z',evidence_tier='conditional_corrected_history',availability_proofs=[p])

    def test_pre_cutoff_receipt_cannot_override_future_publisher_timestamp(self):
        with self.assertRaises(ValueError):source_fact_guard(self.fact()|{'publishedAt':'2026-11-07T00:00:00Z'},'2026-11-06T21:00:00Z','FUTURE')


if __name__=='__main__':unittest.main()
