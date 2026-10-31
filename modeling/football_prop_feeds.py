"""Render-only sportsbook props. No exchange prices, ledger writes or model guesses."""
import copy
import hashlib
import json
import math
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from .sports_data_common import DataProviderError, require_render_runtime, utc_now

DOCS = 'https://prop-line.com/docs'
SPORTS = {'NFL':'football_nfl', 'CFB':'football_ncaaf'}
MARKETS = {'player_pass_yds':'passingYards','player_pass_tds':'passingTouchdowns',
 'player_pass_attempts':'passingAttempts','player_pass_completions':'completions',
 'player_pass_interceptions':'interceptions','player_rush_yds':'rushingYards',
 'player_rush_attempts':'carries','player_rush_tds':'rushingTouchdowns',
 'player_reception_yds':'receivingYards','player_receptions':'receptions',
 'player_reception_tds':'receivingTouchdowns','player_anytime_td':'touchdowns'}
BOOKS = {'draftkings':'DraftKings Sportsbook','fanduel':'FanDuel','betmgm':'BetMGM','hardrock':'Hard Rock'}

def stamp(value):
    if not isinstance(value,str): return None
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d.timestamp() if d.tzinfo else None
    except ValueError: return None

def finite(value):
    return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)

def normalize(events,sport,now=None):
    now=time.time() if now is None else now
    if sport not in SPORTS or not isinstance(events,list) or len(events)>500:
        raise DataProviderError('unsupported_response','The provider dataset is not a bounded football board.')
    rows=[];rejected=0
    for event in events:
        if not isinstance(event,dict) or event.get('sport_key')!=SPORTS[sport]: continue
        kickoff=stamp(event.get('commence_time'))
        if not kickoff or kickoff<=now or not event.get('id') or not all(isinstance(event.get(k),str) and event[k] for k in ['home_team','away_team']):continue
        books=event.get('bookmakers',[])
        if not isinstance(books,list):raise DataProviderError('unsupported_response','Invalid bookmaker collection.')
        for book in books[:100]:
            if not isinstance(book,dict) or book.get('key') not in BOOKS:continue
            markets=book.get('markets',[])
            if not isinstance(markets,list):raise DataProviderError('unsupported_response','Invalid market collection.')
            for market in markets[:500]:
                if not isinstance(market,dict) or market.get('key') not in MARKETS:continue
                updated=market.get('last_update');ts=stamp(updated)
                outcomes=market.get('outcomes',[])
                if not isinstance(outcomes,list):raise DataProviderError('unsupported_response','Invalid outcome collection.')
                for outcome in outcomes[:2000]:
                    if not isinstance(outcome,dict):rejected+=1;continue
                    seen=stamp(outcome.get('last_seen_at'));price=outcome.get('price');line=outcome.get('point');name=outcome.get('description');side=outcome.get('name')
                    # Provider observation time is not a sportsbook publication or executable quote guarantee.
                    if (not ts or ts>now+60 or now-ts>300 or seen!=ts or not finite(price) or int(price)!=price or abs(price)<100 or abs(price)>100000 or not isinstance(name,str) or not name.strip() or not isinstance(side,str) or not side.strip() or (line is not None and not finite(line))):rejected+=1;continue
                    # Preserve null thresholds for touchdown selection markets; don't invent0.5.
                    if line is None and market['key']!='player_anytime_td':rejected+=1;continue
                    identity=json.dumps([sport,str(event['id']),book['key'],market['key'],outcome.get('player_id'),name,side,line,price,updated],separators=(',',':'))
                    rows.append({'id':hashlib.sha256(identity.encode()).hexdigest(),'provider':'PropLine','sport':sport,
                     'dataFamily':'sportsbook_reference','eventId':str(event['id']),'espnEventId':str(event['espn_event_id']) if event.get('espn_event_id') else None,
                     'home':event['home_team'],'away':event['away_team'],'kickoff':event['commence_time'],
                     'player':{'id':outcome.get('player_id') if isinstance(outcome.get('player_id'),str) else None,'name':name},
                     'book':{'key':book['key'],'name':BOOKS[book['key']]},'market':market['key'],'statistic':MARKETS[market['key']],
                     'side':side,'threshold':str(line) if line is not None else None,'americanOdds':int(price),
                     'period':market.get('period'),'sourceUpdatedAt':updated,'lastSeenAt':outcome['last_seen_at'],
                     'quotedAt':None,'observedAt':datetime.fromtimestamp(now,timezone.utc).isoformat(),
                     'timestampMeaning':'PropLine observation; original sportsbook publication time is unverified.',
                     'settlementRules':None,'fees':None,'executionVerified':False,'draftKingsPredictionsEquivalent':False,
                     'sourceUrl':DOCS,'modelProbability':None,'calibratedProbability':None,'expectedValue':None})
                    if len(rows)>10000:raise DataProviderError('response_bound','The football board exceeds the safe row limit.')
    rows.sort(key=lambda r:(r['book']['key']!='draftkings',r['kickoff'],r['id']))
    return rows,rejected

