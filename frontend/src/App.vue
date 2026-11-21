<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount, defineAsyncComponent } from 'vue'
import echarts from './charts.js'
import Chart from './Chart.vue'
import OperationsBrief from './OperationsBrief.vue'
const RiskPage=defineAsyncComponent(()=>import('./RiskPage.vue'))
const ExperimentsPage=defineAsyncComponent(()=>import('./ExperimentsPage.vue'))
const sections = { overview: '运行总览', routes: '航线探索', risk: '单班复盘', experiments: '方法验证' }
const titles={overview:['航空运行驾驶舱','查看延误集中在哪些机场，从机场简报进入航线与时段对照。'],routes:['航线与时段探索','选择机场与计划出发时段，探索历史航线的风险差异。'],risk:['延误风险与历史复盘','查看已评分的真实航班，比较风险判断与实际结果。'],experiments:['实验与系统验证','追溯数据、模型对比与大数据工程实验。']}

const page = ref('overview'), month = ref(''), carrier = ref(''), origin = ref(''), dest = ref(''), hour = ref('')
const choices = ref({ month: [], carrier: [], origin: [], dest: [] }), airports = ref({}), data = ref(null)
const busy = ref(true), error = ref(''), ready = ref(false), geography = ref(null), elapsed = ref(0)
let controller, timer
const pct = v => v == null ? '—' : `${(v * 100).toFixed(1)}%`
const num = v => Number(v ?? 0).toLocaleString('zh-CN')
const airportName = code => airports.value[code]?.city || airports.value[code]?.name || code
const scope = computed(() => month.value || (data.value?.scope.months.length ? `${data.value.scope.months[0]} — ${data.value.scope.months.at(-1)}` : '读取数据中'))
const active = computed(() => Boolean(month.value || carrier.value || origin.value || dest.value || hour.value !== ''))
const summary = computed(() => data.value?.summary || {})
const outlying = code => { const a = airports.value[code]; return !a || a.lon < -125 || a.lon > -66 || a.lat < 24 || a.lat > 50 }
const offmap = computed(() => (data.value?.airports || []).filter(a => outlying(a.origin)))
const airportCoverage = computed(() => { const rows = data.value?.airports || []; return `${rows.filter(a => airports.value[a.origin]).length}/${rows.length}` })
const colour = rate => rate == null ? '#8794a6' : rate > .35 ? '#f6b44d' : rate > .2 ? '#65b5ce' : '#38cfe8'

async function json(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(response.status === 503 ? '尚无已发布数据，请先运行数据处理流程。' : `查询失败（${response.status}），请重试。`)
  return response.json()
}
async function load() {
  controller?.abort()
  if (!ready.value || !['overview','routes'].includes(page.value)) return
  controller = new AbortController()
  const current = controller
  busy.value = true; error.value = ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries({ month: month.value, carrier: carrier.value, origin: origin.value, dest: page.value === 'routes' ? dest.value : '', hour: page.value === 'routes' ? hour.value : '' })) if (value !== '') params.set(key, value)
  const start = performance.now()
  try { const result = await json(`/api/dashboard?${params}`, current.signal); if (current === controller) { data.value = result; elapsed.value = Math.round(performance.now() - start) } }
  catch (e) { if (e.name !== 'AbortError' && current === controller) { data.value = null; error.value = e.message } }
  finally { if (current === controller) busy.value = false }
}
function reset() { stopPlayback(); month.value = ''; carrier.value = ''; origin.value = page.value === 'routes' ? 'ATL' : ''; dest.value = ''; hour.value = '' }
function changePage(value) {
  if (page.value === value) return
  stopPlayback()
  page.value = value
  dest.value = ''; hour.value = ''
  if (value === 'routes' && !origin.value) origin.value = choices.value.origin.includes('ATL') ? 'ATL' : choices.value.origin[0] || ''
  window.scrollTo({ top: 0 })
}
function exploreAirport(code) {
  origin.value = code
  changePage('routes')
}
function stopPlayback() { clearTimeout(timer); timer = null; playing.value = false }
const playing = ref(false)
async function playback() {
  if (playing.value) return stopPlayback()
  playing.value = true
  let next = hour.value === '' ? 0 : Number(hour.value)
  function tick() {
    if (!playing.value) return
    if (busy.value) { timer = setTimeout(tick, 300); return }
    hour.value = String(next)
    next = (next + 1) % 24
    if (playing.value) timer = setTimeout(tick, 1500)
  }
  tick()
}
function retry() { if (ready.value) load(); else window.location.reload() }
watch([page, month, carrier, origin, dest, hour], load)
onMounted(async () => {
  try {
    const [opts, points, map, sources] = await Promise.all([json('/api/filters'), json('/maps/airports.json'), json('/maps/us-contiguous.geojson'), json('/maps/sources.json')])
    choices.value = opts; airports.value = points; geography.value = sources
    echarts.registerMap('usa', map); ready.value = true; await load()
  } catch (e) { error.value = e.message; busy.value = false }
})
onBeforeUnmount(() => { controller?.abort(); stopPlayback() })

