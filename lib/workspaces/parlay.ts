import Decimal from 'decimal.js';
import type {WorkspaceData} from './schema';
export type ParlayLeg=WorkspaceData['legs'][number];
/** Price-free identity: changing a quote must not add a duplicate outcome. */
export function selectionKey(leg:ParlayLeg){const q=leg.sourceQuote;if(q?.target){const {cursor,...target}=q.target as Record<string,unknown>;return JSON.stringify(target);};return JSON.stringify([leg.event,leg.player,leg.market,leg.selection,leg.threshold]);}
export function toggleLeg(legs:ParlayLeg[],leg:ParlayLeg){const key=selectionKey(leg);if(legs.some(l=>selectionKey(l)===key))return legs.filter(l=>selectionKey(l)!==key);if(legs.length>=12)throw Error('A research combination supports up to 12 selections.');return[...legs,leg];}
export function theoreticalCombinedPrice(legs:ParlayLeg[]){
 if(legs.length<2)return null;let multiplier=new Decimal(1);
 for(const leg of legs){if(leg.source.startsWith('User-edited'))return null;const q=leg.currentQuote??leg.sourceQuote;if(!q||q.family!=='sportsbook_reference'||!Number.isSafeInteger(q.americanOdds)||Math.abs(Number(q.americanOdds))<100)return null;const odds=new Decimal(Number(q.americanOdds));multiplier=multiplier.mul(odds.gt(0)?odds.div(100).plus(1):new Decimal(100).div(odds.abs()).plus(1));}
 const american=multiplier.gte(2)?multiplier.minus(1).mul(100):new Decimal(-100).div(multiplier.minus(1));return{decimal:multiplier.toDecimalPlaces(6,Decimal.ROUND_DOWN).toString(),american:american.toDecimalPlaces(0,Decimal.ROUND_DOWN).toString(),verifiedOffer:false as const};
}
