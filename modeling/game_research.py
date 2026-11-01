"""Exact full-game contract research from saved coherent game outcomes.

Prices, fee rules and current availability are deliberately not inferred here.
Winner, home-margin, total and team-score outcomes all share the game engine.
An exact simulation frequency is not a calibrated forecast or executable value.
"""
import array
import base64
from collections import Counter
from functools import lru_cache
import math
import sys
import zlib

from .simulator import DISTRIBUTION_ENCODING, GAME_PARAMETER_SAMPLE_ENCODING, MAX_PARAMETER_SAMPLE_BYTES, wilson

KINDS = ('home_win', 'away_win', 'spread', 'total', 'team_total')


def _definition(result, definition):
    if not isinstance(result,dict) or not isinstance(definition,dict) or definition.get('kind') not in KINDS:
        raise ValueError('An exact supported game-market definition and saved complete-game result are required')
    period=definition.get('period')
    if period!='full_game_including_overtime' and not (period=='full_game' and definition.get('overtimeIncluded') is True):
        raise ValueError('Verified full-game including-overtime settlement is required; regulation, half and quarter outcomes are unsupported')
    if definition.get('overtimeIncluded',True) is not True or definition.get('includesOvertime',True) is not True:
        raise ValueError('The contract excludes overtime but the saved game distribution includes it')
    if result.get('statisticCoverage',{}).get('period')!='full_game_including_overtime':
        raise ValueError('Saved score coverage does not establish full-game including-overtime outcomes')
    if definition.get('equality') not in ('yes','no','push'):
        raise ValueError('Exact tie/equality settlement must explicitly be yes, no or push')
    home,away=result.get('home'),result.get('away')
    if not isinstance(home,str) or not home or not isinstance(away,str) or not away or home==away:
        raise ValueError('Two exact saved team identities are required')
    kind=definition['kind']
    if kind=='team_total' and definition.get('team') not in ('home','away'):
        raise ValueError('A team total needs an explicit home or away team')
    if kind=='spread' and definition.get('team') not in (None,'home'):
        raise ValueError('Spread thresholds are expressed in home-minus-away coordinates; normalize away-team contracts explicitly')
    expected=home if kind=='home_win' else away if kind=='away_win' else result[definition['team']] if kind=='team_total' else None
    if definition.get('teamId') is not None and (expected is None or definition['teamId']!=expected):
        raise ValueError('The contract team identity does not match the saved game definition')
    if kind not in ('home_win','away_win'):
        threshold=definition.get('threshold')
        if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold):
            raise ValueError('A finite exact threshold is required')
        if definition.get('direction') not in ('over','under'):
            raise ValueError('An explicit over or under threshold direction is required')
    return kind


def exact_game_distribution(result, definition):
    """Never reconstruct totals/margins by assuming independent team scores."""
    kind=_definition(result,definition)
    n=result.get('simulations')
    if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=100000:
        raise ValueError('The saved result has no supported complete-game count')
    encoding=result.get('distributionEncoding')
    if encoding!=DISTRIBUTION_ENCODING and (encoding is not None or result.get('engineVersion')!='pbp-runtime-4.0.0'):
        raise ValueError('The saved game histogram does not declare exact integer frequencies')
    if kind in ('home_win','away_win','spread'):
        distribution=result.get('marginDistribution')
        coordinate='away_minus_home' if kind=='away_win' else 'home_minus_away'
    elif kind=='total':
        distribution=result.get('totalDistribution')
        coordinate='combined_score'
    else:
        distribution=result.get('scoreDistributions',{}).get(result[definition['team']])
        coordinate=definition['team']+'_score'
    if not isinstance(distribution,dict) or not isinstance(distribution.get('histogram'),list):
        raise ValueError('The exact saved game-market distribution is unavailable')
    frequencies=Counter()
    for point in distribution['histogram']:
        if not isinstance(point,dict):raise ValueError('Malformed exact game outcome')
        value,count=point.get('value'),point.get('count')
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or int(value)!=value:
            raise ValueError('Exact score and margin outcomes must be finite integers, not chart bins')
        if kind in ('total','team_total') and value<0:
            raise ValueError('A score distribution cannot contain negative points')
        if isinstance(count,bool) or not isinstance(count,int) or count<=0:
            raise ValueError('Every exact game frequency must be a positive integer')
        value=-int(value) if kind=='away_win' else int(value)
        if value in frequencies:raise ValueError('Duplicate game outcome values are ambiguous')
        frequencies[value]=count
    if sum(frequencies.values())!=n:
        raise ValueError('The exact game distribution does not reconcile every simulated game')
    return frequencies,n,coordinate


def _outcome(value,definition):
    kind=definition['kind']
    threshold=0 if kind in ('home_win','away_win') else definition['threshold']
    if value==threshold:return definition['equality']
    above=value>threshold
    return 'yes' if (above if kind in ('home_win','away_win') or definition['direction']=='over' else not above) else 'no'


