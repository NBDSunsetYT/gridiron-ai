"""Same-clock NBA partial ordering from explicit substitution participants.

Corrected source IDs can follow the replacement they caused. An outgoing
player's action precedes that replacement; an incoming player's follows it.
No scores, box totals, or estimated minutes are used to choose the ordering.
"""
from collections import defaultdict
import heapq
def seconds(r):
    m,s=r['clock_display_value'].split(':');return float(m)*60+float(s)
def ids(r):return {str(int(r[k])) for k in ['athlete_id_1','athlete_id_2','athlete_id_3'] if r.get(k) is not None}
def canonical_order(events):
    groups=defaultdict(list)
    for r in events:groups[(int(r['period_number']),seconds(r))].append(r)
    out=[]
    for key,rs in sorted(groups.items(),key=lambda kv:(kv[0][0],-kv[0][1])):
        rs=sorted(rs,key=lambda r:int(r['sequence_number']));edges=defaultdict(set);indegree=[0]*len(rs);actions=[i for i,r in enumerate(rs) if 'substitution' not in str(r.get('type_text','')).lower()]
        def edge(a,b):
            if b not in edges[a]:edges[a].add(b);indegree[b]+=1
        for a,b in zip(actions,actions[1:]):edge(a,b)
        for i,r in enumerate(rs):
            if 'substitution' not in str(r.get('type_text','')).lower():continue
            if r.get('athlete_id_1') is None or r.get('athlete_id_2') is None:raise ValueError('Unmapped substitution ordering')
            incoming=str(int(r['athlete_id_1']));outgoing=str(int(r['athlete_id_2']))
            for j in actions:
                if 'technical' in str(rs[j].get('type_text','')).lower():continue
                participants=ids(rs[j])
                if outgoing in participants:edge(j,i)
                if incoming in participants:edge(i,j)
        heap=[i for i,n in enumerate(indegree) if n==0];heapq.heapify(heap);ordered=[]
        while heap:
            i=heapq.heappop(heap);ordered.append(i)
            for j in edges[i]:
                indegree[j]-=1
                if indegree[j]==0:heapq.heappush(heap,j)
        if len(ordered)!=len(rs):raise ValueError('Conflicting same-clock substitution/action evidence')
        out.extend(rs[i] for i in ordered)
    return out
