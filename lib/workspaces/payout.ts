import Decimal from 'decimal.js';
/** An explicitly user-entered hypothetical multiplier, never an executable combination offer. */
export function hypotheticalPayout(amount:string,multiplier:string,fees:string){
 if(![amount,fees].every(v=>/^(0|[1-9]\d{0,6})(\.\d{1,2})?$/.test(v))||!/^(0|[1-9]\d{0,5})(\.\d{1,6})?$/.test(multiplier))throw Error('Enter valid nonnegative amounts and a multiplier.');
 const stake=new Decimal(amount),multiple=new Decimal(multiplier),cost=new Decimal(fees);if(multiple.lt(1))throw Error('Gross-return multiplier must be at least 1.');
 const gross=stake.mul(multiple).toDecimalPlaces(2,Decimal.ROUND_DOWN),net=gross.minus(cost),profit=net.minus(stake);if(net.lt(0))throw Error('Fees exceed the theoretical return.');
 return{amount:stake.toFixed(2),multiplier:multiple.toString(),grossPayout:gross.toDecimalPlaces(2,Decimal.ROUND_DOWN).toFixed(2),netPayout:net.toDecimalPlaces(2,Decimal.ROUND_DOWN).toFixed(2),profit:profit.toDecimalPlaces(2,Decimal.ROUND_DOWN).toFixed(2),fees:cost.toFixed(2),breakEvenProbability:stake.gt(0)&&net.gt(0)?stake.div(net).toNumber():null,pricingBasis:'user_hypothetical',jointProbability:null,feeAssumption:'Entered fees are charged on a winning return only; excluded on a loss.'};
}