@lru_cache(maxsize=4)
def _decode_game_values(encoded,expected):
    if not isinstance(encoded,str) or len(encoded)>2_666_668:
        raise ValueError('The score sample encoding exceeds its safe bound')
    compressed=base64.b64decode(encoded,validate=True)
    if len(compressed)>2_000_000 or base64.b64encode(compressed).decode('ascii')!=encoded:
        raise ValueError('The score sample payload is malformed or exceeds its bound')
    decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
    raw=decoder.decompress(compressed,expected+1)
    if len(raw)!=expected or decoder.unconsumed_tail or decoder.unused_data or not decoder.eof:
        raise ValueError('The bounded score sample dimensions do not reconcile')
    values=array.array('i')
    if values.itemsize!=4:raise ValueError('Signed int32 score samples are unsupported')
    values.frombytes(raw)
    if sys.byteorder!='little':values.byteswap()
    if any(value<0 or value>60000 for value in values):raise ValueError('Invalid saved score sample values')
    return values


def parameter_game_interval(result,definition,outcome='yes'):
    """Quantile sensitivity across independent whole-game parameter replicates.

Missing v6 score samples are unavailable. Marginal home/away intervals cannot be
combined to manufacture a total or margin interval.
"""
    try:
        _definition(result,definition)
        if outcome not in ('yes','no','push'):return None
        bootstrap=result.get('uncertainty',{}).get('parameterBootstrap',{})
        if 'gameHistograms' in bootstrap:
            from .storage_summary import game_parameter_histograms
            groups,reps,games=game_parameter_histograms(result)
            probabilities=[]
            for rows in groups:
                hits=0
                for home,away,count in rows:
                    kind=definition['kind']
                    value=home-away if kind in ('home_win','spread') else away-home if kind=='away_win' else home+away if kind=='total' else home if definition['team']=='home' else away
                    if _outcome(value,definition)==outcome:hits+=count
                probabilities.append(hits/games)
            probabilities.sort()
            return[probabilities[max(0,int(.025*reps))],probabilities[min(reps-1,math.ceil(.975*reps)-1)]]
        sample=bootstrap.get('gameSamples',{})
        if sample.get('status')!='available' or sample.get('encoding')!=GAME_PARAMETER_SAMPLE_ENCODING or sample.get('valueType')!='int32le':return None
        shape=sample.get('shape')
        if not isinstance(shape,list) or len(shape)!=3 or any(isinstance(v,bool) or not isinstance(v,int) or v<=0 for v in shape):return None
        reps,games,teams=shape
        if not 10<=reps<=40 or not 100<=games<=2000 or teams!=2:return None
        if sample.get('teams')!=[result['home'],result['away']] or sample.get('coverage')!='full_game_including_overtime':return None
        if bootstrap.get('replicates')!=reps or bootstrap.get('gamesPerReplicate')!=games or bootstrap.get('completeGames')!=reps*games:return None
        blocks=bootstrap.get('historicalGameBlocks')
        if isinstance(blocks,bool) or not isinstance(blocks,int) or blocks<8:return None
        expected=reps*games*2*4
        if expected>MAX_PARAMETER_SAMPLE_BYTES or sample.get('uncompressedBytes')!=expected:return None
        values=_decode_game_values(sample.get('dataBase64'),expected)
        if sample.get('compressedBytes')!=len(base64.b64decode(sample['dataBase64'],validate=True)):return None
        probabilities=[]
        for replicate in range(reps):
            hits=0
            for game in range(games):
                index=(replicate*games+game)*2
                home,away=values[index],values[index+1]
                kind=definition['kind']
                value=home-away if kind in ('home_win','spread') else away-home if kind=='away_win' else home+away if kind=='total' else home if definition['team']=='home' else away
                hits+=_outcome(value,definition)==outcome
            probabilities.append(hits/games)
        probabilities.sort()
        return[probabilities[max(0,int(.025*reps))],probabilities[min(reps-1,math.ceil(.975*reps)-1)]]
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,zlib.error):
        return None


def evaluate_exact_game_distribution(result,definition,outcome='yes'):
    frequencies,n,coordinate=exact_game_distribution(result,definition)
    if outcome not in ('yes','no'):raise ValueError('Choose the actual yes or no contract outcome')
    counts=Counter({'yes':0,'no':0,'push':0})
    for value,count in frequencies.items():counts[_outcome(value,definition)]+=count
    probability=counts[outcome]/n
    return{'kind':definition['kind'],'team':definition.get('team'),'teamId':definition.get('teamId'),
           'threshold':0 if definition['kind'] in ('home_win','away_win') else definition['threshold'],
           'coordinate':coordinate,'equality':definition['equality'],'outcome':outcome,'simulations':n,
           'rawSimulationProbability':probability,'yesProbability':counts['yes']/n,'noProbability':counts['no']/n,
           'pushProbability':counts['push']/n,'counts':dict(counts),
           'conditionalNonPushProbability':counts[outcome]/(n-counts['push']) if counts['push']!=n else None,
           'monteCarloSE':math.sqrt(probability*(1-probability)/n),'monteCarloInterval95':wilson(counts[outcome],n),
           'parameterInterval95':parameter_game_interval(result,definition,outcome),
           'calibratedProbability':None,'calibrationStatus':'No validated game-market calibration artifact is attached.',
           'historicalModelReliability':None,'distributionEncoding':DISTRIBUTION_ENCODING,
           'limitations':['Historical conditional game baseline; availability, weather and exceptional settlement coverage must be audited separately.',
                          'The Monte Carlo interval measures sampling error. Independent parameter sensitivity is not validated predictive coverage.',
                          'No executable price, fee, fair value or after-cost profit is inferred from a probability.']}
