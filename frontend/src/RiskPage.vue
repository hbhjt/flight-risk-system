<script setup>
import { ref, onMounted, computed } from 'vue'
import Chart from './Chart.vue'
const origins=ref([]), destinations=ref([]), carriers=ref([]), dates=ref([]), flights=ref([])
const origin=ref('ATL'),dest=ref('LAX'),carrier=ref(''),date=ref(''),selected=ref(''),record=ref(null),error=ref(''),busy=ref(false),examples=ref([])
let serial=0
const pct=v=>v==null?'—':(v*100).toFixed(1)+'%'
const hhmm=v=>String(v).padStart(4,'0').replace(/(..)(..)/,'$1:$2')
async function api(url){const r=await fetch(url);if(!r.ok)throw Error(r.status===503?'评分结果尚未生成，请先完成模型实验。':`查询失败（${r.status}）`);return r.json()}
async function options(level=0){
 const request=++serial;busy.value=true;error.value='';record.value=null
 try {
  let q=await api('/api/risk/options');if(request!==serial)return
  origins.value=q.origins;if(!origins.value.includes(origin.value))origin.value=origins.value[0]||''
  q=await api('/api/risk/options?origin='+origin.value);if(request!==serial)return
  destinations.value=q.destinations;if(level<2||!destinations.value.includes(dest.value))dest.value=destinations.value.includes(dest.value)?dest.value:destinations.value[0]||''
  q=await api('/api/risk/options?'+new URLSearchParams({origin:origin.value,dest:dest.value}));if(request!==serial)return
  carriers.value=q.carriers;if(!carriers.value.includes(carrier.value))carrier.value=carriers.value[0]||''
  q=await api('/api/risk/options?'+new URLSearchParams({origin:origin.value,dest:dest.value,carrier:carrier.value}));if(request!==serial)return
  dates.value=q.dates;if(!dates.value.includes(date.value))date.value=dates.value[0]||''
  await search(request)
 }catch(e){if(request===serial)error.value=e.message}finally{if(request===serial)busy.value=false}
}
async function search(request=++serial){busy.value=true;error.value='';record.value=null;try{const r=await api('/api/risk/flights?'+new URLSearchParams({origin:origin.value,dest:dest.value,carrier:carrier.value,date:date.value}));if(request!==serial)return;flights.value=r.flights;selected.value=flights.value[0]?.flight_id||'';if(selected.value)await inspect(false,request)}catch(e){if(request===serial)error.value=e.message}finally{if(request===serial)busy.value=false}}
async function inspect(reveal=false,request=++serial){busy.value=true;error.value='';try{const row=await api(`/api/risk/flight/${selected.value}?reveal=${reveal}`);if(request===serial)record.value=row}catch(e){if(request===serial)error.value=e.message}finally{if(request===serial)busy.value=false}}
async function example(id){try{const row=await api('/api/risk/flight/'+id);origin.value=row.Origin;dest.value=row.Dest;carrier.value=row.Reporting_Airline;date.value=row.FlightDate;await options();selected.value=id;await inspect()}catch(e){error.value=e.message}}
onMounted(async()=>{await options();try{examples.value=(await api('/api/risk/examples')).cases}catch(e){error.value=e.message}})
const comparison=computed(()=>({textStyle:{color:'#9aaec8'},grid:{left:100,right:35,top:20,bottom:30},xAxis:{type:'value',min:0,max:100,axisLabel:{formatter:'{value}%'},splitLine:{lineStyle:{color:'#26364d'}}},yAxis:{type:'category',data:['历史率 B0','逻辑回归 B1','基础森林 B2','增强森林 B3'],axisTick:{show:false}},series:[{type:'bar',barMaxWidth:22,label:{show:true,position:'right',formatter:'{c}%',color:'#cbdcee'},data:['B0','B1','B2','B3'].map(k=>({value:+((record.value?.['score_'+k]||0)*100).toFixed(1),itemStyle:{color:k===record.value?.model?'#f6b44d':'#38cfe8'}}))}]}))
</script>
<template>
 <div class="notice">历史回测 · 仅支持 2024 年 6 月已评分的真实航班。风险以未取消、未备降为条件；特征历史截至 2024 年 4 月。</div>
 <section class="filter-bar risk-form" aria-label="风险复盘条件">
  <label>出发机场<select v-model="origin" @change="options(1)"><option v-for="v in origins" :key="v">{{v}}</option></select></label>
  <label>到达机场<select v-model="dest" @change="options(2)"><option v-for="v in destinations" :key="v">{{v}}</option></select></label>
  <label>航司<select v-model="carrier" @change="options(3)"><option v-for="v in carriers" :key="v">{{v}}</option></select></label>
  <label>出发日期<select v-model="date" @change="search()"><option v-for="v in dates" :key="v">{{v}}</option></select></label>
  <label>计划时刻<select v-model="selected" @change="inspect()"><option v-for="f in flights" :key="f.flight_id" :value="f.flight_id">{{hhmm(f.CRSDepTime)}} · {{f.Reporting_Airline}}{{f.Flight_Number_Reporting_Airline}}</option></select></label>
 </section>
 <div v-if="busy" class="loading" role="status">正在读取历史评分…</div><div v-if="error" class="error" role="alert">{{error}} <button @click="options()">重试</button></div>
 <div v-if="record" :class="{pending:busy}" class="risk-content">
  <div class="main-grid"><section class="panel score-panel"><div class="eyebrow">HISTORICAL RISK REPLAY</div><h2>{{record.Origin}} → {{record.Dest}} <span class="pill">{{record.Reporting_Airline}}{{record.Flight_Number_Reporting_Airline}}</span></h2><div class="risk-number">{{pct(record.score)}}</div><p>模型估计分数 · {{record.model}} / {{record.version}}</p><div class="decision">{{record.predicted_delayed?'达到延误判定阈值':'低于延误判定阈值'}} <span>验证集阈值 {{pct(record.threshold)}}</span></div><p>{{record.FlightDate}} · 计划出发 {{hhmm(record.CRSDepTime)}}（出发机场当地时间）</p><p class="risk-explain">此分数来自离线模型，未进行额外概率校准。它表达条件风险，不能保证航班实际结果。</p></section>
   <section class="panel"><div class="panel-heading"><div><h2>相同航班的模型比较</h2><p>四组模型共享测试样本 · 阈值分别在验证集确定</p></div></div><Chart :option="comparison" label="同一航班四个模型的风险分数"/></section></div>
  <div class="kpi-grid"><article class="kpi"><span>航线历史参考（平滑率）</span><strong>{{pct(record.historical_reference)}}</strong><p>2024 年 1—4 月 · {{record.hist_route_count.toLocaleString()}} 个有效历史样本</p></article><article class="kpi"><span>出发机场历史支持</span><strong>{{record.hist_origin_count.toLocaleString()}}</strong><p>历史延误率 {{pct(record.hist_origin_rate)}}</p></article><article class="kpi"><span>航空公司历史支持</span><strong>{{record.hist_carrier_count.toLocaleString()}}</strong><p>历史延误率 {{pct(record.hist_carrier_rate)}}</p></article><article class="kpi"><span>计划属性</span><strong>{{record.CRSElapsedTime}}<small>分钟</small></strong><p>距离 {{record.Distance}} 英里 · 支持数不是置信度</p></article></div>
  <section class="panel outcome"><div><h2>真实结果复盘</h2><p>先查看风险判断，再展开该历史航班的实际标签。</p></div><button v-if="record.actual_delayed===undefined" class="action" @click="inspect(true)">展开实际结果</button><strong v-else :class="record.actual_delayed?'amber':'cyan'">{{record.actual_delayed?'实际到达延误 ≥15 分钟':'实际到达延误 <15 分钟'}} · {{record.actual_delayed===record.predicted_delayed?'本例判断一致':'本例判断不一致'}}</strong></section>
 </div>
 <div v-else-if="!busy&&!error" class="empty">当前条件没有已评分记录，请调整条件。</div>
 <section class="panel examples"><h2>真实航班示例</h2><p>按固定规则从四类判断结果中选取，供复盘使用，不代表总体表现。</p><div><button v-for="(row,i) in examples" :key="row.flight_id" @click="example(row.flight_id)">{{row.origin}} → {{row.dest}} <small>{{row.date}} · 案例 {{i+1}}</small></button></div></section>
</template>
