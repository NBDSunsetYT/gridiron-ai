'use client';
import {useEffect, useState} from 'react';

const number = (value: unknown, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'Unavailable';
type Metrics = {games: number; scores?: {mae: number; rmse: number; bias: number}; scoreCRPS?: number; baselineScores?: {mae: number}; homeWin?: {brier: number; logLoss: number; ece: number; bins: Array<{n: number; meanPredicted: number; observed: number}>}; researchThresholds?: {brier: number}; players?: Record<string, {mae: number; observations: number; coverage: Record<string, number>}>};
type Report = {
  generatedAt: string; uniqueGames: number; forecastVersions: number; completeSimulatedGames: number;
  productionPromotions: number; strictPregameQualifiedGames: number; finalTestComplete: boolean;
  budget: {cpuSeconds: number}; stoppingConditions: Record<string, string>;
  researchSelectedModels: Record<string, string>; diagnosticFinalists: Record<string, string>;
  finalTest: Record<string, Record<string, Metrics>>;
  iterations: Array<{sport: string; iteration: number; challenger: string; incumbent: string; gate: {passed: boolean; vetoes?: string[]; reason?: string; pairedGames: number; multiplicityAdjustedCRPSInterval?: number[]}; challengerMetrics: Metrics}>;
  limitations: string[];
};

export default function IterativeLearning({sport}: {sport?: string}) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/engine?view=iterations', {signal: controller.signal}).then(async response => {
      if (!response.ok) throw Error('The iterative evaluation report could not be loaded.');
      setReport(await response.json());
    }).catch(error => {if (error.name !== 'AbortError') setError(error.message);});
    return () => controller.abort();
  }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!report) return <p role="status">Loading the measured learning experiments…</p>;
  const sports = Object.keys(report.finalTest).filter(value => !sport || sport === 'all' || value === sport);
  return <section aria-label="Iterative model research" className="panel reality-evidence">
    <h2>What the model experiments showed</h2>
    <p>Three chronological validation cohorts per sport. Final tests were locked after model selection. Research candidates remain separate from the production models.</p>
    <div className="reality-scores">
      <article className="reality-score"><span>Games in this experiment</span><strong>{report.uniqueGames}</strong><small>Repeated forecasts count once here</small></article>
      <article className="reality-score"><span>Forecast versions evaluated</span><strong>{report.forecastVersions}</strong><small>{report.completeSimulatedGames.toLocaleString()} complete simulated games</small></article>
      <article className="reality-score"><span>Production promotions</span><strong>{report.productionPromotions}</strong><small>{report.strictPregameQualifiedGames} strictly qualified historical pregame archives</small></article>
    </div>
    {!report.finalTestComplete && <p role="status">Final evaluation is incomplete. Do not interpret partial results as a validated improvement.</p>}
    {sports.map(league => <article key={league} className="reality-evidence">
      <h3>{league} · untouched final period</h3>
      <p className="muted">Stopped: {(report.stoppingConditions[league] ?? 'Not recorded').replaceAll('_', ' ')}. Research selection: {report.researchSelectedModels[league]}. Diagnostic finalist: {report.diagnosticFinalists[league]}.</p>
      <div className="reality-table"><table><caption>Final-test outcomes; lower errors and losses are better</caption><thead><tr><th>Candidate</th><th>Games</th><th>Score MAE</th><th>Recent baseline MAE</th><th>RMSE</th><th>CRPS</th><th>Win Brier</th><th>Log loss</th><th>Calibration gap</th></tr></thead>
        <tbody>{Object.entries(report.finalTest[league]).map(([id, metrics]) => <tr key={id}><th scope="row">{id}</th><td>{metrics.games}</td><td>{number(metrics.scores?.mae)}</td><td>{number(metrics.baselineScores?.mae)}</td><td>{number(metrics.scores?.rmse)}</td><td>{number(metrics.scoreCRPS)}</td><td>{number(metrics.homeWin?.brier)}</td><td>{number(metrics.homeWin?.logLoss)}</td><td>{number(metrics.homeWin?.ece)}</td></tr>)}</tbody></table></div>
      <p className="muted">These are raw probability reliability measurements. No calibration model was fitted to the final test.</p>
      <svg viewBox="0 0 380 300" style={{width: '100%', maxWidth: 440}} role="img" aria-label={league + ' locked final-test raw probability reliability'}>
        <path d="M35 15V225H345M35 225L345 15" fill="none" stroke="var(--muted)" strokeDasharray="4 4"/>
        {Object.entries(report.finalTest[league]).map(([id, metrics], index) => <g key={id} fill={['var(--gold)', 'var(--cyan)', '#47e2a5'][index]}>
          {(metrics.homeWin?.bins ?? []).map((bin, i) => <circle key={i} cx={35 + 310 * bin.meanPredicted} cy={225 - 210 * bin.observed} r={3 + Math.min(5, Math.sqrt(bin.n))}><title>{id}: {bin.n} games; predicted {number(100 * bin.meanPredicted, 1)}%, observed {number(100 * bin.observed, 1)}%</title></circle>)}
          <text x="40" y={248 + index * 16} fontSize="9">{id} · {metrics.games} games</text>
        </g>)}
      </svg>
      <p className="muted">Dots summarize probability buckets; the diagonal represents ideal calibration. These small held-out samples cannot establish reliable calibration by themselves.</p>
      <details><summary>Challenger decisions</summary>{report.iterations.filter(row => row.sport === league).map(row => <div key={row.iteration} className="reality-evidence"><h4>Iteration {row.iteration}: {row.challenger}</h4><p>{row.gate.passed ? 'Research selection gate passed. Production eligibility remains separate.' : 'Rejected by the research selection gate.'} {row.gate.pairedGames} paired games.</p><p>{row.gate.vetoes?.join('; ') || row.gate.reason}</p>{row.gate.multiplicityAdjustedCRPSInterval && <p>Paired CRPS difference interval: {row.gate.multiplicityAdjustedCRPSInterval.map(value => number(value)).join(' to ')}. An interval crossing zero does not establish improvement.</p>}</div>)}</details>
      <details><summary>Player-category final errors</summary>{Object.entries(report.finalTest[league]).map(([id, metrics]) => <div key={id}><h4>{id}</h4><div className="reality-table"><table><thead><tr><th>Category</th><th>Observed pairs</th><th>MAE</th><th>90% interval coverage</th></tr></thead><tbody>{Object.entries(metrics.players ?? {}).map(([stat, metric]) => <tr key={stat}><th scope="row">{stat.replace(/([A-Z])/g, ' $1')}</th><td>{metric.observations}</td><td>{number(metric.mae)}</td><td>{number(100 * metric.coverage['0.9'], 1)}%</td></tr>)}</tbody></table></div></div>)}</details>
    </article>)}
    <p className="muted">Measured local worker CPU: {number(report.budget.cpuSeconds / 60, 1)} minutes. Updated {new Date(report.generatedAt).toLocaleString()}. Hosted simulation workers were not used for these experiments.</p>
    <details><summary>Evidence and limitations</summary><ul>{report.limitations.map(text => <li key={text}>{text}</li>)}</ul></details>
  </section>;
}
