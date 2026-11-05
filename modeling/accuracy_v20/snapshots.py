"""Local research snapshot/outbox; never the user's production database."""
import sqlite3,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from .quality import aware
def hash_value(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
class ResearchSnapshots:
    def __init__(self,path):
        from ..reconstruction_v19.runtime import local_only
        local_only();self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path,timeout=5);self.db.execute('pragma journal_mode=WAL');self.db.execute('pragma foreign_keys=ON');self.db.executescript('''
        create table if not exists snapshots(id text primary key,event_id text not null,model_version text not null,prediction_asof text not null,input_hash text not null,recorded_at text not null,phase text not null,body text not null);
        create index if not exists snapshots_event on snapshots(event_id,model_version);
        create table if not exists evidence(id text primary key,event_id text not null,actor_key text not null,kind text not null,semantic_hash text not null,published_at text not null,body text not null);
        create index if not exists evidence_current on evidence(event_id,actor_key,kind,published_at);
        create table if not exists invalidations(snapshot_id text not null references snapshots(id),evidence_id text not null references evidence(id),primary key(snapshot_id,evidence_id));
        create table if not exists refresh_jobs(id text primary key,event_id text not null,model_version text not null,input_hash text not null,state text not null default 'queued',reason text not null,unique(event_id,model_version,input_hash));
        ''')
    def freeze(self,body,recorded_at=None):
        recorded_at=recorded_at or datetime.now(timezone.utc).isoformat();cutoff=aware(body['predictionAsOf']);event=aware(body['eventStart'])
        if cutoff>=event:raise ValueError('Pregame cutoff must precede kickoff')
        if body['phase']=='prospective_pregame' and aware(recorded_at)>=event:raise ValueError('Cannot backdate a prospective pregame snapshot')
        if body['phase'] not in ('prospective_pregame','historical_replay'):raise ValueError('Explicit historical/prospective phase required')
        ident=hash_value(body)
        with self.db:self.db.execute('insert or ignore into snapshots values(?,?,?,?,?,?,?,?)',(ident,body['eventId'],body['modelVersion'],body['predictionAsOf'],body['inputHash'],recorded_at,body['phase'],json.dumps(body,sort_keys=True)))
        return ident
    def verified_update(self,fact,event_start):
        required=['eventId','source','sourceVersion','publishedAt','retrievedAt','kind','value']
        if any(fact.get(k) is None for k in required):raise ValueError('Versioned, timestamped fact required')
        if fact.get('verified') is not True or not str(fact['source']).startswith('https://'):raise ValueError('Verified authorized source required')
        if fact['kind'] not in ('injury','lineup','participation','weather'):raise ValueError('Unsupported material input type')
        if aware(fact['publishedAt'])>aware(fact['retrievedAt']):raise ValueError('Invalid source publication/retrieval order')
        if aware(fact['publishedAt'])>=aware(event_start):return {'accepted':False,'reason':'postkickoff_evidence_cannot_update_pregame_forecasts','queued':0}
        semantic=hash_value({k:fact.get(k) for k in ('eventId','playerId','kind','value')});ident=hash_value(fact);jobs=[];published=aware(fact['publishedAt']).isoformat();actor=fact.get('playerId') or '__team__'
        with self.db:
            previous=self.db.execute('select semantic_hash,published_at from evidence where event_id=? and actor_key=? and kind=? order by published_at desc,id desc limit 1',(fact['eventId'],actor,fact['kind'])).fetchone();self.db.execute('insert or ignore into evidence values(?,?,?,?,?,?,?)',(ident,fact['eventId'],actor,fact['kind'],semantic,published,json.dumps(fact,sort_keys=True)))
            tied=self.db.execute('select 1 from evidence where event_id=? and actor_key=? and kind=? and published_at=? and semantic_hash<>? limit 1',(fact['eventId'],actor,fact['kind'],published,semantic)).fetchone()
            if tied and previous and previous[1]==published:
                for sid,cutoff in self.db.execute('select id,prediction_asof from snapshots where event_id=?',(fact['eventId'],)):
                    if aware(published)>aware(cutoff):self.db.execute('insert or ignore into invalidations values(?,?)',(sid,ident))
                self.db.execute("update refresh_jobs set state='blocked_conflicting_evidence' where event_id=? and state='queued'",(fact['eventId'],))
                return {'accepted':False,'reason':'conflicting_statuses_at_same_publication_time','queued':0,'runsStarted':0}
            previous_conflicted=previous and self.db.execute('select count(distinct semantic_hash) from evidence where event_id=? and actor_key=? and kind=? and published_at=?',(fact['eventId'],actor,fact['kind'],previous[1])).fetchone()[0]>1
            if previous and ((previous[0]==semantic and not previous_conflicted) or previous[1]>published):return {'accepted':True,'unchanged':previous[0]==semantic,'olderThanCurrent':previous[1]>published,'queued':0}
            rows=self.db.execute('select id,model_version,prediction_asof,input_hash,body from snapshots where event_id=? order by prediction_asof desc,recorded_at desc,id desc',(fact['eventId'],)).fetchall();latest={}
            for sid,model,cutoff,old,raw in rows:
                body=json.loads(raw)
                if aware(body['eventStart'])!=aware(event_start):raise ValueError('Event identity/start mismatch')
                if fact.get('playerId') and fact['playerId'] not in body.get('playerIds',[]):continue
                if aware(fact['publishedAt'])<=aware(cutoff):continue
                self.db.execute('insert or ignore into invalidations values(?,?)',(sid,ident));latest.setdefault(model,(old,cutoff))
            for model,(old,cutoff) in latest.items():
                facts=self.db.execute('select actor_key,kind,semantic_hash,published_at from evidence where event_id=? order by published_at,id',(fact['eventId'],)).fetchall();current={}
                for who,kind,h,pub in facts:
                    if aware(pub)>aware(cutoff):current[(who,kind)]=h
                new=hash_value({'oldInputs':old,'newEvidence':sorted(current.values())});jid=hash_value([fact['eventId'],model,new]);self.db.execute("update refresh_jobs set state='superseded' where event_id=? and model_version=? and input_hash<>? and state in ('queued','blocked_conflicting_evidence')",(fact['eventId'],model,new));self.db.execute("insert into refresh_jobs(id,event_id,model_version,input_hash,reason) values(?,?,?,?,?) on conflict(id) do update set state=case when refresh_jobs.state in ('superseded','blocked_conflicting_evidence') then 'queued' else refresh_jobs.state end",(jid,fact['eventId'],model,new,fact['kind']));jobs.append(jid)
        return {'accepted':True,'queued':len(set(jobs)),'jobIds':sorted(set(jobs)),'runsStarted':0,'reason':'Queued once; execution requires evidence, validation and cumulative compute-budget checks.'}
    def get(self,ident):
        r=self.db.execute('select body from snapshots where id=?',(ident,)).fetchone()
        if not r:return None
        return {'snapshot':json.loads(r[0]),'stale':bool(self.db.execute('select 1 from invalidations where snapshot_id=?',(ident,)).fetchone())}
    def backup(self,destination):
        with sqlite3.connect(destination) as backup:self.db.backup(backup)
    def close(self):self.db.close()
