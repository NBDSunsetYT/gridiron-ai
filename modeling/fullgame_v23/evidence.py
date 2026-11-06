"""Historical primary evidence parsers. A missing row never means healthy."""
import io,re
from collections import defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import pdfplumber

def nba_rows(body):
    """Carry published column geometry over headerless continuation pages.

    2024 NBA PDFs print column headings only on page one. Earlier research
    silently skipped later pages; retain their original team/match context.
    """
    records=[];state={'date':None,'matchup':None,'team':None};report_time=None;starts=None;width=None
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        for page in pdf.pages:
            text=page.extract_text() or '';m=re.search(r'Injury\s*Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2}\s*[AP]M)',text)
            if not m:raise ValueError('Each injury-report page must retain its dated publisher header')
            issued=datetime.strptime(m[1]+' '+re.sub(r'\s+',' ',m[2]),'%m/%d/%y %I:%M %p').replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat()
            if report_time and report_time!=issued:raise ValueError('Mixed injury report editions')
            report_time=issued;words=page.extract_words();labels=['GameDate','GameTime','Matchup','Team','PlayerName','CurrentStatus','Reason'];headers={w['text']:w for w in words if w['text'] in labels}
            if len(headers)==7:starts=[headers[k]['x0']-1 for k in labels];top=max(w['bottom'] for w in headers.values());width=page.width
            else:
                if starts is None or abs(page.width-width)>1:raise ValueError('Continuation column geometry cannot be verified')
                title=[w for w in words if w['top']<60 and w['text'] in ['Injury','Report:','AM','PM']]
                if not title:raise ValueError('Continuation page header geometry missing')
                top=max(w['bottom'] for w in title)
            lines=defaultdict(list)
            for w in words:
                if w['top']>top+1 and not re.fullmatch(r'Page\d+of\d+',w['text']):lines[round(w['top']/2)*2].append(w)
            for _,ws in sorted(lines.items()):
                cells=['']*7
                for w in sorted(ws,key=lambda w:w['x0']):
                    col=max((i for i,x in enumerate(starts) if w['x0']>=x),default=0);cells[col]+=(' ' if cells[col] else '')+w['text']
                date,clock,match,team,name,status,reason=cells
                if re.fullmatch(r'\d{2}/\d{2}/\d{4}',date):state['date']=datetime.strptime(date,'%m/%d/%Y').date().isoformat()
                if re.fullmatch(r'[A-Z]{2,4}@[A-Z]{2,4}',match):state['matchup']=match;state['team']=None
                if team:state['team']=team
                if ',' in name and status in ['Out','Doubtful','Questionable','Probable','Available'] and state['team'] and state['date']:
                    last,first=name.split(',',1);records.append({**state,'name':first+' '+last,'status':status,'reason':reason})
                elif 'NOTYETSUBMITTED' in re.sub(r'\W','',name+status+reason).upper():records.append({**state,'status':'not_yet_submitted'})
                elif reason and records and not (date or clock or match or team or name or status):
                    # A wrapped continuation can follow NOT YET SUBMITTED,
                    # whose row intentionally has no player/reason fields.
                    # Preserve the publisher fragment without inventing status.
                    records[-1]['reason']=(records[-1].get('reason','')+' '+reason).strip()
    return records,report_time
