"""Timing distinctions backed by NCAA 2023/2024 rule announcements.

https://www.ncaa.org/news/media-center-football-timing-rules-approved-for-divisions-i-ii/
https://www.ncaa.org/news/media-center-technology-rules-approved-in-football/
"""
def first_down_clock(sport,season,period,seconds_remaining,after_two_minute_timeout=None):
    if sport not in ('NFL','CFB') or period not in (1,2,3,4) or not 0<=seconds_remaining<=900:raise ValueError('Supported regulation state required')
    if sport=='NFL':return {'automaticFirstDownStop':False,'certainty':'rule','otherStoppagesStillApply':True}
    if season<2023:return {'automaticFirstDownStop':True,'certainty':'rule','restart':'ready_for_play'}
    if period not in (2,4):return {'automaticFirstDownStop':False,'certainty':'rule'}
    if season==2023:return {'automaticFirstDownStop':seconds_remaining<120,'certainty':'rule','restart':'ready_for_play_when_stopped'}
    if seconds_remaining>120:return {'automaticFirstDownStop':False,'certainty':'rule'}
    if after_two_minute_timeout is None:return {'automaticFirstDownStop':None,'certainty':'missing_timeout_state','cannotAssumeClockAt120MeansTimeoutOccurred':True}
    return {'automaticFirstDownStop':bool(after_two_minute_timeout),'certainty':'verified_timeout_state','restart':'ready_for_play_when_stopped'}
