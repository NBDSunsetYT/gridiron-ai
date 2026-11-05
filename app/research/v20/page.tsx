import AccuracyResearchV20,{type AccuracyReport} from '@/components/AccuracyResearchV20';
import report from '@/docs/reports/accuracy-first-v20.json';
import './research.css';
export const dynamic='force-static';
export default function Page(){
 // Ship only the visible checkpoint fields to the iPhone. The complete audit
 // remains a separate cached download; no Python/model computation is invoked.
 const leagues=Object.fromEntries(Object.entries(report.leagues).map(([sport,l])=>{
  const primary=sport==='NBA'?'rebounds':'passingYards';
  return [sport,{evidenceCoverage:l.evidenceCoverage,evaluatedProjectionGames:l.evaluatedProjectionGames,playerObservations:l.playerObservations,phaseBenchmarks:Object.fromEntries(Object.entries(l.phaseBenchmarks).map(([phase,categories])=>[phase,{[primary]:categories[primary as keyof typeof categories]}])),probabilityAndIntervals:Object.fromEntries(Object.entries(l.probabilityAndIntervals).map(([name,m])=>[name,{games:m.games,rawMoneyline:m.rawMoneyline,calibratedMoneyline:null,categories:{[primary]:m.categories[primary as keyof typeof m.categories]}}])),attribution:l.attribution,walkForward:l.walkForward,promotionQualified:l.promotionQualified}];
 }));
 const compact={version:report.version,recordedAt:report.recordedAt,reservedFinalOpened:report.reservedFinalOpened,productionPromotions:report.productionPromotions,attributionCaveat:report.attributionCaveat,quarantined:report.quarantined,leagues};
 return <AccuracyResearchV20 report={compact as unknown as AccuracyReport}/>;
}
