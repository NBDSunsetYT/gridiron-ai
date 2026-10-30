"""Normalize a local authorized nflverse CSV/CSV.GZ; never downloads automatically."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .fit import REQUIRED

SOURCE = 'https://github.com/nflverse/nflverse-data/releases/tag/pbp'


def number(row, key, fallback=0):
    value = row.get(key, '')
    return int(float(value)) if value not in ('', None, 'NA', 'NaN') else fallback


def read_pbp(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', newline='') as handle:
        return list(csv.DictReader(handle))


def normalize(rows, max_week=12):
    output, excluded, first_drive = [], Counter(), set()
    for index, r in enumerate(rows):
        if r.get('season_type') != 'REG' or number(r, 'week') > max_week:
            excluded['outside_training_window'] += 1
            continue
        team, defense, kind = r.get('posteam'), r.get('defteam'), r.get('play_type')
        if not team or not defense or number(r, 'no_play') or kind == 'no_play' or number(r, 'penalty'):
            excluded['penalty_or_missing_possession'] += 1
            continue
        if kind == 'run':
            kind = 'rush'
        if number(r, 'extra_point_attempt'):
            kind = 'extra_point'
        elif number(r, 'two_point_attempt'):
            kind = 'two_point'
        elif number(r, 'sack'):
            kind = 'sack'
        elif number(r, 'qb_kneel'):
            kind = 'kneel'
        elif number(r, 'qb_spike'):
            kind = 'spike'
        if kind not in ('pass', 'rush', 'sack', 'punt', 'field_goal', 'kneel', 'spike', 'extra_point', 'two_point'):
            excluded['unsupported_event'] += 1
            continue
        stamp = r.get('time_of_day', '')
        if not stamp:
            excluded['missing_actual_timestamp'] += 1
            continue
        down, field = number(r, 'down', 1), number(r, 'yardline_100')
        if kind in ('extra_point', 'two_point'):
            down, field, elapsed = 1, max(1, min(99, field)), 1
        else:
            if not 1 <= down <= 4 or not 1 <= field <= 99:
                excluded['invalid_state'] += 1
                continue
            elapsed = 0
            for nxt in rows[index + 1:index + 6]:
                if nxt.get('game_id') != r.get('game_id') or nxt.get('game_half') != r.get('game_half'):
                    break
                delta = number(r, 'game_seconds_remaining') - number(nxt, 'game_seconds_remaining')
                if delta > 0:
                    elapsed = delta
                    break
            if not 1 <= elapsed <= 90:
                excluded['unknown_or_extreme_clock_duration'] += 1
                continue
        qb, receiver, runner = r.get('passer_player_id', ''), r.get('receiver_player_id', ''), r.get('rusher_player_id', '')
        if (kind in ('pass','spike') and not qb) or (kind in ('rush', 'kneel') and not runner) or (number(r, 'complete_pass') and kind == 'pass' and not receiver):
            excluded['missing_player_identity'] += 1
            continue
        if number(r, 'lateral_reception') or number(r, 'lateral_rush') or number(r, 'lateral_return'):
            excluded['unsupported_lateral'] += 1
            continue
        key = (r['game_id'], r.get('fixed_drive') or r.get('drive'), team)
        start = key not in first_drive
        first_drive.add(key)
        made = r.get('field_goal_result') == 'made' or r.get('extra_point_result') == 'good' or r.get('two_point_conv_result') == 'success'
        row = dict(game_id=r['game_id'], play_id=r['play_id'], played_at=stamp, offense=team, defense=defense,
                   down=down, yards_to_go=max(1, number(r, 'ydstogo', 10)), yardline_100=field,
                   seconds_remaining=max(0, min(3600, number(r, 'game_seconds_remaining'))),
                   score_diff=number(r, 'score_differential'), play_type=kind, yards_gained=number(r, 'yards_gained'),
                   elapsed_seconds=elapsed, drive_start=int(start), complete_pass=int(kind == 'pass' and bool(number(r, 'complete_pass'))),
                   interception=int(kind == 'pass' and bool(number(r, 'interception'))), fumble_lost=number(r, 'fumble_lost'),
                   field_goal_made=int(made), punt_yards=max(0, min(100, number(r, 'kick_distance'))),
                   turnover_return_yards=max(0, min(100, number(r, 'return_yards'))), passer_id=qb or '', receiver_id=receiver or '',
                   rusher_id=runner or '', availability='{}')
        for optional in ('epa','success','air_yards','yards_after_catch'):
            row[optional]=r.get(optional) or ''
        output.append(row)
    target = io.StringIO()
    writer = csv.DictWriter(target, fieldnames=sorted(REQUIRED | {'play_id', 'availability','epa','success','air_yards','yards_after_catch'}))
    writer.writeheader()
    writer.writerows(output)
    return target.getvalue(), {'normalizedPlays': len(output), 'excluded': dict(excluded), 'maxTrainingWeek': max_week,
                               'limitations': ['Penalties/laterals and unknown clock durations excluded; this selection can bias the fitted model.', 'No injury, roster, weather or license entitlement metadata supplied by this adapter.', 'time_of_day is source event time; no claim it represents publication time.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--max-week', type=int, default=12)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    normalized, report = normalize(read_pbp(args.input), args.max_week)
    args.out.write_text(normalized)
    report.update(source=SOURCE, inputSha256=hashlib.sha256(raw).hexdigest(), createdAt=datetime.now(timezone.utc).isoformat())
    args.out.with_suffix('.provenance.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
