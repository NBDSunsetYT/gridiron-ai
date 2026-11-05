"""Versioned, non-destructive adapter for frozen research forecast records."""
import math
def nested_predictions(row):
    out={**row,'predictions':dict(row['predictions'])}
    for name in ['lineup_state_minutes']:
        if name not in row:continue
        value=float(row[name])
        if not math.isfinite(value):raise ValueError('Non-finite archived forecast')
        if name in out['predictions'] and out['predictions'][name]!=value:raise ValueError('Conflicting archived forecast fields')
        out['predictions'][name]=value
    return out
