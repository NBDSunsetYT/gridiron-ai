"""Explicit statistic support; absent fields never become observed zeros."""
import math
TD_STATS=('passingTouchdowns','receivingTouchdowns','rushingTouchdowns')
class UnsupportedStatistic(ValueError):pass

def supported_value(record,stat):
    if stat not in record.get('stats',{}):raise UnsupportedStatistic('Historical statistic is missing: '+stat)
    value=record['stats'][stat]
    if not isinstance(value,(float,int)) or not math.isfinite(value):raise UnsupportedStatistic('Historical statistic is not finite: '+stat)
    return float(value)

def safe_schedule_metadata(row):
    """Final schedule QB, coach, weather and closing prices are NOT pregame facts."""
    return {k:row[k] for k in ('game_id','gameday','gametime','home_team','away_team','espn','stadium_id','stadium') if k in row}

def freeze_invalid_head_notice(source_hashes):
    return {'reason':'Archived normalized football player records contain no touchdown fields; missing values were previously filled as zero. Those legacy TD projection/evaluation metrics are invalidated, never reinterpreted as actual zero touchdowns.','affectedSports':['NFL','CFB'],'affectedStatistics':list(TD_STATS),'affectedSourceHashes':source_hashes,'preserveOriginalArtifacts':True,'replacement':'Versioned official-box grades and separately ingested explicit PBP touchdown flags.','scope':'Legacy normalized research caches and derived projection heads only. No blanket invalidation of unrelated licensed/live models or user wagers.'}
