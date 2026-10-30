"""Auditable empirical baseline. Inputs: CSV observed_at,value; oldest to newest.

This pipeline does not supply NFL data or claim opponent-adjusted forecasting.
Only Python's standard library is required.
"""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

VERSION = "empirical-rolling-python-1.0"


def utc(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Every observed_at timestamp needs a timezone")
    return result.astimezone(timezone.utc)


def analyze(rows, threshold, direction, odds, source, as_of=None):
    if direction not in ("over", "under") or not math.isfinite(threshold):
        raise ValueError("Finite threshold and over/under direction required")
    if abs(odds) < 100 or not math.isfinite(odds):
        raise ValueError("Valid American odds required")
    if not source.strip():
        raise ValueError("Data provenance is required")
    as_of = as_of or datetime.now(timezone.utc)
    values, previous = [], None
    for row in rows:
        when, value = utc(row["observed_at"]), float(row["value"])
        if not math.isfinite(value):
            raise ValueError("Non-finite observations are not allowed")
        if previous is not None and when <= previous:
            raise ValueError("Observations must have unique, strictly increasing timestamps")
        if when > as_of:
            raise ValueError("An observation occurs after the declared as_of cutoff")
        previous = when
        values.append(value)
    if len(values) < 20:
        raise ValueError("At least 20 comparable observations required")

    def win(x):
        return x > threshold if direction == "over" else x < threshold

    def fit(data):
        resolved = [x for x in data if x != threshold]
        if len(resolved) < 20:
            return None
        return (sum(map(win, resolved)) + 0.5) / (len(resolved) + 1)

    probability = fit(values)
    if probability is None:
        raise ValueError("At least 20 non-push observations required")
    # Each row is predicted once from its strict historical prefix. No shuffling.
    predictions = []
    for index in range(20, len(values)):
        p = fit(values[:index])
        if p is not None and values[index] != threshold:
            predictions.append({"index": index, "probability": p, "outcome": int(win(values[index]))})
    metrics = None
    if len(predictions) >= 20:
        n = len(predictions)
        calibration = []
        for bucket in range(10):
            points = [r for r in predictions if min(9, int(r["probability"] * 10)) == bucket]
            calibration.append({"bucket": bucket, "n": len(points),
                                "predicted": sum(r["probability"] for r in points) / len(points) if points else None,
                                "observed": sum(r["outcome"] for r in points) / len(points) if points else None})
        metrics = {"n": n, "brier": sum((r["probability"] - r["outcome"]) ** 2 for r in predictions) / n,
                   "log_loss": -sum(r["outcome"] * math.log(r["probability"]) + (1-r["outcome"]) * math.log(1-r["probability"]) for r in predictions) / n,
                   "calibration": calibration, "validation": "expanding rolling origin; initial 20 outcomes reserved for fit"}
    dec = 1 + odds / 100 if odds > 0 else 1 + 100 / -odds
    push = values.count(threshold) / len(values)
    return {"model_version": VERSION, "provenance": source, "as_of": as_of.isoformat(),
            "sample_size": len(values), "probability": probability, "push_probability": push,
            "break_even": 1 / dec, "expected_value_per_dollar": (1-push) * (probability * dec - 1),
            "out_of_sample": metrics, "predictions": predictions,
            "limitations": ["Unadjusted retrospective empirical baseline; not a trained NFL projection model.",
                            "Source observations are user-supplied and not independently verified.",
                            "Threshold selection on these same outcomes creates selection bias; freeze it before validation."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--direction", choices=("over", "under"), required=True)
    parser.add_argument("--odds", type=float, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--as-of", help="Timezone-aware evidence cutoff; defaults to now")
    parser.add_argument("--out", type=Path, default=Path("model-report.json"))
    args = parser.parse_args()
    raw = args.csv.read_bytes()
    with args.csv.open(newline="") as handle:
        result = analyze(list(csv.DictReader(handle)), args.threshold, args.direction, args.odds, args.source, utc(args.as_of) if args.as_of else None)
    result["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    args.out.write_text(json.dumps(result, indent=2))
    print(f"Saved {args.out}; {result['sample_size']} source observations; model {VERSION}")


if __name__ == "__main__":
    main()
