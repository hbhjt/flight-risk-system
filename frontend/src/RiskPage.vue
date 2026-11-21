<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import Chart from './Chart.vue'
import { chartAxis, chartBase } from './charts.js'

const origins = ref([]), destinations = ref([]), carriers = ref([]), dates = ref([]), flights = ref([])
const origin = ref('ATL'), dest = ref('LAX'), carrier = ref(''), date = ref(''), selected = ref('')
const record = ref(null), busy = ref(false), error = ref(''), scorePanel = ref(null)
const examples = ref([]), examplesError = ref(''), casePage = ref(0)
const pageSize = 4
const casePages = computed(() => Math.ceil(examples.value.length / pageSize))
const visibleCases = computed(() => examples.value.slice(casePage.value * pageSize, (casePage.value + 1) * pageSize))
let serial = 0
let retry = () => options()

const pct = v => v == null ? '—' : (v * 100).toFixed(1) + '%'
const count = v => v == null ? '—' : v.toLocaleString('zh-CN')
const hhmm = v => String(v).padStart(4, '0').replace(/(..)(..)/, '$1:$2')
const choose = (values, value) => values.includes(value) ? value : values[0] || ''

async function api(path, params) {
  const url = '/api/risk/' + path + (params ? '?' + new URLSearchParams(params) : '')
  const response = await fetch(url)
  if (!response.ok) throw Error(response.status === 503 ? '评分产物暂不可用。' : '航班查询失败（' + response.status + '）')
  return response.json()
}

async function run(action, repeat, keepRecord = false) {
  const request = ++serial
  busy.value = true
  error.value = ''
  if (!keepRecord) record.value = null
  try {
    await action(request)
  } catch (e) {
    if (request === serial) {
      error.value = e.message
      retry = repeat
    }
  } finally {
    if (request === serial) busy.value = false
  }
}

async function readFlight(request, reveal = false) {
  const flight = await api('flight/' + selected.value, { reveal })
  if (request === serial) record.value = flight
}

async function listFlights(request, preferred) {
  if (!origin.value || !dest.value || !carrier.value || !date.value) {
    flights.value = []
    selected.value = ''
    return
  }
  const result = await api('flights', { origin: origin.value, dest: dest.value, carrier: carrier.value, date: date.value })
  if (request !== serial) return
  flights.value = result.flights
  if (preferred && !flights.value.some(f => f.flight_id === preferred.flight_id)) flights.value = [...flights.value, preferred]
  selected.value = preferred?.flight_id || flights.value[0]?.flight_id || ''
  if (preferred) record.value = preferred
  else if (selected.value) await readFlight(request)
}

async function loadOptions(request, preferred) {
  const all = await api('options')
  if (request !== serial) return
  origins.value = all.origins
  origin.value = choose(origins.value, origin.value)
  const from = origin.value ? await api('options', { origin: origin.value }) : { destinations: [] }
  if (request !== serial) return
  destinations.value = from.destinations
  dest.value = choose(destinations.value, dest.value)
  const route = dest.value ? await api('options', { origin: origin.value, dest: dest.value }) : { carriers: [] }
  if (request !== serial) return
  carriers.value = route.carriers
  carrier.value = choose(carriers.value, carrier.value)
  const airline = carrier.value ? await api('options', { origin: origin.value, dest: dest.value, carrier: carrier.value }) : { dates: [] }
  if (request !== serial) return
  dates.value = airline.dates
  date.value = choose(dates.value, date.value)
  await listFlights(request, preferred)
}

function options() { return run(request => loadOptions(request), options) }
function search() { return run(request => listFlights(request), search) }
function inspect(reveal = false) { return run(request => readFlight(request, reveal), () => inspect(reveal), reveal) }

function example(id) {
  return run(async request => {
    const flight = await api('flight/' + id, { reveal: false })
    if (request !== serial) return
    origin.value = flight.Origin
    dest.value = flight.Dest
    carrier.value = flight.Reporting_Airline
    date.value = flight.FlightDate
    await loadOptions(request, flight)
    await nextTick()
    if (request === serial) scorePanel.value?.focus()
  }, () => example(id))
}

