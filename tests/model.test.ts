import {describe,it,expect} from 'vitest';
import {americanOdds,decimalOdds,distribution,parlay,rollingMetrics,wilson} from '../lib/model';
describe('price and distribution calculations',()=>{
  it('converts prices and break-even probabilities exactly',()=>{
    expect(decimalOdds(-110)).toBeCloseTo(1.909090909);
    expect(1/decimalOdds(-110)).toBeCloseTo(.523809524);
    expect(americanOdds(2.5)).toBe(150);expect(americanOdds(1.5)).toBe(-200);
    expect(()=>decimalOdds(0)).toThrow();
  });
  it('fits supplied observations and treats returned pushes as zero profit',()=>{
    const data=[...Array(20).fill(70),...Array(20).fill(50),...Array(10).fill(60)];
    const m=distribution(data,60,'over',100);
    expect(m.probability).toBe(.5);expect(m.pushProbability).toBe(.2);expect(m.expectedValue).toBe(0);
    expect(m.sampleSize).toBe(50);expect(m.projection.mean).toBe(60);
    expect(m.histogram.reduce((n,b)=>n+b.count,0)).toBe(50);
  });
  it('does not claim certainty or performance with insufficient observations',()=>{
    expect(()=>distribution([1,2],1.5,'over',-110)).toThrow();
    const m=distribution(Array(20).fill(70),64.5,'over',-110);
    expect(m.probability).toBeLessThan(1);expect(m.metrics).toBeNull();
    expect(m.uncertainty[0]).toBeLessThan(1);
  });
  it('rolling validation predicts each next outcome from earlier observations only',()=>{
    const data=Array.from({length:60},(_,i)=>i%3===0?80:40);
    const rows=[];
    for(let i=20;i<data.length;i++){
      const p=(data.slice(0,i).filter(v=>v>60).length+.5)/(i+1),y=+(data[i]>60);rows.push({p,y});
    }
    const result=rollingMetrics(data,60,'over')!;
    expect(result.n).toBe(40);
    expect(result.brier).toBeCloseTo(rows.reduce((s,r)=>s+(r.p-r.y)**2,0)/rows.length,12);
    expect(result.calibration.reduce((s,b)=>s+b.n,0)).toBe(40);
  });
  it('Wilson intervals include 0 and 1 boundaries and contract with sample size',()=>{
    expect(wilson(0,20)[0]).toBeCloseTo(0);expect(wilson(20,20)[1]).toBeCloseTo(1);
    const a=wilson(10,20),b=wilson(100,200);expect(b[1]-b[0]).toBeLessThan(a[1]-a[0]);
  });
});
describe('parlay dependence',()=>{
  it('rejects silently assuming independence',()=>expect(()=>parlay({probabilities:[.5,.5],odds:[100,100]})).toThrow(/dependence/));
  it('preserves perfect positive correlation in aligned outcomes',()=>{
    const jointSamples=Array.from({length:100},(_,i)=>[i<50,i<50]);
    const m=parlay({probabilities:[.5,.5],odds:[100,100],jointSamples});
    expect(m.jointProbability).toBe(.5);expect(m.independenceProbability).toBe(.25);expect(m.expectedValue).toBe(1);
  });
  it('captures mutually exclusive legs rather than multiplying probabilities',()=>{
    const jointSamples=Array.from({length:100},(_,i)=>[i<50,i>=50]);
    const m=parlay({probabilities:[.5,.5],odds:[100,100],jointSamples});
    expect(m.jointProbability).toBeLessThan(.01);expect(m.independenceProbability).toBe(.25);
  });
  it('clearly labels explicit independence as hypothetical',()=>{
    const m=parlay({probabilities:[.6,.5],odds:[-110,100],independenceAssumed:true});
    expect(m.jointProbability).toBe(.3);expect(m.uncertainty).toBeNull();expect(m.method).toMatch(/Hypothetical/);
  });
});
