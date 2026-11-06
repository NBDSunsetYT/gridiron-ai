"""Primary-source article/table parsing with exact identities and dates."""
from html.parser import HTMLParser
from collections import defaultdict
import re,html
from datetime import timedelta
from .io import canonical_article
from .tiers import timestamped_fact
from ..accuracy_v20.quality import aware
NFL_HEADINGS={'CARDINALS':'ARI','FALCONS':'ATL','RAVENS':'BAL','BILLS':'BUF','PANTHERS':'CAR','BEARS':'CHI','BENGALS':'CIN','BROWNS':'CLE','COWBOYS':'DAL','BRONCOS':'DEN','LIONS':'DET','PACKERS':'GB','TEXANS':'HOU','COLTS':'IND','JAGUARS':'JAX','CHIEFS':'KC','RAIDERS':'LV','CHARGERS':'LAC','RAMS':'LA','DOLPHINS':'MIA','VIKINGS':'MIN','PATRIOTS':'NE','SAINTS':'NO','GIANTS':'NYG','JETS':'NYJ','EAGLES':'PHI','STEELERS':'PIT','49ERS':'SF','SEAHAWKS':'SEA','BUCCANEERS':'TB','TITANS':'TEN','COMMANDERS':'WAS'}
def nfl_article_statuses(article,*,errors=None):
    """Parse explicit publisher injury sections, never absence as healthy."""
    team=None;rows=[]
    for line in article.get('articleBody','').splitlines():
        line=line.strip()
        if line in NFL_HEADINGS:team=NFL_HEADINGS[line];continue
        m=re.match(r'^(OUT|DOUBTFUL|QUESTIONABLE):\s*(.+)',line)
        if not m or team is None:continue
        # The official summary sometimes omits a position or a comma between
        # two parenthesized entries. Preserve an unknown position explicitly.
        entries=re.sub(r'\)\s+(?=[A-Z/]{1,4}\s+[A-Z])', '), ',m[2])
        for item in re.split(r',\s*(?![^()]*\))',entries):
            match=re.fullmatch(r'(?:([A-Z/]{1,4})\s+)?([^()]+?)(?:\s*\(([^()]*)\))?',item.strip())
            if not match:
                if errors is None:raise ValueError('Unresolved explicit injury item; do not guess a player identity')
                errors.append({'teamId':team,'status':m[1].lower(),'rawItem':item.strip(),'reason':'Unresolved publisher text; no player identity guessed'})
                continue
            rows.append({'teamId':team,'position':match[1],'playerName':match[2].strip(),'status':m[1].lower(),'injury':match[3] or 'unspecified'})
    return rows
class Tables(HTMLParser):
    def __init__(self):super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.table=[]
        elif tag=='tr' and self.table is not None:self.row=[]
        elif tag in ('td','th') and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:self.row.append(' '.join(' '.join(self.cell).split()));self.cell=None
        elif tag=='tr' and self.row is not None:self.table.append(self.row);self.row=None
        elif tag=='table' and self.table is not None:self.tables.append(self.table);self.table=None
def article_timestamp(body,receipt,cutoff):
    a=canonical_article(body,receipt['url']);proof=timestamped_fact(receipt['url'],receipt['sourceVersion'],a['datePublished'],receipt['retrievedAt'],cutoff,a.get('dateModified'));return a,proof
def injury_tables(body,receipt,game,team_order,names):
    cutoff=(aware(game['at'])-timedelta(minutes=30)).isoformat();article,proof=article_timestamp(body,receipt,cutoff);parser=Tables();parser.feed(body.decode(errors='replace'));tables=[t for t in parser.tables if t and any('Game Status' in h for h in t[0])];facts=[]
    if len(tables)!=len(team_order):raise ValueError('Exact team/table order needs independent verification')
    for team,table in zip(team_order,tables):
        for row in table[1:]:
            if len(row)!=len(table[0]):continue
            player=re.sub(r'^[A-Z]{1,4}\s+','',row[0]);norm=re.sub('[^a-z0-9]','',player.lower());ids=names.get((team,norm),set());pid=next(iter(ids)) if len(ids)==1 else None;status=row[-1] or 'no_game_status_designation'
            facts.append({**proof,'sport':'NFL','eventId':game['id'],'teamId':team,'playerId':pid,'playerName':player,'kind':'injury_report','status':status,'practice':dict(zip(table[0][2:-1],row[2:-1])),'injury':row[1],'identityStatus':'resolved' if pid else 'unresolved','availability':'unknown' if status.lower() not in ('out','inactive') else 'confirmed_out','confidence':'publisher_dated_pregame','articleHeadline':article['headline']})
    return facts
def depth_chart(body,receipt,game,team,names):
    cutoff=(aware(game['at'])-timedelta(minutes=30)).isoformat();article,proof=article_timestamp(body,receipt,cutoff);p=Tables();p.feed(body.decode(errors='replace'));facts=[]
    for table in p.tables:
        if not table or not table[0] or table[0][0]!='Position':continue
        for row in table[1:]:
            if len(row)<2:continue
            for rank,value in enumerate(row[1:],1):
                for name in value.replace('*','').split('/'):
                    if not name:continue
                    norm=re.sub('[^a-z0-9]','',name.lower());ids=names.get((team,norm),set());pid=next(iter(ids)) if len(ids)==1 else None
                    facts.append({**proof,'sport':'NFL','eventId':game['id'],'teamId':team,'playerId':pid,'playerName':name,'position':row[0],'depthRank':rank,'kind':'projected_depth_chart','availability':'unknown','confirmedStarter':False,'confidence':'publisher_dated_projected','identityStatus':'resolved' if pid else 'unresolved','articleHeadline':article['headline']})
    return facts
