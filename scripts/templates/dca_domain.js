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
  rallyCorrection:Object.freeze({id:'rallyCorrection',risePercent:25,riseMonths:4,drawdownPercent:30,declineMonths:6,recoveryMode:'current',recoveryPercent:100,recoveryMonths:null,useCycleReference:false,sequence:'rise-correction'}),
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

 function analyzeOutcomeTimeline({points,periodsPerMonth,buyPeriods,startPrice,declineEndPeriod}){
  const rows=Array.isArray(points)?points:[],ppm=Math.max(1,Number(periodsPerMonth)||1),toMonth=period=>Math.max(0,Math.ceil(period/ppm)),valid=rows.filter(row=>row.invested>0),firstLoss=valid.findIndex(row=>row.value<row.invested-1e-8),searchFrom=firstLoss>=0?firstLoss:0;
  const breakEven=valid.slice(searchFrom).find(row=>row.value>=row.invested-1e-8),firstProfit=valid.slice(searchFrom).find(row=>row.value>row.invested+1e-8);
  let sustainedProfit=null;
  for(let i=searchFrom;i<valid.length;i++){if(valid[i].value>valid[i].invested+1e-8&&valid.slice(i).every(row=>row.value>=row.invested-1e-8)){sustainedProfit=valid[i];break;}}
  const returned=valid.find(row=>row.period>Math.max(0,declineEndPeriod||0)&&row.price>=startPrice-1e-8);
  const buyCompleteMonth=toMonth(buyPeriods),breakEvenMonth=breakEven?toMonth(breakEven.period):null;
  return{buyCompleteMonth,breakEvenMonth,firstProfitMonth:firstProfit?toMonth(firstProfit.period):null,sustainedProfitMonth:sustainedProfit?toMonth(sustainedProfit.period):null,returnToStartMonth:returned?toMonth(returned.period):null,monthsAfterBuyingToBreakEven:breakEvenMonth===null?null:Math.max(0,breakEvenMonth-buyCompleteMonth),experiencedLoss:firstLoss>=0};
 }

 function buildPricePath({model='linear',current,bottom,target,steps,downSteps,recentPrices=[]}){
  const count=Math.max(1,Math.round(steps)),decline=Math.min(count,Math.max(1,Math.round(downSteps))),requested=model,history=Array.isArray(recentPrices)?recentPrices.map(Number).filter(value=>value>0):[],usableRecent=requested==='recent3m'&&history.length>=10,modelUsed=requested==='recent3m'&&!usableRecent?'linear':requested;
  const smooth=t=>t*t*(3-2*t),sample=t=>{const index=t*(history.length-1),lo=Math.floor(index),hi=Math.min(history.length-1,lo+1),mix=index-lo;return history[lo]*(1-mix)+history[hi]*mix},historyStart=history[0]||1,historyEnd=history.at(-1)||historyStart;
  const prices=[current];
  for(let i=1;i<=count;i++){
   const falling=i<=decline,t=falling?i/decline:(i-decline)/Math.max(1,count-decline),from=falling?current:bottom,to=falling?bottom:target,eased=modelUsed==='cycle'?smooth(t):t;
   let price=from+(to-from)*eased;
   if(modelUsed==='recent3m'){
    const observed=sample(t)/historyStart,trend=1+(historyEnd/historyStart-1)*t,residual=Math.max(-.12,Math.min(.12,observed/Math.max(.0001,trend)-1));price*=1+residual*Math.sin(Math.PI*t);
   }else if(modelUsed==='stress'){
    const wiggle=(Math.sin(i*1.71)+Math.sin(i*.47))*.022;price*=1+wiggle*Math.sin(Math.PI*t);
   }
   prices.push(Math.max(.01,price));
  }
  prices[decline]=bottom;prices[count]=target;
  return{prices,modelUsed,requestedModel:requested,sourcePoints:usableRecent?history.length:0,fallbackReason:requested==='recent3m'&&!usableRecent?'recent-data-unavailable':null};
 }

 function buildRiseCorrectionPath({model='cycle',current,peak,bottom,target,steps,riseSteps,declineSteps,recentPrices=[]}){
  const count=Math.max(2,Math.round(steps)),rise=Math.min(count-1,Math.max(1,Math.round(riseSteps))),fall=Math.min(count-rise,Math.max(1,Math.round(declineSteps))),turn=rise+fall;
  const first=buildPricePath({model,current,bottom:peak,target:peak,steps:rise,downSteps:rise,recentPrices});
  const second=buildPricePath({model,current:peak,bottom,target,steps:count-rise,downSteps:fall,recentPrices});
  const prices=first.prices.concat(second.prices.slice(1));
  prices[rise]=peak;prices[turn]=bottom;prices[count]=target;
  return{prices,modelUsed:second.modelUsed,requestedModel:model,sourcePoints:second.sourcePoints,fallbackReason:first.fallbackReason||second.fallbackReason,peakPeriod:rise,declineEndPeriod:turn};
 }

 function simulateScenario({current,bottom,target,steps,downSteps,initial,contribution,budget,annualDiv,periodsPerYear,model='linear',recentPrices=[],pricePath=null}){
  const path=Array.isArray(pricePath)&&pricePath.length===steps+1?pricePath:buildPricePath({model,current,bottom,target,steps,downSteps,recentPrices}).prices;
  let reserve=initial,allocated=initial,dividendCash=0,first=boardLotPurchase(reserve,current),shares=first.shares,invested=first.cost,worst=0;
  reserve-=first.cost;
  for(let i=1;i<=steps;i++){
   const price=path[i];
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
  const value=shares*path.at(-1)+dividendCash,pnl=value-invested;
  return{invested,value,pnl,pct:invested?pnl/invested*100:0,worst:worst*100};
 }

 return Object.freeze({SCENARIO_PRESETS,periodsPerMonth,contributionPerPeriod,boardLotPurchase,assessMonthlyBudget,rankAffordableAlternatives,analyzeOutcomeTimeline,buildPricePath,buildRiseCorrectionPath,simulateScenario});
});
