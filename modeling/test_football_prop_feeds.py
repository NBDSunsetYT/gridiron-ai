"""Synthetic mechanics only; no fixture is live market evidence."""
import copy,json,os,time,unittest
from unittest.mock import patch
from .football_prop_feeds import PropLineClient,normalize,choose_feed,DataProviderError
class FreePropsTests(unittest.TestCase):
 def setUp(self):
  self.now=time.time();self.at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(self.now));self.env=patch.dict(os.environ,{'RENDER':'true','RENDER_SERVICE_ID':'SYNTHETIC','PROPLINE_API_KEY':'SYNTHETIC-PRIVATE'});self.env.start()
  self.board=[{'id':'SYNTHETIC','sport_key':'football_nfl','home_team':'SYNTHETIC HOME','away_team':'SYNTHETIC AWAY','commence_time':'2099-01-01T00:00:00Z','bookmakers':[{'key':'draftkings','markets':[{'key':'player_pass_yds','last_update':self.at,'outcomes':[{'name':'Over','description':'SYNTHETIC PLAYER','player_id':'espn:1','point':250.5,'price':-110,'last_seen_at':self.at}]}]}]}]
 def tearDown(self):self.env.stop()
 def test_normalize_sportsbook_not_contract(self):
  rows,n=normalize(self.board,'NFL',self.now);self.assertEqual(len(rows),1);self.assertFalse(rows[0]['draftKingsPredictionsEquivalent']);self.assertEqual(rows[0]['threshold'],'250.5');self.assertIsNone(rows[0]['modelProbability']);self.assertIsNone(rows[0]['quotedAt'])
 def test_separate_sports(self):self.assertEqual(normalize(self.board,'CFB',self.now)[0],[])
 def test_reject_stale_withdrawn_prices_and_unrelated_books(self):
  for change in [{'price':None},{'price':True},{'price':0},{'last_seen_at':'2000-01-01T00:00:00Z'}]:
   board=copy.deepcopy(self.board);board[0]['bookmakers'][0]['markets'][0]['outcomes'][0].update(change);self.assertEqual(normalize(board,'NFL',self.now)[0],[])
  self.board[0]['bookmakers'][0]['key']='kalshi';self.assertEqual(normalize(self.board,'NFL',self.now)[0],[])
 def test_render_guard_before_credentials(self):
  with patch.dict(os.environ,{'RENDER':'false'}):
   with self.assertRaises(DataProviderError):PropLineClient().read('NFL')
 def test_header_only_credentials_and_cache(self):
  calls=[]
  def transport(url,key):calls.append(url);self.assertNotIn('SYNTHETIC-PRIVATE',url);return 200,{},json.dumps(self.board).encode()
  c=PropLineClient(transport);self.assertEqual(len(c.read('NFL')['items']),1);self.assertTrue(c.read('NFL')['cached']);self.assertEqual(len(calls),3)
 def test_quota_exhaustion_no_retry_or_paid_upgrade(self):
  calls=[]
  def t(u,k):calls.append(u);return 429,{'X-Daily-Remaining':'0','X-Daily-Reset':str(int(self.now+3600))},b''
  c=PropLineClient(t)
  for i in range(2):
   with self.assertRaises(DataProviderError):c.read('NFL')
  self.assertEqual(len(calls),1)
 def test_invalid_json(self):
  with self.assertRaises(DataProviderError):PropLineClient(lambda u,k:(200,{},b'bad')).read('NFL')
 def test_missing_key_no_request(self):
  with patch.dict(os.environ,{'PROPLINE_API_KEY':''}):
   with self.assertRaises(DataProviderError):PropLineClient(lambda u,k:self.fail()).read('NFL')
 def test_fallback_only_verified_current_same_sport(self):
  row=normalize(self.board,'NFL',self.now)[0][0];row['provider']='ParlayAPI'
  def fail(s):raise DataProviderError('outage','SYNTHETIC')
  self.assertTrue(choose_feed(fail,lambda s:{'provider':'ParlayAPI','sport':s,'items':[row]},'NFL')['fallbackUsed'])
  self.assertFalse(choose_feed(fail,None,'NFL')['fallbackUsed'])
 def test_bad_fallback_cannot_replace_primary(self):
  value=choose_feed(lambda s:{'items':[]},lambda s:{'provider':'ParlayAPI','sport':'CFB','items':[{}]},'NFL');self.assertEqual(value['items'],[])

 def test_burst_does_not_pause_until_daily_reset(self):
  c=PropLineClient(lambda u,k:(429,{'X-Daily-Remaining':'900','X-Daily-Reset':str(int(self.now+3600)),'Retry-After':'1'},b''))
  with self.assertRaises(DataProviderError) as error:c.read('NFL')
  self.assertLessEqual(error.exception.retry_after,2)
 def test_cached_counts_do_not_advertise_expired_book_rows(self):
  t=[self.now];at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(self.now-250));self.board[0]['bookmakers'][0]['markets'][0]['last_update']=at;self.board[0]['bookmakers'][0]['markets'][0]['outcomes'][0]['last_seen_at']=at
  c=PropLineClient(lambda u,k:(200,{},json.dumps(self.board).encode()),lambda:t[0]);self.assertEqual(c.read('NFL')['bookCounts']['draftkings'],1);t[0]+=60;value=c.read('NFL');self.assertEqual(value['items'],[]);self.assertEqual(value['bookCounts']['draftkings'],0);self.assertEqual(value['status'],'unavailable')
 def test_current_injury_reports_preserve_source_and_never_invent_availability_weights(self):
  def t(url,key):
   if url.endswith('/injuries'):return 200,{},json.dumps({'players':[{'player_id':'espn:1','player_name':'SYNTHETIC PLAYER','status':'Out','status_code':'out','source':'conference_report','source_updated_at':self.at}]}).encode()
   if url.endswith('/ids'):return 200,{},b'[]'
   return 200,{},json.dumps(self.board).encode()
  value=PropLineClient(t).read('NFL');self.assertEqual(value['injuryCoverage'],'available');self.assertEqual(value['injuries'][0]['status_code'],'out');self.assertEqual(value['injuries'][0]['source_updated_at'],self.at);self.assertNotIn('availabilityProbability',value['injuries'][0])
 def test_secondary_quota_exhaustion_stops_additional_provider_reads(self):
  calls=[];clock=[self.now]
  def t(url,key):
   calls.append(url)
   if url.endswith('/ids'):return 429,{'X-Daily-Remaining':'0','X-Daily-Reset':str(int(self.now+3600))},b''
   return 200,{},json.dumps(self.board).encode()
  client=PropLineClient(t,lambda:clock[0]);client.read('NFL');self.assertEqual(len(calls),2);clock[0]+=121
  with self.assertRaises(DataProviderError):client.read('NFL')
  self.assertEqual(len(calls),2)
