"""Apply explicit sourced scenario changes, never infer healthy from absence."""
def validate(changes,owners):
    for r in changes or []:
        if r.get('status')!='out' or r.get('playerId') not in owners or owners[r['playerId']]!=r.get('teamId') or r.get('period') not in (1,2,3,4) or not 0<=r.get('remaining',-1)<=900 or not r.get('sourceVersion') or not str(r.get('source','')).startswith('https://'):raise ValueError('Explicit owned, sourced regulation availability scenario required')
    return list(changes or [])
def due(r,period,remaining):return period>r['period'] or period==r['period'] and remaining<=r['remaining']