const base = { animationDuration: 250, textStyle: { color: '#9aaec8', fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif' }, tooltip: { trigger: 'axis', backgroundColor: '#172740', borderColor: '#324863', textStyle: { color: '#edf4ff' } }, grid: { left: 46, right: 20, top: 22, bottom: 28 } }
const axis = { axisLine: { lineStyle: { color: '#32435c' } }, axisTick: { show: false }, splitLine: { lineStyle: { color: '#23324a' } } }
const trend = computed(() => ({ ...base, xAxis: { ...axis, type: 'category', data: data.value?.trend.map(r => r.month.slice(5)) || [] }, yAxis: { ...axis, type: 'value', axisLabel: { formatter: '{value}%' } }, series: [{ type: 'line', smooth: .25, symbolSize: 7, data: data.value?.trend.map(r => r.delay_rate == null ? null : +(r.delay_rate * 100).toFixed(2)), lineStyle: { color: '#38cfe8', width: 3 }, itemStyle: { color: '#38cfe8' }, areaStyle: { color: '#38cfe8', opacity: .07 } }] }))
const ranking = computed(() => {
  const rows = (page.value === 'routes' ? data.value?.routes : data.value?.carriers)?.slice(0, 8).reverse() || []
  return { ...base, grid: { left: 66, right: 52, top: 12, bottom: 26 }, xAxis: { ...axis, type: 'value', axisLabel: { formatter: '{value}%' } }, yAxis: { ...axis, type: 'category', data: rows.map(r => page.value === 'routes' ? (origin.value ? r.dest : r.origin+' → '+r.dest) : r.carrier) }, series: [{ type: 'bar', barMaxWidth: 13, data: rows.map(r => ({ value: r.delay_rate == null ? null : +(r.delay_rate * 100).toFixed(1), itemStyle: { color: colour(r.delay_rate), borderRadius: [0, 3, 3, 0] } })), label: { show: true, position: 'right', formatter: '{c}%', color: '#d9e6f6', fontSize: 10 } }] }
})
const heat = computed(() => ({ ...base, grid: { left: 42, right: 20, top: 14, bottom: 54 }, tooltip: { ...base.tooltip, trigger: 'item', formatter: p => `${['一', '二', '三', '四', '五', '六', '日'][p.value[1]]} · ${p.value[0]}时<br/>延误率 ${p.value[2].toFixed(1)}% · ${num(p.value[3])} 个有效到达` }, xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, i) => i), axisLabel: { interval: 2, color: '#9aaec8' }, axisLine: { show: false }, axisTick: { show: false }, splitArea: { show: true, areaStyle: { color: '#142035' } } }, yAxis: { type: 'category', data: ['一', '二', '三', '四', '五', '六', '日'], axisLabel: { color: '#9aaec8' }, axisLine: { show: false }, axisTick: { show: false } }, visualMap: { dimension: 2, min: 0, max: 50, calculable: false, orient: 'horizontal', left: 'center', bottom: 0, itemHeight: 110, itemWidth: 8, text: ['≥50%', '0%'], textStyle: { color: '#9aaec8', fontSize: 10 }, inRange: { color: ['#133a52', '#287d9a', '#51c2d7', '#f6b44d'] } }, series: [{ type: 'heatmap', data: (data.value?.heatmap || []).filter(r => r.dep_hour != null && r.delay_rate != null).map(r => [r.dep_hour, r.weekday - 1, r.delay_rate * 100, r.eligible]), itemStyle: { borderColor: '#101a2a', borderWidth: 3 }, emphasis: { itemStyle: { borderColor: '#edf4ff', borderWidth: 1 } } }] }))
const hours = computed(() => ({ ...base, xAxis: { ...axis, type: 'category', data: (data.value?.hours || []).map(r => r.dep_hour ?? '未知') }, yAxis: { ...axis, type: 'value' }, series: [{ type: 'bar', barMaxWidth: 12, itemStyle: { color: '#38cfe8', opacity: .8, borderRadius: [3, 3, 0, 0] }, data: (data.value?.hours || []).map(r => r.planned) }] }))
const mapOption = computed(() => {
  let points = (data.value?.airports || []).filter(r => !outlying(r.origin)).map(r => ({ name: r.origin, value: [airports.value[r.origin].lon, airports.value[r.origin].lat, r.delay_rate == null ? -1 : r.delay_rate * 100, r.planned], itemStyle: { color: colour(r.delay_rate) } }))
  const routes = (data.value?.routes || []).filter(r => !outlying(r.origin) && !outlying(r.dest))
  if (page.value === 'routes') {
    const seen = new Set(points.map(r => r.name))
    for (const r of routes) if (!seen.has(r.dest)) { points.push({ name: r.dest, value: [airports.value[r.dest].lon, airports.value[r.dest].lat, (r.delay_rate == null ? -1 : r.delay_rate * 100), r.planned], itemStyle: { color: colour(r.delay_rate) } }); seen.add(r.dest) }
  }
  const max = Math.max(1, ...points.map(p => p.value[3]))
  return { ...base, tooltip: { ...base.tooltip, trigger: 'item', formatter: p => p.seriesType === 'scatter' ? `${p.name} · ${airportName(p.name)}<br/>${num(p.value[3])} 个航班 · 延误率 ${p.value[2] < 0 ? '—' : p.value[2].toFixed(1) + '%'}` : `${p.data.from} → ${p.data.to}<br/>${num(p.data.planned)} 个航班 · 延误率 ${pct(p.data.rate)}` }, geo: { map: 'usa', roam: true, left: '5%', right: '5%', top: '6%', bottom: '6%', itemStyle: { areaColor: '#192941', borderColor: '#3b5068', borderWidth: .7 }, emphasis: { disabled: true }, silent: false }, series: [{ type: 'lines', coordinateSystem: 'geo', z: 2, lineStyle: { color: '#38cfe8', opacity: .45, curveness: .15, width: 1.3 }, data: page.value === 'routes' ? routes.map(r => ({ from: r.origin, to: r.dest, planned: r.planned, rate: r.delay_rate, coords: [[airports.value[r.origin].lon, airports.value[r.origin].lat], [airports.value[r.dest].lon, airports.value[r.dest].lat]] })) : [] }, { type: 'scatter', coordinateSystem: 'geo', z: 3, symbolSize: value => 3 + Math.sqrt(value[3] / max) * 20, itemStyle: { borderColor: '#b7e9f3', borderWidth: .5, opacity: .87 }, label: { show: false, formatter: '{b}' }, emphasis: { label: { show: true, color: '#fff', position: 'top' }, scale: 1.25 }, data: points }] }
})
function selectRanking(p) {
  if (page.value === 'overview') carrier.value = p.name
  else if (p.name.includes(' → ')) [origin.value, dest.value] = p.name.split(' → ')
  else dest.value = p.name
}
function mapClick(p) { if (p.seriesType === 'scatter') { if (page.value === 'routes' && p.name !== origin.value) dest.value = p.name; else origin.value = origin.value === p.name && page.value === 'overview' ? '' : p.name } }
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="changePage('overview')"><span class="brand-mark">↗</span><span>AEROLENS<small>航空运行分析</small></span></a>
      <div class="nav-label">分析工作台</div>
      <nav aria-label="分析页面"><button :class="{selected:page==='overview'}" @click="changePage('overview')"><svg class="nav-icon" aria-hidden="true" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 10h18M10 10v11"/></svg>运行驾驶舱</button><button :class="{selected:page==='routes'}" @click="changePage('routes')"><svg class="nav-icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M4 18l7-12 9 12M4 18h16"/><circle cx="4" cy="18" r="2"/><circle cx="11" cy="6" r="2"/><circle cx="20" cy="18" r="2"/></svg>航线与时段</button><button :class="{selected:page==='risk'}" @click="changePage('risk')"><svg class="nav-icon" aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 3v4m9 5h-4"/></svg>风险复盘</button><button :class="{selected:page==='experiments'}" @click="changePage('experiments')"><svg class="nav-icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M4 21V3m0 18h17M9 17v-6m5 6V6m5 11V9"/></svg>实验验证</button></nav>
      <div class="sidebar-note"><span class="status-dot"></span> 官方历史数据<small>BTS · Reporting Carrier<br>2024 年上半年</small></div>
      <div class="sidebar-bottom">数据处理环境<small>HDFS · Spark Standalone<br>本地批处理与历史复盘</small></div>
    </aside>
    <main>
      <header class="page-header"><div><div class="eyebrow">BTS 历史档案 <span aria-hidden="true"> / </span> {{sections[page]}}</div><h1>{{titles[page][0]}}</h1><p>{{titles[page][1]}}</p></div><div class="archive-tag"><span class="status-dot"></span>历史档案分析<small>非实时航班跟踪</small></div></header>
      <section v-if="['overview','routes'].includes(page)" class="filter-bar" aria-label="数据筛选">
        <label>月份<select aria-label="月份" v-model="month"><option value="">全部月份</option><option v-for="v in choices.month" :key="v" :value="v">{{v}}</option></select></label>
        <label>航空公司<select aria-label="航空公司" v-model="carrier"><option value="">全部航司</option><option v-for="v in choices.carrier" :key="v">{{v}}</option></select></label>
        <label>出发机场<select aria-label="出发机场" v-model="origin"><option value="">全部机场</option><option v-for="v in choices.origin" :key="v" :value="v">{{v}} · {{airportName(v)}}</option></select></label>
        <label v-if="page==='routes'">到达机场<select aria-label="到达机场" v-model="dest"><option value="">全部目的地</option><option v-for="v in choices.dest" :key="v" :value="v">{{v}} · {{airportName(v)}}</option></select></label>
        <button class="reset" @click="reset" :disabled="!active">重置筛选 ↺</button><span class="filter-hint">{{scope}}<br><strong>{{num(summary.planned)}} 条计划航班</strong></span>
      </section>
      <div v-if="error && ['overview','routes'].includes(page)" class="error" role="alert">{{error}} <button @click="retry">重新加载</button></div>
      <div v-if="busy && ['overview','routes'].includes(page)" class="loading" role="status">正在读取所选范围的真实统计…</div>
      <div v-if="data && ['overview','routes'].includes(page)" class="content" :class="{pending:busy}">
        <OperationsBrief :data="data" :routes="page==='routes'" :city="airportName" @explore="exploreAirport"/>
        <section class="kpi-grid">
          <article class="kpi"><span>计划航班量</span><strong>{{num(summary.planned)}}<small>班</small></strong><p>当前筛选范围内的计划记录</p></article>
          <article class="kpi"><span>到达延误率 <em>≥15 分钟</em></span><strong class="cyan">{{pct(summary.delay_rate)}}</strong><p>{{num(summary.delayed)}} / {{num(summary.eligible)}} 个有效到达</p></article>
          <article class="kpi"><span>航班取消率</span><strong class="amber">{{pct(summary.cancellation_rate)}}</strong><p>{{num(summary.cancelled)}} 班取消 · 分母为计划航班</p></article>
          <article class="kpi"><span>平均到达延误</span><strong>{{summary.mean_arrival_delay==null?'—':summary.mean_arrival_delay.toFixed(1)}}<small>分钟</small></strong><p>包含提前到达的负值</p></article>
        </section>
        <section v-if="page==='routes'" class="playback panel"><div><h2>计划出发小时</h2><p>机场当地时间 · 历史聚合回放</p></div><button @click="playback" :aria-label="playing?'暂停小时回放':'播放小时回放'">{{playing?'Ⅱ 暂停':'▷ 回放'}}</button><input aria-label="计划出发小时" type="range" min="0" max="23" step="1" :value="hour===''?0:hour" @input="stopPlayback();hour=$event.target.value"><strong>{{hour===''?'全部时段':`${String(hour).padStart(2,'0')}:00—${String(hour).padStart(2,'0')}:59`}}</strong><button class="text-button" @click="stopPlayback();hour=''">全部</button></section>
        <div class="main-grid"><section class="panel map-panel"><div class="panel-heading"><div><h2>{{page==='overview'?'机场运行分布':'主要航线连接'}}</h2><p>{{page==='overview'?'气泡大小表示航班量 · 颜色表示历史延误率':'按航班量显示前 20 条 · 点击目的地联动筛选'}}</p></div><span class="pill">{{origin||'全美出发机场'}}</span></div><Chart v-if="ready" :option="mapOption" label="美国本土机场与历史延误分布地图，可点击机场筛选" @select="mapClick"/><div class="map-footer"><span><i class="cyan-dot"></i>≤20% <i class="mid-dot"></i>20—35% <i class="amber-dot"></i>&gt;35%</span><span>可拖动缩放 · 航线为示意连接</span></div></section>
          <section class="panel"><div class="panel-heading"><div><h2>{{page==='overview'?'航司延误比较':'主要目的地延误比较'}}</h2><p>按航班量选取前 8 项 · 点击条形联动筛选</p></div></div><Chart :option="ranking" label="主要航司或目的地的到达延误率比较" @select="selectRanking"/></section></div>
        <div class="lower-grid"><section class="panel"><div class="panel-heading"><div><h2>{{page==='overview'?'月度延误趋势':'计划出发小时分布'}}</h2><p>{{page==='overview'?'有效到达航班中的延误比例':'当前条件下各小时计划航班量'}}</p></div></div><Chart :option="page==='overview'?trend:hours" label="月份延误率趋势或计划起飞小时航班量" @select="p=>{if(page==='routes' && p.name!=='未知')hour=String(p.name)}"/></section><section class="panel"><div class="panel-heading"><div><h2>星期与时段热力图</h2><p>出发机场当地时间 · 空白表示无有效样本</p></div></div><Chart :option="heat" label="星期与计划出发小时的到达延误率热力图"/></section></div>
        <section class="detail-strip panel"><div><h2>{{origin?`${origin} · ${airportName(origin)}`:'数据范围与地图覆盖'}}</h2><p>{{origin?(airports[origin]?.name||'未匹配机场名称'):'全部统计保留非本土机场与无坐标机场'}}</p></div><div><span>坐标匹配</span><strong>{{airportCoverage}} 个出发机场</strong></div><div><span>备降航班</span><strong>{{num(summary.diverted)}} 班</strong></div><div><span>统计来源</span><strong>BTS / 2024</strong></div></section>
        <section v-if="offmap.length" class="offmap"><span>主图外机场（含阿拉斯加、夏威夷及属地）</span><button v-for="row in offmap" :key="row.origin" @click="origin=row.origin">{{row.origin}} <b>{{num(row.planned)}}</b> · {{pct(row.delay_rate)}}</button></section>
        <div v-if="summary.planned===0" class="empty">当前组合没有航班记录，请调整筛选条件。比例显示为“—”。</div>
      </div>
      <RiskPage v-if="page==='risk'"/><ExperimentsPage v-if="page==='experiments'"/>
      <footer><span>来源：BTS Reporting Carrier · 地图：Natural Earth / OurAirports <a href="/maps/sources.json" target="_blank" rel="noreferrer">来源与快照 ↗</a></span><span>历史统计关联不代表因果 · {{elapsed}} ms</span></footer>
    </main>
  </div>
</template>
