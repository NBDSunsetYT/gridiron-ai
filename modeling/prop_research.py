"""Exact cached-distribution research. Never interpolates chart buckets.

These helpers consume trusted, persisted complete-game engine outputs. A raw
simulation frequency is not a calibrated probability or a forecast guarantee.
"""
import math
import array
import base64
import sys
import zlib
from collections import Counter
from functools import lru_cache

from .simulator import STATS, DISTRIBUTION_ENCODING, PARAMETER_SAMPLE_ENCODING, MAX_PARAMETER_SAMPLE_BYTES, combination_summary, wilson


@lru_cache(maxsize=4)
def _decode_sample_values(encoded,expected,columns):
    if not isinstance(encoded,str) or len(encoded)>2_666_668:
        raise ValueError('Parameter sample storage is outside its safe bound')
    compressed=base64.b64decode(encoded,validate=True)
    if len(compressed)>2_000_000:raise ValueError('Parameter sample compressed bytes exceed the bound')
    decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
    raw=decoder.decompress(compressed,expected+1)
    if len(raw)!=expected or decoder.unconsumed_tail or decoder.unused_data or not decoder.eof:
        raise ValueError('Parameter samples do not reconcile their exact bounded dimensions')
    values=array.array('i')
    if values.itemsize!=4:raise ValueError('Int32 parameter sample support is unavailable')
    values.frombytes(raw)
    if sys.byteorder!='little':values.byteswap()
    yards={'passingYards','rushingYards','receivingYards'}
    if any(abs(value)>60_000 or value<0 and columns[index%len(columns)] not in yards for index,value in enumerate(values)):
        raise ValueError('Parameter samples contain unsupported player outcomes')
    if all(stat in columns for stat in ('touchdowns','receivingTouchdowns','rushingTouchdowns')):
        td,rec,rush=(columns.index(stat) for stat in ('touchdowns','receivingTouchdowns','rushingTouchdowns'))
        if any(values[offset+td]!=values[offset+rec]+values[offset+rush] for offset in range(0,len(values),len(columns))):
            raise ValueError('Parameter samples do not preserve scorer touchdowns')
    return values


def parameter_player_interval(result,definition,outcome='yes'):
    """A new threshold's sensitivity across the fixed whole-game replicates."""
    try:
        bootstrap=result.get('uncertainty',{}).get('parameterBootstrap',{})
        samples=bootstrap.get('playerSamples',{})
        if samples.get('status')!='available' or samples.get('encoding')!=PARAMETER_SAMPLE_ENCODING or samples.get('valueType')!='int32le':return None
        shape=samples.get('shape')
        if not isinstance(shape,list) or len(shape)!=4 or any(isinstance(v,bool) or not isinstance(v,int) or v<=0 for v in shape):return None
        reps,games,players,stats=shape
        if not 10<=reps<=40 or not 100<=games<=2000 or players>256 or stats>len(STATS):return None
        if bootstrap.get('replicates')!=reps or bootstrap.get('gamesPerReplicate')!=games or bootstrap.get('completeGames')!=reps*games or bootstrap.get('historicalGameBlocks',0)<8:return None
        ids,columns=samples.get('players'),samples.get('stats')
        if not isinstance(ids,list) or len(ids)!=players or any(not isinstance(v,str) or not v or len(v)>120 for v in ids) or len(set(ids))!=players:return None
        if not isinstance(columns,list) or len(columns)!=stats or any(v not in STATS for v in columns) or len(set(columns))!=stats:return None
        if definition.get('playerId') not in ids or definition.get('stat') not in columns or outcome not in ('yes','no'):return None
        if definition.get('stat')=='touchdowns' and (definition.get('touchdownScope')!='offensive_rushing_receiving_only' or
                result.get('statisticCoverage',{}).get('touchdowns')!='offensive_rushing_receiving_only'):return None
        expected=reps*games*players*stats*4
        if expected>MAX_PARAMETER_SAMPLE_BYTES or samples.get('uncompressedBytes')!=expected:return None
        values=_decode_sample_values(samples.get('dataBase64'),expected,tuple(columns))
        if samples.get('compressedBytes')!=len(base64.b64decode(samples['dataBase64'],validate=True)):return None
        player,column=ids.index(definition['playerId']),columns.index(definition['stat'])
        probabilities=[]
        for replicate in range(reps):
            hits=0
            for game in range(games):
                value=values[(((replicate*games+game)*players+player)*stats+column)]
                if value==definition['threshold']:
                    key=definition['equality']
                else:
                    key='yes' if (value>definition['threshold'] if definition['direction']=='over' else value<definition['threshold']) else 'no'
                hits+=key==outcome
            probabilities.append(hits/games)
        probabilities.sort()
        return[probabilities[max(0,int(.025*reps))],probabilities[min(reps-1,math.ceil(.975*reps)-1)]]
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,zlib.error):
        return None


