"""Audit archival event clocks and primary pregame documents without guessing."""
import sys,re,json,hashlib,importlib.util,io
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modeling.fullgame_v23.io import OUT,fetch
from modeling.fullgame_v23.runtime import job
from modeling.evidence_v21.io import canonical_article,published_metadata
from modeling.iterative_learning import freeze_json
from modeling.overnight_v20.state import atomic
spec=importlib.util.spec_from_file_location('r23',ROOT/'scripts/fullgame-v23.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
URLS=['https://goheels.com/news/2024/9/20/football-homestand-concludes-saturday-with-james-madison','https://georgiadogs.com/news/2024/11/25/football-bulldogs-wrap-up-regular-season-against-rival-tech','https://gophersports.com/documents/download/2024/9/25/09.28.24_Michigan_Notes.pdf']
def run():
    p,_=s.inputs();docs=[];audit=[]
    for url in URLS:
        b,r=fetch(url);entry={'source':url,'sourceVersion':r.get('sourceVersion'),'retrievedAt':r['retrievedAt'],'httpStatus':r.get('httpStatus'),'completeAvailabilityOrLineupEstablished':False}
        if b and b.startswith(b'%PDF'):
            from pypdf import PdfReader
            pdf=PdfReader(io.BytesIO(b));entry.update(pages=len(pdf.pages),documentMetadata={str(k):str(v) for k,v in (pdf.metadata or {}).items()},publicationInterpretation='Creation metadata and URL date do not independently establish first public availability. Depth charts in pregame notes are projected, not confirmed availability.')
        elif b:
            entry['publishedMetadata']=published_metadata(b)
            try:
                a=canonical_article(b,url);entry.update(datePublished=a.get('datePublished'),dateModified=a.get('dateModified'),primaryPregameScheduleCandidate=True)
            except ValueError as e:entry['blocker']=str(e)
        docs.append(entry)
    for gid in s.SELECTION['CFB']:
        text=(OUT/'gamebooks'/(s.BOOKS[gid]+'.txt')).read_text();date=re.search(r'Date:\s*([A-Z][a-z]+ \d{1,2}, \d{4})',text);kick=re.search(r'Kickoff time:\s*(\d{1,2}:\d\d\s*[AP]M)',text);actual=None
        if date and kick:
            actual=datetime.strptime(date[1]+' '+re.sub(r'\s+',' ',kick[1]),'%b %d, %Y %I:%M %p').replace(tzinfo=ZoneInfo('America/New_York')).isoformat()
        original=p['CFB'][gid]['at'];audit.append({'gameId':gid,'archivedAt':original,'primaryGamebookDate':date[1] if date else None,'primaryActualKickoffLocal':actual,'source':s.source_context('CFB',gid)['sources'][-1],'originalArchiveModified':False,'strictCutoffUsable':False,'blocker':'Archived event timestamp conflicts with independently printed game date/time. A final book documents actual kickoff, not a publication-complete pregame snapshot. Recover original scheduled cutoff before Mode B.'})
    result={'primaryDocuments':docs,'CFBEventTimeAudit':audit,'strictNewGames':0,'unknownIsHealthy':False,'allCorrectedArchiveClocksRemainResearchOnly':True};atomic(OUT/'evidence/schedule-audit-r1.json',result);return {'documents':len(docs),'CFBEventTimeAuditGames':len(audit),'strictNewGames':0}
if __name__=='__main__':
    if '--register' in sys.argv:freeze_json(OUT/'specs/schedule-r1.json',{'numericCode':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'modeling/fullgame_v23/io.py']},'urls':URLS,'scope':'Primary pregame inventory, not forecast generation'})
    else:print(json.dumps(job('schedule-r1',run,cpu=120,wall=300),indent=2))
