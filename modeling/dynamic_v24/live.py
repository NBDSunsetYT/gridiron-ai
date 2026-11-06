"""Immutable live feeds, corrections and a local bounded outbox.

This module performs no network polling and never starts work on a page read.
Unqualified or delayed feeds cannot publish current live probabilities.
"""
import json,sqlite3,time,math
from datetime import datetime,timezone
from ..overnight_v20.state import digest
from ..accuracy_v20.quality import aware

class FeedLog:
    def __init__(self,sport,event,maximum_latency=60):self.sport=sport;self.event=event;self.maximum_latency=maximum_latency;self.events={};self.versions=[];self.last_sequence=-1;self.frozen_reason=None;self.last_good_timestamp=None
    def ingest(self,row,now=None,replay=False):
        if row.get('sport')!=self.sport or row.get('eventId')!=self.event:raise ValueError('Live sport/event identity mismatch')
        if not str(row.get('source','')).startswith('https://') or not row.get('sourceVersion'):raise ValueError('Versioned authorized source required')
        source=aware(row.get('sourceTimestamp'));received=aware(row.get('receivedAt'));now=aware(now) if now else datetime.now(timezone.utc)
        if received<source or source>now:raise ValueError('Invalid source clock')
        latency=(received-source).total_seconds();sequence=row.get('sequence');revision=row.get('revision',0);uid=row.get('id')
        if not isinstance(sequence,int) or isinstance(sequence,bool) or not uid or not isinstance(revision,int) or revision<0:raise ValueError('Stable event ID, integer order and revision required')
        prior=self.events.get(uid)
        if prior:
            if revision==prior['revision']:
                if digest({k:v for k,v in row.items() if k!='receivedAt'})!=prior['sha256']:raise ValueError('Unversioned correction rejected')
                return {'status':'duplicate','recompute':False}
            if revision<prior['revision'] or sequence!=prior['sequence']:raise ValueError('Revision ordering mismatch')
        elif sequence<=self.last_sequence:raise ValueError('Out-of-order event requires explicit correction/rebuild')
        gap=not prior and self.last_sequence>=0 and sequence!=self.last_sequence+1
        self.events[uid]={'row':dict(row),'revision':revision,'sequence':sequence,'sha256':digest({k:v for k,v in row.items() if k!='receivedAt'})};self.last_sequence=max(self.last_sequence,sequence)
        ordered=sorted((v['row'] for v in self.events.values()),key=lambda r:r['sequence']);version=digest(ordered);self.versions.append({'version':version,'corrected':bool(prior),'supersedes':self.versions[-1]['version'] if self.versions else None,'sourceTimestamp':row['sourceTimestamp'],'receivedAt':row['receivedAt']})
        self.frozen_reason='event_sequence_gap' if gap else 'source_latency_exceeded' if latency>self.maximum_latency or not replay and (now-source).total_seconds()>self.maximum_latency else None
        # A subsequent event cannot silently repair a missing event gap.
        seq=sorted(v['sequence'] for v in self.events.values())
        if seq and any(b-a!=1 for a,b in zip(seq,seq[1:])):self.frozen_reason='event_sequence_gap'
        if not self.frozen_reason:self.last_good_timestamp=row['sourceTimestamp']
        return {'status':'frozen' if self.frozen_reason else 'verified_order_only','reason':self.frozen_reason,'snapshotVersion':version,'recompute':True,'latencySeconds':latency,'requiresRebuild':bool(prior),'productionForecastQualified':False}
    def snapshot(self):
        return {'sport':self.sport,'eventId':self.event,'events':[v['row'] for v in sorted(self.events.values(),key=lambda v:v['sequence'])],'version':self.versions[-1]['version'] if self.versions else None,'lastVerifiedTimestamp':self.last_good_timestamp,'status':'frozen' if self.frozen_reason else 'ordered_evidence_only','reason':self.frozen_reason,'productionForecastQualified':False}

