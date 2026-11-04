/** Public, read-only experiment evidence. Never trains, prices a bet or opens a ledger. */
import {z} from 'zod';

type Report = {
 version: string; generatedAt: string; uniqueGames: number; forecastVersions: number;
 completeSimulatedGames: number; strictPregameQualifiedGames: number;
 productionPromotions: number; productionChampion: unknown;
 researchSelectedModels: Record<string, string>; diagnosticFinalists: Record<string, string>;
 finalTestComplete: boolean; finalTest: Record<string, unknown>;
 stoppingConditions: Record<string, string>;
 iterations: Array<{sport: string; iteration: number; challenger: string; incumbent: string; gate: unknown}>;
 limitations: string[];
};

export function offlineExperimentEvidence(report: Report, input: unknown) {
 const args = z.object({sport: z.enum(['NFL', 'CFB', 'NBA']).optional()}).strict().parse(input);
 const sports = Object.keys(report.finalTest).filter(sport => !args.sport || sport === args.sport);
 return {
  scope: 'retrospective_independent_model_research', protocolVersion: report.version,
  source: '/api/engine?view=iterations', sourceTimestamp: report.generatedAt,
  sample: {distinctGames: report.uniqueGames, forecastVersions: report.forecastVersions,
   completeSimulatedGames: report.completeSimulatedGames, strictlyPregameQualifiedGames: report.strictPregameQualifiedGames},
  productionChampion: report.productionChampion, productionPromotions: report.productionPromotions,
  selectedResearchModels: Object.fromEntries(sports.map(sport => [sport, report.researchSelectedModels[sport]])),
  diagnosticFinalists: Object.fromEntries(sports.map(sport => [sport, report.diagnosticFinalists[sport]])),
  untouchedPeriodEvaluation: Object.fromEntries(sports.map(sport => [sport, report.finalTest[sport]])),
  finalTestComplete: report.finalTestComplete,
  decisions: report.iterations.filter(row => sports.includes(row.sport)).map(({sport, iteration, challenger, incumbent, gate}) => ({sport, iteration, challenger, incumbent, gate})),
  stoppingConditions: Object.fromEntries(sports.map(sport => [sport, report.stoppingConditions[sport]])),
  limitations: report.limitations,
  interpretation: 'Raw simulation reliability is measured, not assumed calibrated. A better score average alone does not prove an improved model. Fixed research thresholds are not historical betting lines. No financial records or newly run simulations are included.',
 };
}