class PropLineClient:
    def __init__(self,transport=None,clock=time.time):
        self.transport=transport or self._http;self.clock=clock;self.lock=threading.Lock();self.cache={};self.until=0;self.used=0;self.day=None
    def _http(self,url,key):
        req=urllib.request.Request(url,headers={'X-API-Key':key,'Accept':'application/json'})
        # No redirects may forward a provider credential to another host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as response:
                body=response.read(32000001)
                if len(body)>32000000:raise DataProviderError('response_bound','Provider response too large.')
                return response.status,dict(response.headers),body
        except urllib.error.HTTPError as error:return error.code,dict(error.headers),b''
        except (urllib.error.URLError,TimeoutError,OSError):raise DataProviderError('provider_network_error','PropLine could not be reached.',retryable=True) from None
    def read(self,sport):
        require_render_runtime()
        if sport not in SPORTS:raise DataProviderError('unsupported_sport','Choose NFL or CFB.')
        key=os.environ.get('PROPLINE_API_KEY','')
        if not key:raise DataProviderError('credentials_missing','Configure PROPLINE_API_KEY on Render.',requires_operator=True)
        with self.lock:
            now=self.clock();old=self.cache.get(sport)
            if old and now-old[0]<300:
                result=copy.deepcopy(old[1]);result['cached']=True;return result
            if now<self.until:raise DataProviderError('provider_quota_paused','PropLine requests are paused until its retry/reset time.',retryable=True,retry_after=math.ceil(self.until-now))
            day=datetime.fromtimestamp(now,timezone.utc).date()
            if day!=self.day:self.day=day;self.used=0
            if self.used>=1000:raise DataProviderError('local_daily_limit','The conservative1,000request daily budget is exhausted.',retryable=True)
            self.used+=1
            url='https://api.prop-line.com/v1/sports/'+SPORTS[sport]+'/odds?'+urllib.parse.urlencode({'markets':','.join(MARKETS),'bookmakers':','.join(BOOKS),'includeBookIds':'true'})
            status,headers,body=self.transport(url,key);headers={k.lower():v for k,v in headers.items()}
            quota={k:headers[k] for k in ['x-daily-limit','x-daily-used','x-daily-remaining','x-daily-reset','retry-after'] if k in headers}
            def number(name,default):
                try:return float(headers.get(name,default))
                except (ValueError,TypeError):return default
            if number('x-daily-remaining',1)<=0:
                self.until=max(now+number('retry-after',60),number('x-daily-reset',now+60))
            elif status==429:
                self.until=now+max(1,number('retry-after',60))
            if status!=200:raise DataProviderError('rate_limited' if status==429 else 'credentials_or_access_denied' if status in (401,403) else 'provider_unavailable','PropLine did not supply a successful live football board.',http_status=status,retryable=status==429 or status>=500,requires_operator=status in (401,403),retry_after=max(0,math.ceil(self.until-now)) if self.until>now else None)
            if key.encode() in body:raise DataProviderError('unsafe_response','Provider response withheld.')
            try:raw=json.loads(body)
            except (ValueError,UnicodeError):raise DataProviderError('unsupported_response','PropLine did not return valid JSON.') from None
            rows,rejected=normalize(raw,sport,now)
            value={'provider':'PropLine','sport':sport,'dataFamily':'sportsbook_reference','status':'available' if rows else 'unavailable',
             'providerHttpStatus':200,'checkedAt':utc_now(),'items':rows,'rejectedRows':rejected,'quota':quota,'cached':False,
             'diagnostic':{'code':'verified_provider_rows' if rows else 'no_verified_current_props','message':'Current provider rows were validated.' if rows else 'No current supported sportsbook props passed identity and freshness checks.'},
             'fallbackVerified':False}
            self.cache[sport]=(now,value);return copy.deepcopy(value)

def choose_feed(primary,fallback,sport):
    checks=[]
    for provider,reader in [('PropLine',primary),('ParlayAPI',fallback)]:
        if reader is None:
            checks.append({'provider':provider,'code':'documentation_and_access_unverified'});continue
        try:
            value=reader(sport)
            # A fallback must already normalize valid rows; never accept a differently branded dataset.
            rows=value.get('items',[])
            if rows and value.get('sport')==sport and value.get('provider')==provider and all(r.get('provider')==provider and r.get('sport')==sport and r.get('dataFamily')=='sportsbook_reference' and r.get('draftKingsPredictionsEquivalent') is False and stamp(r.get('sourceUpdatedAt')) and -60<=time.time()-stamp(r['sourceUpdatedAt'])<=300 for r in rows):return{**value,'sourceChecks':checks,'fallbackUsed':provider!='PropLine'}
            checks.append({'provider':provider,'code':'no_verified_current_props'})
        except DataProviderError as error:checks.append({'provider':provider,**error.diagnostic()})
    return {'provider':None,'sport':sport,'dataFamily':'sportsbook_reference','status':'unavailable','items':[],
      'checkedAt':utc_now(),'sourceChecks':checks,'fallbackUsed':False,
      'diagnostic':{'code':'no_verified_provider','message':'No authorized provider supplied verified current football props. No sportsbook or exchange prices were invented.'}}