async function loadExamples() {
  examplesError.value = ''
  try { examples.value = (await api('examples')).cases }
  catch (e) { examplesError.value = e.message }
}

onMounted(() => { options(); loadExamples() })

const outcome = computed(() => {
  const flight = record.value
  if (flight?.actual_delayed == null) return null
  if (flight.actual_delayed) return flight.predicted_delayed ? { title: '命中延误', code: 'TP', tone: 'tone-low' } : { title: '漏报延误', code: 'FN', tone: 'tone-high' }
  return flight.predicted_delayed ? { title: '误报延误', code: 'FP', tone: 'tone-mid' } : { title: '正确排除', code: 'TN', tone: 'tone-low' }
})

const modelLabels = { B0: '分层历史率', B1: '逻辑回归', B2: '基础森林', B3: '增强森林' }
const comparison = computed(() => {
  const flight = record.value
  const models = Object.keys(modelLabels)
  return {
    ...chartBase,
    grid: { left: 100, right: 56, top: 14, bottom: 34 },
    tooltip: { ...chartBase.tooltip, trigger: 'item', valueFormatter: value => value == null ? '—' : value + '%' },
    xAxis: { ...chartAxis, type: 'value', min: 0, max: 100, interval: 25, axisLabel: { ...chartAxis.axisLabel, formatter: '{value}%' } },
    yAxis: { ...chartAxis, type: 'category', inverse: true, splitLine: { show: false }, data: models.map(m => m + '  ' + modelLabels[m]) },
    series: [{
      name: '模型分数', type: 'bar', barMaxWidth: 16, showBackground: true,
      backgroundStyle: { color: '#192a44', borderRadius: 4 },
      label: { show: true, position: 'right', formatter: '{c}%', color: '#e2e8f0' },
      data: models.map(m => ({
        value: flight?.['score_' + m] == null ? null : +(flight['score_' + m] * 100).toFixed(1),
        itemStyle: { color: m === flight?.model ? '#38bdf8' : '#527498', borderRadius: [0, 4, 4, 0] }
      }))
    }]
  }
})
</script>

