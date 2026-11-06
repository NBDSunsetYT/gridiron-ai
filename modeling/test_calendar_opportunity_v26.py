import unittest
from .accuracy_v25.opportunity_calendar import project,observed,requested_team_total


class CalendarOpportunity(unittest.TestCase):
    def game(self,i,attempts=None,anonymous=0):
        ps={'starter':{'stats':{'passingAttempts':30.}}}
        if attempts is not None:ps['backup']={'stats':{'passingAttempts':float(attempts)}}
        return {'eventId':'SYNTHETIC-'+str(i),'teams':{'T':{'players':ps,'totals':{'passingAttempts':sum(p['stats']['passingAttempts'] for p in ps.values())+anonymous}}}}
    def test_calendar_mean_reconciles_unequal_appearance_denominators(self):
        games=[self.game(i,5 if i<3 else None) for i in range(5)];raw={g['eventId']:{} for g in games}
        p=project(games,raw,'CFB','T','backup','passingAttempts')
        self.assertEqual(p['reference'],5.);self.assertEqual(p['candidate'],3.)
        self.assertEqual(sum([30.,p['candidate']]),sum(g['teams']['T']['totals']['passingAttempts'] for g in games)/5)
    def test_anonymous_credits_are_not_given_to_an_arbitrary_backup(self):
        g=self.game(1,None,anonymous=2)
        value,reason=observed(g,{},'CFB','T','backup','passingAttempts');self.assertIsNone(value);self.assertIn('anonymous',reason)
    def test_absent_nba_row_is_unknown_but_explicit_dnp_is_a_historical_zero(self):
        g={'teams':{'T':{'players':{},'totals':{}}}}
        self.assertIsNone(observed(g,{},'NBA','T','p','minutes')[0])
        raw={'boxscore':{'players':[{'team':{'id':'T'},'statistics':[{'athletes':[{'athlete':{'id':'p'},'didNotPlay':True,'stats':[]}]}]}]}}
        self.assertEqual(observed(g,raw,'NBA','T','p','minutes')[0],0.)

    def test_nfl_gross_passing_is_not_team_net_and_ncaa_does_not_add_sacks(self):
        g={'teams':{'T':{'totals':{'passingYards':-2},'players':{}}}}
        raw={'boxscore':{'teams':[{'team':{'id':'T'},'statistics':[{'name':'netPassingYards','displayValue':'-2'},{'name':'sacksYardsLost','displayValue':'1-2'}]}]}}
        self.assertEqual(requested_team_total(g,raw,'NFL','T','passingYards'),0.)
        self.assertEqual(requested_team_total(g,raw,'CFB','T','passingYards'),-2.)

    def test_matching_attempts_do_not_prove_unknown_yardage_credit_is_zero(self):
        g=self.game(1,None);g['teams']['T']['totals']['rushingYards']=10;g['teams']['T']['totals']['carries']=1
        g['teams']['T']['players']['starter']['stats'].update(carries=1,rushingYards=5)
        self.assertIsNone(observed(g,{},'CFB','T','unknown','rushingYards')[0])


if __name__=='__main__':unittest.main()