class Outbox:
    def __init__(self,path,maximum_pending=32):
        self.db=sqlite3.connect(str(path),timeout=5);self.db.execute('PRAGMA journal_mode=WAL');self.maximum_pending=maximum_pending
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0, ready REAL NOT NULL, lease REAL, result TEXT, error TEXT, token TEXT)")
        if 'token' not in [r[1] for r in self.db.execute('PRAGMA table_info(jobs)')]:self.db.execute('ALTER TABLE jobs ADD COLUMN token TEXT')
        self.db.execute('CREATE TABLE IF NOT EXISTS provider_budget (provider TEXT NOT NULL, day INTEGER NOT NULL, requests INTEGER NOT NULL, last REAL NOT NULL, PRIMARY KEY(provider,day))');self.db.commit()
    def enqueue(self,snapshot,model,trials=10000,qualified=False,now=None):
        if not qualified:raise ValueError('Live job withheld: evidence, mechanics and calibration gates have not passed')
        if not 10000<=trials<=100000 or snapshot.get('status')!='verified_current':raise ValueError('Verified current snapshot and bounded trials required')
        payload={'snapshot':snapshot['version'],'eventId':snapshot['eventId'],'model':model,'trials':trials};key=digest(payload);now=time.time() if now is None else now
        with self.db:
            if self.db.execute('SELECT id FROM jobs WHERE id=?',(key,)).fetchone():return key
            if self.db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running','retry')").fetchone()[0]>=self.maximum_pending:raise ValueError('Bounded live queue full')
            self.db.execute("UPDATE jobs SET status='obsolete',token=NULL WHERE json_extract(payload,'$.eventId')=? AND status IN ('queued','retry','running')",(snapshot['eventId'],));self.db.execute("INSERT INTO jobs(id,payload,status,ready) VALUES(?,?,'queued',?)",(key,json.dumps(payload),now))
        return key
    def claim(self,now=None,lease_seconds=120):
        now=time.time() if now is None else now
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute("SELECT 1 FROM jobs WHERE status='running' AND lease>?",(now,)).fetchone():return None
            self.db.execute("UPDATE jobs SET status='retry',ready=?,error='expired lease' WHERE status='running' AND lease<=?",(now+2,now));r=self.db.execute("SELECT id,payload,attempt FROM jobs WHERE status IN ('queued','retry') AND ready<=? AND attempt<3 ORDER BY ready,id LIMIT 1",(now,)).fetchone()
            if not r:return None
            token=digest({'id':r[0],'attempt':r[2]+1,'claimedAt':now});self.db.execute("UPDATE jobs SET status='running',attempt=attempt+1,lease=?,token=? WHERE id=?",(now+lease_seconds,token,r[0]));return {'id':r[0],'payload':json.loads(r[1]),'attempt':r[2]+1,'token':token}
    def finish(self,key,token,result=None,error=None,now=None):
        now=time.time() if now is None else now
        with self.db:
            row=self.db.execute("SELECT attempt,status,token,lease FROM jobs WHERE id=?",(key,)).fetchone()
            if not row or row[1]!='running' or row[2]!=token or now>row[3]:raise ValueError('Job lease is not current; stale worker fenced')
            status='complete' if error is None else 'failed' if row[0]>=3 else 'retry';self.db.execute('UPDATE jobs SET status=?,result=?,error=?,ready=?,lease=NULL WHERE id=?',(status,json.dumps(result) if error is None else None,str(error)[:200] if error else None,now+min(120,2**row[0]),key))
    def cached(self,key):
        r=self.db.execute("SELECT result FROM jobs WHERE id=? AND status='complete'",(key,)).fetchone();return json.loads(r[0]) if r else None
    def provider_request(self,provider,now=None,minimum_interval=30,daily_limit=1000):
        now=time.time() if now is None else now;day=int(now//86400)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE');row=self.db.execute('SELECT requests,last FROM provider_budget WHERE provider=? AND day=?',(provider,day)).fetchone()
            if row and (row[0]>=daily_limit or now-row[1]<minimum_interval):return False
            self.db.execute('INSERT INTO provider_budget(provider,day,requests,last) VALUES(?,?,1,?) ON CONFLICT(provider,day) DO UPDATE SET requests=requests+1,last=excluded.last',(provider,day,now));return True

def player_projection(actual,samples,threshold=None,threshold_evidence=None):
    import numpy as np
    values=np.asarray(samples,float)
    if len(values)<1 or not np.isfinite(values).all():raise ValueError('Verified finite jointly simulated samples required')
    result={'actual':actual,'remainingMean':float(np.mean(values-actual)),'finalMean':float(np.mean(values)),'predictionInterval90':np.quantile(values,[.05,.95]).tolist(),'simulations':len(values),'probability':None,'calibratedProbability':None}
    if threshold is not None:
        if not threshold_evidence or threshold_evidence.get('verified') is not True or not threshold_evidence.get('settlementRules') or not threshold_evidence.get('sourceVersion'):raise ValueError('Exact verified threshold and settlement rules required')
        if threshold_evidence.get('operator') not in ('>','>='):raise ValueError('Explicit settlement comparison required')
        success=int(np.sum(values>threshold if threshold_evidence['operator']=='>' else values>=threshold));p=success/len(values)
        from ..simulator import wilson
        result.update(probability=p,successfulOutcomes=success,monteCarloSE=math.sqrt(p*(1-p)/len(values)),monteCarloInterval95=wilson(success,len(values)),threshold=threshold)
    return result
