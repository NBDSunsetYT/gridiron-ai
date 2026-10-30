import {parseCSVRecords} from './csv';
export const contractCSVColumns=['contractId','eventId','event','question','threshold','operator','eventStart','settlementRule','rulesUrl','yesAskCents','noAskCents','quotedAt','sourceUrl','entryFeeCents','winFeeCents','feeSource'];
export function parseContractCSV(source:string){return parseCSVRecords(source,100).map((raw,i)=>{
 for(const key of contractCSVColumns)if(!(key in raw)||raw[key]==='')throw Error(`CSV row ${i+2} is missing ${key}. Missing fees and settlement terms are not inferred.`);
 const threshold=Number(raw.threshold);if(!Number.isFinite(threshold))throw Error(`CSV row ${i+2} threshold must be finite.`);
 const quote:Record<string,any>={...raw,threshold,verified:false,entryFeeRounding:raw.entryFeeRounding||'none',liquidityContracts:raw.liquidityContracts?Number(raw.liquidityContracts):null};
 for(const key of ['yesBidCents','noBidCents'])if(!quote[key])delete quote[key];
 if(raw.settlementDefinition)quote.settlementDefinition=JSON.parse(raw.settlementDefinition);else delete quote.settlementDefinition;
 return quote;
});}
/** Conservative OCR helpers extract only explicitly labelled text; every candidate remains unverified. */
export function contractOCRSuggestions(text:string){
 const cents=(label:string)=>{const match=text.match(new RegExp(`\\b${label}\\s*(?:price|ask|fee)?\\s*[:=]?\\s*(\\d{1,2}(?:\\.\\d{1,4})?)\\s*(?:¢|cents\\b)`,'i'));return match?.[1];};
 const result:Record<string,any>={};
 for(const [label,key] of [['YES','yesAskCents'],['NO','noAskCents'],['Entry','entryFeeCents'],['Win','winFeeCents']]){const value=cents(label);if(value!==undefined)result[key]=value;}
 for(const [label,key] of [['Contract ID','contractId'],['Event ID','eventId']]){const match=text.match(new RegExp(`${label}\\s*[:=]\\s*([A-Za-z0-9_.:-]+)`,'i'));if(match)result[key]=match[1];}
 const threshold=text.match(/\bthreshold\s*[:=]\s*(-?\d+(?:\.\d+)?)/i);if(threshold)result.threshold=Number(threshold[1]);
 const question=text.split(/\r?\n/).find(line=>line.trim().length>=5&&line.includes('?'));if(question)result.question=question.trim();
 return result;
}
