(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.DcaDomain=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';

 const SCENARIO_PRESETS=Object.freeze({
  cycle:Object.freeze({id:'cycle',drawdownPercent:null,declineMonths:null,recoveryMode:'current',recoveryPercent:100,recoveryMonths:null,useCycleReference:true}),
  mild:Object.freeze({id:'mild',drawdownPercent:10,declineMonths:3,recoveryMode:'current',recoveryPercent:100,recoveryMonths:null,useCycleReference:false}),
  correction:Object.freeze({id:'correction',drawdownPercent:25,declineMonths:9,recoveryMode:'partial',recoveryPercent:50,recoveryMonths:null,useCycleReference:false}),
  crisis:Object.freeze({id:'crisis',drawdownPercent:50,declineMonths:18,recoveryMode:'none',recoveryPercent:0,recoveryMonths:null,useCycleReference:false}),
 });

 function periodsPerMonth(frequency){return frequency==='daily'?21:frequency==='weekly'?4:1}

 function contributionPerPeriod({monthlyBudget,frequency}){
  return Math.max(0,Number(monthlyBudget)||0)/periodsPerMonth(frequency);
 }

 function boardLotPurchase(cash,price){
  const shares=price>0?Math.floor((Math.max(0,cash)+1e-8)/price/100)*100:0;
  return{shares,cost:shares*price};
 }

 function assessMonthlyBudget({monthlyBudget,currentPrice,initial=0}){
  const budget=Math.max(0,Number(monthlyBudget)||0),price=Math.max(0,Number(currentPrice)||0),firstCash=Math.max(0,Number(initial)||0),lotCost=price*100;
  if(!lotCost)return{status:'unknown',lotCost:0,monthsPerLot:null,monthsUntilFirstLot:null};
  if(budget>=lotCost)return{status:'fit',lotCost,monthsPerLot:1,monthsUntilFirstLot:firstCash>=lotCost?0:1};
  if(!budget)return{status:'insufficient',lotCost,monthsPerLot:null,monthsUntilFirstLot:firstCash>=lotCost?0:null};
  return{status:'accumulate',lotCost,monthsPerLot:Math.ceil(lotCost/budget),monthsUntilFirstLot:firstCash>=lotCost?0:Math.ceil((lotCost-firstCash)/budget)};
 }

 function rankAffordableAlternatives({stocks,symbol,monthlyBudget,limit=5}){
  const source=stocks&&typeof stocks==='object'?stocks:{},base=source[symbol]||{},baseReturn=Number(base.r?.return60),baseDrawdown=Number(base.r?.maxDrawdown),budget=Math.max(0,Number(monthlyBudget)||0);
  return Object.entries(source).filter(([ticker,item])=>ticker!==symbol&&item?.m?.length&&item.m.at(-1)[1]*100<=budget).map(([ticker,item])=>{
   const current=Number(item.m.at(-1)[1]),ret=Number(item.r?.return60),drawdown=Number(item.r?.maxDrawdown),liquid=Number(item.r?.medianValue30)||0;
   const distance=(Number.isFinite(baseReturn)&&Number.isFinite(ret)?Math.abs(ret-baseReturn):20)+(Number.isFinite(baseDrawdown)&&Number.isFinite(drawdown)?Math.abs(drawdown-baseDrawdown)*.5:10)+(liquid<1000000?25:0);
   return{symbol:ticker,current,lotCost:current*100,return60:Number.isFinite(ret)?ret:null,maxDrawdown:Number.isFinite(drawdown)?drawdown:null,distance};
  }).sort((a,b)=>a.distance-b.distance||b.lotCost-a.lotCost).slice(0,Math.max(0,limit));
 }

 function simulateScenario({current,bottom,target,steps,downSteps,initial,contribution,budget,annualDiv,periodsPerYear}){
  let reserve=initial,allocated=initial,dividendCash=0,first=boardLotPurchase(reserve,current),shares=first.shares,invested=first.cost,worst=0;
  reserve-=first.cost;
  for(let i=1;i<=steps;i++){
   const price=i<=downSteps?current+(bottom-current)*i/downSteps:bottom+(target-bottom)*(i-downSteps)/Math.max(1,steps-downSteps);
   if(annualDiv){
    dividendCash+=shares*(annualDiv/periodsPerYear);
    const reinvest=boardLotPurchase(dividendCash,price);
    shares+=reinvest.shares;
    dividendCash-=reinvest.cost;
   }
   if(contribution>0&&allocated+contribution<=budget+.01){reserve+=contribution;allocated+=contribution;}
   const purchase=boardLotPurchase(reserve,price);
   shares+=purchase.shares;
   invested+=purchase.cost;
   reserve-=purchase.cost;
   const pct=invested?(shares*price+dividendCash)/invested-1:0;
   worst=Math.min(worst,pct);
  }
  const value=shares*target+dividendCash,pnl=value-invested;
  return{invested,value,pnl,pct:invested?pnl/invested*100:0,worst:worst*100};
 }

 return Object.freeze({SCENARIO_PRESETS,periodsPerMonth,contributionPerPeriod,boardLotPurchase,assessMonthlyBudget,rankAffordableAlternatives,simulateScenario});
});
