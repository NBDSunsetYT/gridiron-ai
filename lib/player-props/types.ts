import type {PublicGame,ResearchSource} from '../public-nfl/types';
import type {PropMarketContract,PropProviderStatus,PropStat} from './market-types';
export type {PropMarketContract,PropProviderStatus,PropStat} from './market-types';

export type PropDistribution={histogram:Array<{value:number;count:number}>;simulations:number;mean:number|null;p10:number|null;p50:number|null;p90:number|null;encoding:'exact_integer_frequency_v1';coverage:string};
export type PropResearch={
 id:string;runId:string;game:PublicGame;contract:PropMarketContract;currentContract?:PropMarketContract;
 player:{id:string|null;name:string;team:string;position:string|null};side:'YES'|'NO';
 status:'available'|'conditional'|'withheld'|'stale'|'historical';stale:boolean;withheldReasons:string[];modelInputsCurrent?:boolean;
 simulationId:string|null;modelVersion:string|null;inputVersion:string|null;simulations:number;
 probability:{raw:number|null;calibrated:number|null;conditional:boolean;condition:string|null;interval95:[number,number]|null;samplingError:number|null;modelInterval95:[number,number]|null;calibrationStatus:string;calibrationArtifactId?:string|null;historicalSampleSize:number;historicalBrier:number|null};
 valuation:{breakEven:number|null;fairCents:string|null;netValueCents:string|null;entryCostCents:string|null;feesVerified:boolean;reason:string};
 currentValuation?:PropResearch['valuation'];distribution:PropDistribution|null;
 injury:{status:string;message:string;checkedAt:string|null;affectedPlayers:Array<{id:string;name:string;status:string}>;fullyAdjusted:boolean;probabilityChange:number|null};
 sensitivity:{injury:string;weather:string;injuryDelta:number|null;weatherDelta:number|null};
 dataQuality:{score:number;checks:Array<{name:string;passed:boolean}>;meaning:string};
 rankingReason:string;capturedAt:string;updatedAt:string;sources:ResearchSource[];assumptions:string[];
 rankingMetrics?:{calibratedProbability:number|null;modelMarketDifference:number|null;historicalSupport:number|null;uncertaintyWidth:number|null;injuryChange:number|null;priceChange:number|null;modelMarketDifferenceBasis?:'observed_ask'|'displayed_percentage'|null};
 settlementEstimate?:{winProbability:number;lossProbability:number;tieProbability:number;tiePayoutCents:string;expectedSettlementCents:string;condition:string};
};
export type PropScanStatus='queued'|'running'|'completed'|'partial'|'unavailable'|'failed';
export type PropScan={
 status:PropScanStatus;runId:string|null;message?:string;resultSetId?:string|null;updatedAt:string;providers:PropProviderStatus[];games:PublicGame[];
 results:PropResearch[];progress:{completed:number;total:number;phase:string;gamesComplete:number;gamesTotal:number};
 sources:ResearchSource[];limitations:string[];performance:Record<string,unknown>;totalResults:number;nextCursor:string|null;
 primaryProvider?:'DraftKings Predictions';marketScope?:'all'|'player'|'game';ranking?:string;rankingMeaning?:string;
 paginationStable?:boolean;
};
export type PropRun={id:string;status:PropScanStatus;data:Record<string,any>;result:Record<string,any>|null;error:string|null;lease:string|null;created_at:string;updated_at:string};
export type PropCategory=PropStat;