<template>
  <section class="filter-panel" aria-label="风险复盘条件">
    <div class="filter-bar">
      <label>出发机场<select v-model="origin" :disabled="busy || !origins.length" @change="options()"><option v-for="v in origins" :key="v">{{ v }}</option></select></label>
      <label>到达机场<select v-model="dest" :disabled="busy || !destinations.length" @change="options()"><option v-for="v in destinations" :key="v">{{ v }}</option></select></label>
      <label>航司<select v-model="carrier" :disabled="busy || !carriers.length" @change="options()"><option v-for="v in carriers" :key="v">{{ v }}</option></select></label>
      <label>出发日期<select v-model="date" :disabled="busy || !dates.length" @change="search()"><option v-for="v in dates" :key="v">{{ v }}</option></select></label>
      <label>计划时刻<select v-model="selected" :disabled="busy || !flights.length" @change="inspect()">
        <option v-for="f in flights" :key="f.flight_id" :value="f.flight_id">{{ hhmm(f.CRSDepTime) }} · {{ f.Reporting_Airline }}{{ f.Flight_Number_Reporting_Airline }}</option>
      </select></label>
    </div>
  </section>
  <div v-if="busy && !record" class="loading" role="status">正在读取历史评分…</div>
  <div v-if="error" class="error" role="alert">{{ error }} <button @click="retry()">重试</button></div>
  <div v-if="record" class="risk-content">
    <div class="review-columns">
      <section ref="scorePanel" tabindex="-1" class="panel score-panel" aria-label="航班风险判断">
        <div class="flight-heading">
          <div><h2><span>{{ record.Origin }}</span><span aria-hidden="true" class="flight-arrow">→</span><span>{{ record.Dest }}</span></h2>
            <p>{{ record.Reporting_Airline }}{{ record.Flight_Number_Reporting_Airline }} · {{ record.FlightDate }} · 当地 {{ hhmm(record.CRSDepTime) }} 计划出发</p></div>
          <span class="pill">{{ record.model }} · {{ record.version }}</span>
        </div>
        <div class="score-readings">
          <div><span>模型估计分数</span><strong class="risk-number">{{ pct(record.score) }}</strong></div>
          <div><span>发布阈值</span><strong>{{ pct(record.threshold) }}</strong></div>
          <span class="prediction" :class="{ flagged: record.predicted_delayed }">{{ record.predicted_delayed ? '发出延误预警' : '低于预警阈值' }}</span>
        </div>
        <div class="score-track" aria-hidden="true"><i :style="{width: pct(record.score)}"></i><b :style="{left: pct(record.threshold)}"></b></div>
        <p class="score-context">六月已评分航班 · 限未取消、未备降的记录。模型分数未经额外概率校准。</p>
        <div class="outcome" aria-live="polite">
          <div><h3>实际到达结果</h3><p>{{ outcome ? (record.actual_delayed ? '实际延误达到 15 分钟' : '实际延误低于 15 分钟') : '查看预测后，可展开历史记录进行核对。' }}</p></div>
          <strong v-if="outcome" class="outcome-tag" :class="outcome.tone">{{ outcome.title }} · {{ outcome.code }}</strong>
          <button v-else class="action" :disabled="busy" @click="inspect(true)">{{ busy ? '读取中…' : '展开实际结果' }}</button>
        </div>
      </section>
      <section class="panel model-comparison"><div class="panel-heading">
        <div><h2>同一航班的模型分数</h2><p>四个模型独立评分，亮色条为本次判断使用的模型。</p></div>
      </div><Chart :option="comparison" label="同一航班四个模型的风险分数" /></section>
    </div>
    <div class="kpi-grid history-evidence">
      <article class="kpi"><span>航线历史延误率</span><strong>{{ pct(record.historical_reference) }}</strong><p>平滑估计 · {{ count(record.hist_route_count) }} 个有效样本</p></article>
      <article class="kpi"><span>出发机场历史样本</span><strong>{{ count(record.hist_origin_count) }}<small>班</small></strong><p>{{ record.Origin }} 历史延误率 {{ pct(record.hist_origin_rate) }}</p></article>
      <article class="kpi"><span>航司历史样本</span><strong>{{ count(record.hist_carrier_count) }}<small>班</small></strong><p>{{ record.Reporting_Airline }} 历史延误率 {{ pct(record.hist_carrier_rate) }}</p></article>
      <article class="kpi"><span>计划飞行时长</span><strong>{{ count(record.CRSElapsedTime) }}<small>分钟</small></strong><p>航线距离 {{ count(record.Distance) }} 英里</p></article>
    </div>
    <p class="history-period">历史特征统计至 {{ record.history_cutoff_month }}，样本量表示历史支持数。</p>
  </div>
  <div v-else-if="!busy && !error" class="empty">当前条件没有已评分记录，请调整筛选。</div>
  <section class="panel examples">
    <div class="panel-heading"><div><h2>真实航班示例</h2><p>按固定规则从四类判断结果中选取，案例分布不代表总体。</p></div>
      <div v-if="casePages > 1" class="case-pager">
        <button :disabled="casePage === 0" aria-label="上一页案例" @click="casePage--">上一页</button>
        <span aria-live="polite">{{ casePage + 1 }} / {{ casePages }}</span>
        <button :disabled="casePage + 1 >= casePages" aria-label="下一页案例" @click="casePage++">下一页</button>
      </div>
    </div>
    <div v-if="examplesError" class="error" role="alert">{{ examplesError }} <button @click="loadExamples">重试案例</button></div>
    <div class="case-list"><button v-for="row in visibleCases" :key="row.flight_id" :aria-pressed="record?.flight_id === row.flight_id" @click="example(row.flight_id)">
      <strong>{{ row.origin }} → {{ row.dest }}</strong><small>{{ row.date }}</small>
    </button></div>
  </section>
</template>
