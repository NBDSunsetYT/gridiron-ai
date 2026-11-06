"""Football statistical attribution differs by league.
NCAA manual, General Principles (team statistics): intentional kneels and spikes
are team credits, not individual quarterback rushing/pass attempts. This does
not claim a missing spike subtype has been fitted to the play-selection model.
"""
NCAA_MANUAL='https://fs.ncaa.org/Docs/stats/Stats_Manuals/Football.pdf'

def clock_stop_owner(sport,kind,quarterback,team):
    if sport not in ('NFL','CFB') or kind not in ('kneel','spike'):raise ValueError('Unsupported statistical-credit rule')
    return 'team-stat:'+team if sport=='CFB' else quarterback