def exact_player_distribution(result, player_id, stat, touchdown_scope=None):
    if not isinstance(result,dict) or not isinstance(player_id,str) or not player_id:
        raise ValueError('A saved complete-game result and exact player ID are required')
    n = result.get('simulations')
    if isinstance(n,bool) or not isinstance(n,int) or not 1 <= n <= 100000:
        raise ValueError('The saved result has no supported complete-game count')
    encoding = result.get('distributionEncoding')
    if encoding != DISTRIBUTION_ENCODING:
        # The v4 engine used the same exact Counter representation before an
        # explicit marker existed. No other histogram format is inferred exact.
        if encoding is not None or result.get('engineVersion') != 'pbp-runtime-4.0.0':
            raise ValueError('The distribution does not declare exact integer frequencies')
    if stat not in STATS:
        raise ValueError('This player statistic is not supported by the game engine')
    withheld=result.get('publicPlayerForecastsWithheld',{})
    if not isinstance(withheld,dict):raise ValueError('The saved player-availability audit is malformed')
    if player_id in withheld:
        raise ValueError('Current availability evidence withholds this player projection')
    if stat == 'touchdowns':
        if touchdown_scope != 'offensive_rushing_receiving_only':
            raise ValueError('Touchdown settlement must explicitly cover rushing and receiving only; return/defensive player touchdowns are not modeled')
        if result.get('statisticCoverage',{}).get('touchdowns') != touchdown_scope:
            raise ValueError('The saved result does not provide verified touchdown-statistic coverage')
    players=result.get('players',{})
    if not isinstance(players,dict) or not isinstance(players.get(player_id,{}),dict):
        raise ValueError('No exact saved player-statistic distribution exists')
    distribution = players.get(player_id,{}).get(stat)
    if not isinstance(distribution,dict) or not isinstance(distribution.get('histogram'),list):
        raise ValueError('No exact saved distribution exists for this player/statistic')
    frequencies = Counter()
    for point in distribution['histogram']:
        if not isinstance(point,dict):
            raise ValueError('An exact histogram point is malformed')
        value,count = point.get('value'),point.get('count')
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or int(value)!=value:
            raise ValueError('Exact player outcomes must be finite integers, not chart-bin boundaries')
        if isinstance(count,bool) or not isinstance(count,int) or count<=0:
            raise ValueError('Exact histogram frequencies must be positive integers')
        if value in frequencies:
            raise ValueError('Duplicate outcome values make the saved distribution ambiguous')
        frequencies[int(value)] = count
    if sum(frequencies.values()) != n:
        raise ValueError('The exact distribution does not reconcile every simulated game')
    return frequencies,n


