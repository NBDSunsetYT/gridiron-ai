import {createHash} from 'node:crypto';
import Decimal from 'decimal.js';
import {parseCSVRecords} from './csv';
const transactionTypes=['starting_balance','deposit','withdrawal','transfer','promotional_credit','adjustment','refund'];
export function financialImportRows(input:unknown){
 if(!Array.isArray(input)||!input.length||input.length>1000)throw Error('Import requires 1–1,000 verified transaction rows.');
 return input.map((raw:any)=>{
  if(!raw||typeof raw!=='object'||Array.isArray(raw)||!transactionTypes.includes(raw.type)||!['DraftKings','Hard Rock'].includes(raw.sportsbook))throw Error('Choose valid transaction types and sportsbooks for every CSV row.');
  const amount=String(raw.amount);if(!/^-?\d+(\.\d{1,2})?$/.test(amount))throw Error('CSV amounts require exact decimal dollars with at most two decimal places.');
  const decimal=new Decimal(amount);if(!decimal.isFinite()||decimal.abs().gt(1_000_000_000))throw Error('CSV amount is outside the supported range.');
  const date=raw.date?new Date(String(raw.date)).toISOString():'';
  const row:Record<string,string>={type:raw.type,sportsbook:raw.sportsbook,amount:decimal.toFixed(2),date};
  for(const key of ['toSportsbook','note','reference']){if(raw[key]!==undefined&&typeof raw[key]!=='string')throw Error('CSV text fields must contain text.');row[key]=(raw[key]||'').trim();}
  return row;
 });
}
export function financialImportPlan(body:{rows?:unknown;csv?:unknown;sourceHash?:unknown}){
 const parsed=typeof body.csv==='string'?parseCSVRecords(body.csv):body.rows,rows=financialImportRows(parsed);
 if(body.rows&&typeof body.csv==='string'&&JSON.stringify(financialImportRows(body.rows))!==JSON.stringify(rows))throw Error('The reviewed rows do not match the uploaded CSV. Review the original file again.');
 const sourceHash=typeof body.csv==='string'?createHash('sha256').update(body.csv).digest('hex'):null;
 if(body.sourceHash!==undefined&&body.sourceHash!==sourceHash)throw Error('CSV file integrity check failed.');
 const digest=createHash('sha256').update(JSON.stringify(rows)).digest('hex');
 return{digest,sourceHash,rows:rows.map((r,i)=>({...r,reference:r.reference||`csv:${digest}:${i}`}))};
}