def evaluate_exact_player_distribution(result, definition, outcome='yes'):
    """Evaluate an exact threshold with explicit equality and YES/NO rules."""
    if not isinstance(definition,dict) or definition.get('kind')!='player':
        raise ValueError('A normalized player contract definition is required')
    threshold = definition.get('threshold')
    direction,equality = definition.get('direction'),definition.get('equality')
    if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold):
        raise ValueError('The exact contract threshold must be finite')
    if direction not in ('over','under') or equality not in ('push','yes','no'):
        raise ValueError('Explicit over|under direction and push|yes|no equality settlement are required')
    if outcome not in ('yes','no'):
        raise ValueError('Choose the actual yes|no contract outcome')
    histogram,n = exact_player_distribution(result,definition.get('playerId'),definition.get('stat'),definition.get('touchdownScope'))
    counts = Counter({'yes':0,'no':0,'push':0})
    for value,count in histogram.items():
        if value==threshold:
            selected = equality
        else:
            selected = 'yes' if (value>threshold if direction=='over' else value<threshold) else 'no'
        counts[selected] += count
    probability = counts[outcome]/n
    parameter = None
    # A bootstrap interval belongs only to the identical saved contract, never
    # to an arbitrary new threshold inferred from a marginal chart.
    for stored in result.get('contracts',[]):
        rule = stored.get('settlement',{})
        if stored.get('id')==definition.get('id') and all(rule.get(key)==definition.get(key) for key in ('kind','playerId','stat','threshold','direction','equality')):
            entry = result.get('uncertainty',{}).get('parameterBootstrap',{}).get('contracts',{}).get(stored['id'],{})
            parameter = entry.get('parameterInterval95' if outcome=='yes' else 'noParameterInterval95')
            break
    if parameter is None:parameter=parameter_player_interval(result,definition,outcome)
    return {'playerId':definition['playerId'],'stat':definition['stat'],'threshold':threshold,
            'direction':direction,'equality':equality,'outcome':outcome,'simulations':n,
            'rawSimulationProbability':probability,'yesProbability':counts['yes']/n,
            'noProbability':counts['no']/n,'pushProbability':counts['push']/n,
            'conditionalNonPushProbability':counts[outcome]/(n-counts['push']) if n!=counts['push'] else None,
            'counts':dict(counts),'monteCarloSE':math.sqrt(probability*(1-probability)/n),
            'monteCarloInterval95':wilson(counts[outcome],n),'parameterInterval95':parameter,
            'calibratedProbability':None,'calibrationStatus':'No validated player-prop calibration artifact is attached.',
            'historicalModelReliability':None,'distributionEncoding':DISTRIBUTION_ENCODING,
            'encodingVerification':'explicit' if result.get('distributionEncoding') else 'trusted_legacy_v4_exact_histogram_with_reconciled_counts',
            'limitations':['Exact threshold frequencies are conditional on the saved complete-game model; they are not evidence of calibration.',
                           'Monte Carlo sampling error excludes structural, future availability and all unestimated model uncertainty.']}


def evaluate_saved_combination(result, selected_outcomes):
    """Revalue a selected subset from an existing shared-game joint table."""
    if not isinstance(result,dict) or not isinstance(result.get('contracts'),list):
        raise ValueError('A saved joint simulation is required')
    n = result.get('simulations')
    if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=100000:
        raise ValueError('A verified complete-game count is required')
    contracts = []
    for contract in result['contracts']:
        if not isinstance(contract,dict) or not isinstance(contract.get('id'),str) or not contract.get('id'):
            raise ValueError('The saved contract ordering is malformed')
        contracts.append({'id':contract['id']})
    if len({c['id'] for c in contracts})!=len(contracts) or len(contracts)>32:
        raise ValueError('The saved contract ordering contains duplicate IDs or too many entries')
    joint = Counter()
    points = result.get('jointOutcomes')
    if not isinstance(points,list) or not points:
        raise ValueError('Marginal player distributions cannot establish joint probability; rerun selected contracts together')
    for point in points:
        if not isinstance(point,dict):raise ValueError('The saved joint outcome table is malformed')
        outcomes,count = point.get('outcomes'),point.get('count')
        if not isinstance(outcomes,list) or len(outcomes)!=len(contracts) or any(value not in ('yes','no','push') for value in outcomes):
            raise ValueError('The saved joint outcome ordering does not match its contracts')
        if isinstance(count,bool) or not isinstance(count,int) or count<=0:
            raise ValueError('Joint frequencies must be positive integer game counts')
        encoded = '|'.join(outcomes)
        if encoded in joint:raise ValueError('Duplicate joint outcome rows are ambiguous')
        joint[encoded] = count
    if sum(joint.values())!=n:
        raise ValueError('Joint outcomes do not reconcile every complete simulated game')
    answer = combination_summary(contracts,joint,selected_outcomes,n)
    if answer is None:raise ValueError('Select 2..12 actual contract outcomes')
    stored = result.get('combination',{})
    if stored.get('selectedOutcomes')==selected_outcomes:
        answer['parameterInterval95'] = stored.get('parameterInterval95')
    return answer
