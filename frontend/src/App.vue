<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount, defineAsyncComponent } from 'vue'
import echarts, { chartBase as base, chartAxis as axis } from './charts.js'
import Chart from './Chart.vue'
import OperationsBrief from './OperationsBrief.vue'

const RiskPage = defineAsyncComponent(() => import('./RiskPage.vue'))
const ExperimentsPage = defineAsyncComponent(() => import('./ExperimentsPage.vue'))

const sections = { overview: '运行总览', routes: '航线探索', risk: '单班复盘', experiments: '方法验证' }
const titles = {
  overview: ['航空运行驾驶舱', '查看全美延误热点分布，从机场简报或图表联动进入细分分析。'],
  routes: ['航线与时段探索', '围绕出发机场查看航线风险分布，对比全天时段差异并逐小时回放。'],
  risk: ['延误风险与历史复盘', '查看已评分的真实航班，比较风险判断与实际结果。'],
  experiments: ['实验与系统验证', '追溯数据、模型对比与大数据工程实验。']
}

const carrierNames = {
  AA: '美航',
  DL: '达美',
  WN: '西南',
  UA: '美联航',
  OO: '天西',
  YX: '共和',
  NK: '精神',
  B6: '捷蓝',
  AS: '阿拉斯加',
  MQ: '特使',
  '9E': '奋进',
  OH: 'PSA',
  F9: '边疆',
  G4: '忠实',
  HA: '夏威夷'
}
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const hourTicks = ['00时', '06时', '12时', '18时', '23时']

const page = ref('overview'), month = ref(''), carrier = ref(''), origin = ref(''), dest = ref(''), hour = ref('')
const choices = ref({ month: [], carrier: [], origin: [], dest: [] }), airports = ref({}), data = ref(null)
const busy = ref(true), error = ref(''), ready = ref(false), geography = ref(null), elapsed = ref(0)
let controller, timer

const pct = v => v == null ? '—' : `${(v * 100).toFixed(1)}%`
const num = v => Number(v ?? 0).toLocaleString('zh-CN')
const airportName = code => airports.value[code]?.city || airports.value[code]?.name || code
const carrierLabel = code => carrierNames[code] ? `${code} · ${carrierNames[code]}` : code
const carrierShort = code => carrierNames[code] ? `${code} ${carrierNames[code]}` : code

const scope = computed(() => month.value || (data.value?.scope.months.length ? `${data.value.scope.months[0]} — ${data.value.scope.months.at(-1)}` : '读取数据中'))
const active = computed(() => Boolean(month.value || carrier.value || origin.value || dest.value || hour.value !== ''))
const summary = computed(() => data.value?.summary || {})
const outlying = code => { const a = airports.value[code]; return !a || a.lon < -125 || a.lon > -66 || a.lat < 24 || a.lat > 50 }
const offmap = computed(() => (data.value?.airports || []).filter(a => outlying(a.origin)))
const airportCoverage = computed(() => { const rows = data.value?.airports || []; return `${rows.filter(a => airports.value[a.origin]).length}/${rows.length}` })

const colour = rate => rate == null ? '#64748b' : rate > 0.35 ? '#fb7185' : rate > 0.2 ? '#f59e0b' : '#2dd4bf'
const rateTone = rate => rate == null ? '' : rate > 0.35 ? 'tone-high' : rate > 0.2 ? 'tone-mid' : 'tone-low'
const rateTag = rate => rate == null ? '' : rate > 0.35 ? '偏高' : rate > 0.2 ? '中等' : '平稳'

const mapPillText = computed(() => {
  if (page.value === 'routes') {
    if (origin.value && dest.value) return `${origin.value} → ${dest.value}`
    if (origin.value) return `${origin.value} · Top 20 航线`
    if (dest.value) return `全部出发机场 → ${dest.value}`
    return '全美主要航线'
  }
  return origin.value ? `${origin.value} · ${airportName(origin.value)}` : '全美出发机场'
})

const hourWindowText = computed(() => {
  if (hour.value === '') return '全部时段'
  const h = String(hour.value).padStart(2, '0')
  return `${h}:00—${h}:59`
})

const activeChips = computed(() => {
  const list = []
  if (month.value) list.push({ key: 'month', label: '月份', value: month.value, clear: () => { month.value = '' } })
  if (carrier.value) list.push({ key: 'carrier', label: '航司', value: carrierLabel(carrier.value), clear: () => { carrier.value = '' } })
  if (origin.value) list.push({ key: 'origin', label: '出发', value: `${origin.value} · ${airportName(origin.value)}`, clear: () => { origin.value = '' } })
  if (page.value === 'routes' && dest.value) list.push({ key: 'dest', label: '到达', value: `${dest.value} · ${airportName(dest.value)}`, clear: () => { dest.value = '' } })
  if (page.value === 'routes' && hour.value !== '') {
    list.push({ key: 'hour', label: '时段', value: hourWindowText.value, clear: () => { stopPlayback(); hour.value = '' } })
  }
  return list
})

async function json(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(response.status === 503 ? '尚无已发布数据，请先运行数据处理流程。' : `查询失败（${response.status}），请重试。`)
  return response.json()
}

async function load() {
  controller?.abort()
  if (!ready.value || !['overview', 'routes'].includes(page.value)) return
  controller = new AbortController()
  const current = controller
  busy.value = true; error.value = ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries({
    month: month.value,
    carrier: carrier.value,
    origin: origin.value,
    dest: page.value === 'routes' ? dest.value : '',
    hour: page.value === 'routes' ? hour.value : ''
  })) {
    if (value !== '') params.set(key, value)
  }
  const start = performance.now()
  try {
    const result = await json(`/api/dashboard?${params}`, current.signal)
    if (current === controller) {
      data.value = result
      elapsed.value = Math.round(performance.now() - start)
    }
  } catch (e) {
    if (e.name !== 'AbortError' && current === controller) {
      data.value = null
      error.value = e.message
    }
  } finally {
    if (current === controller) busy.value = false
  }
}

function reset() {
  stopPlayback()
  month.value = ''
  carrier.value = ''
  origin.value = page.value === 'routes' ? 'ATL' : ''
  dest.value = ''
  hour.value = ''
}

function changePage(value) {
  if (page.value === value) return
  stopPlayback()
  page.value = value
  dest.value = ''
  hour.value = ''
  if (value === 'routes' && !origin.value) origin.value = choices.value.origin.includes('ATL') ? 'ATL' : choices.value.origin[0] || ''
  window.scrollTo({ top: 0 })
}

function exploreAirport(code) {
  origin.value = code
  changePage('routes')
}

function stopPlayback() {
  clearTimeout(timer)
  timer = null
  playing.value = false
}

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

function retry() {
  if (ready.value) load()
  else window.location.reload()
}

watch([page, month, carrier, origin, dest, hour], load)

onMounted(async () => {
  try {
    const [opts, points, map, sources] = await Promise.all([
      json('/api/filters'),
      json('/maps/airports.json'),
      json('/maps/us-contiguous.geojson'),
      json('/maps/sources.json')
    ])
    choices.value = opts
    airports.value = points
    geography.value = sources
    echarts.registerMap('usa', map)
    ready.value = true
    await load()
  } catch (e) {
    error.value = e.message
    busy.value = false
  }
})

onBeforeUnmount(() => {
  controller?.abort()
  stopPlayback()
})

const trend = computed(() => {
  const rows = data.value?.trend || []
  const avg = summary.value.delay_rate == null ? null : +(summary.value.delay_rate * 100).toFixed(1)
  return {
    ...base,
    grid: { left: 48, right: 24, top: 28, bottom: 30 },
    tooltip: {
      ...base.tooltip,
      trigger: 'axis',
      axisPointer: { lineStyle: { color: '#38bdf8', type: 'dashed' } },
      formatter: params => {
        const p = params[0]
        const row = rows[p?.dataIndex]
        if (!row) return ''
        const rateText = row.delay_rate == null ? '—' : `${(row.delay_rate * 100).toFixed(1)}%`
        const detail = row.eligible != null ? `<br/><span style="color:#94a3b8">延误 ${num(row.delayed)} / 有效到达 ${num(row.eligible)}</span>` : ''
        return `<div style="font-weight:600;margin-bottom:4px">${row.month}</div>到达延误率 <b style="color:${colour(row.delay_rate)}">${rateText}</b>${detail}`
      }
    },
    xAxis: {
      ...axis,
      type: 'category',
      boundaryGap: false,
      data: rows.map(r => r.month.slice(5)),
      axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}月' }
    },
    yAxis: {
      ...axis,
      type: 'value',
      axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' }
    },
    series: [{
      type: 'line',
      smooth: 0.25,
      symbol: 'circle',
      symbolSize: 7,
      data: rows.map(r => r.delay_rate == null ? null : +(r.delay_rate * 100).toFixed(2)),
      lineStyle: { color: '#38bdf8', width: 2.5 },
      itemStyle: { color: '#38bdf8', borderColor: '#0f192b', borderWidth: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(56, 189, 248, 0.24)' },
            { offset: 1, color: 'rgba(56, 189, 248, 0.01)' }
          ]
        }
      },
      markLine: avg == null ? undefined : {
        silent: true,
        symbol: ['none', 'none'],
        lineStyle: { color: '#64748b', type: 'dashed', width: 1 },
        label: {
          show: true,
          position: 'insideEndTop',
          formatter: `范围均值 ${avg}%`,
          color: '#94a3b8',
          fontSize: 11
        },
        data: [{ yAxis: avg }]
      }
    }]
  }
})

const ranking = computed(() => {
  const isRoutes = page.value === 'routes'
  const rows = (isRoutes ? data.value?.routes : data.value?.carriers)?.slice(0, 8).reverse() || []
  return {
    ...base,
    grid: { left: isRoutes ? (origin.value ? 64 : 96) : 86, right: 54, top: 10, bottom: 26 },
    tooltip: {
      ...base.tooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(56, 189, 248, 0.07)' } },
      formatter: params => {
        const p = params[0]
        const d = p?.data
        if (!d) return ''
        const title = isRoutes
          ? (d.code.includes(' → ') ? d.code : `${d.code} · ${airportName(d.code)}`)
          : carrierLabel(d.code)
        const valText = d.value == null ? '—' : `${d.value}%`
        const volText = d.planned != null ? `<br/><span style="color:#94a3b8">计划航班 ${num(d.planned)} 班</span>` : ''
        return `<div style="font-weight:600;margin-bottom:4px">${title}</div>到达延误率 <b style="color:${d.itemStyle.color}">${valText}</b>${volText}`
      }
    },
    xAxis: {
      ...axis,
      type: 'value',
      axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' }
    },
    yAxis: {
      ...axis,
      type: 'category',
      splitLine: { show: false },
      data: rows.map(r => isRoutes ? (origin.value ? r.dest : `${r.origin} → ${r.dest}`) : r.carrier),
      axisLabel: {
        color: '#cbd5e1',
        fontSize: 12,
        fontFamily: isRoutes ? 'Cascadia Mono, Consolas, monospace' : undefined,
        formatter: val => isRoutes ? val : carrierShort(val)
      }
    },
    series: [{
      type: 'bar',
      barMaxWidth: 14,
      showBackground: true,
      backgroundStyle: { color: 'rgba(30, 48, 74, 0.45)', borderRadius: [0, 4, 4, 0] },
      data: rows.map(r => {
        const code = isRoutes ? (origin.value ? r.dest : `${r.origin} → ${r.dest}`) : r.carrier
        const dimmed = (!isRoutes && carrier.value && carrier.value !== r.carrier) || (isRoutes && dest.value && r.dest !== dest.value)
        return {
          value: r.delay_rate == null ? null : +(r.delay_rate * 100).toFixed(1),
          code,
          origin: r.origin,
          dest: r.dest,
          planned: r.planned,
          itemStyle: {
            color: colour(r.delay_rate),
            borderRadius: [0, 4, 4, 0],
            opacity: dimmed ? 0.35 : 0.95
          }
        }
      }),
      label: {
        show: true,
        position: 'right',
        formatter: '{c}%',
        color: '#e2e8f0',
        fontSize: 11,
        fontFamily: 'Cascadia Mono, Consolas, monospace'
      }
    }]
  }
})

const heat = computed(() => ({
  ...base,
  grid: { left: 46, right: 16, top: 14, bottom: 52 },
  tooltip: {
    ...base.tooltip,
    trigger: 'item',
    formatter: p => `<div style="font-weight:600;margin-bottom:4px">${weekdays[p.value[1]]} · ${String(p.value[0]).padStart(2, '0')}:00 时段</div>延误率 <b style="color:${colour(p.value[2] / 100)}">${p.value[2].toFixed(1)}%</b><br/><span style="color:#94a3b8">${num(p.value[3])} 个有效到达</span>`
  },
  xAxis: {
    type: 'category',
    data: Array.from({ length: 24 }, (_, i) => i),
    axisLabel: { interval: 2, color: '#94a3b8', fontSize: 11, formatter: '{value}时' },
    axisLine: { show: false },
    axisTick: { show: false },
    splitArea: { show: true, areaStyle: { color: ['rgba(20, 34, 56, 0.45)', 'rgba(15, 25, 43, 0.25)'] } }
  },
  yAxis: {
    type: 'category',
    data: weekdays,
    axisLabel: { color: '#cbd5e1', fontSize: 11 },
    axisLine: { show: false },
    axisTick: { show: false }
  },
  visualMap: {
    dimension: 2,
    min: 0,
    max: 50,
    calculable: false,
    orient: 'horizontal',
    left: 'center',
    bottom: 2,
    itemHeight: 140,
    itemWidth: 8,
    text: ['≥50%', '0%'],
    textStyle: { color: '#94a3b8', fontSize: 11 },
    inRange: { color: ['#103b47', '#238282', '#e8a235', '#f4647a'] }
  },
  series: [{
    type: 'heatmap',
    data: (data.value?.heatmap || []).filter(r => r.dep_hour != null && r.delay_rate != null).map(r => [r.dep_hour, r.weekday - 1, r.delay_rate * 100, r.eligible]),
    itemStyle: { borderColor: '#0f192b', borderWidth: 2, borderRadius: 2 },
    emphasis: { itemStyle: { borderColor: '#f1f5f9', borderWidth: 1.5 } }
  }]
}))

const hours = computed(() => {
  const byHour = new Map((data.value?.comparison_hours || []).map(row => [row.dep_hour, row]))
  const rows = Array.from({ length: 24 }, (_, dep_hour) =>
    byHour.get(dep_hour) ?? { dep_hour, planned: 0, delay_rate: null })
  if (byHour.has(null)) rows.push(byHour.get(null))
  return {
    ...base,
    grid: { left: 50, right: 16, top: 20, bottom: 28 },
    tooltip: {
      ...base.tooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(56, 189, 248, 0.08)' } },
      formatter: params => {
        const p = params[0]
        const row = rows[p?.dataIndex]
        if (!row) return ''
        const title = row.dep_hour == null ? '未知时段' : `${String(row.dep_hour).padStart(2, '0')}:00—${String(row.dep_hour).padStart(2, '0')}:59`
        const rateLine = `<br/>到达延误率 <b style="color:${colour(row.delay_rate)}">${pct(row.delay_rate)}</b>`
        return `<div style="font-weight:600;margin-bottom:4px">${title}</div>计划航班 <b>${num(row.planned)}</b> 班${rateLine}`
      }
    },
    xAxis: {
      ...axis,
      type: 'category',
      data: rows.map(r => r.dep_hour ?? '未知'),
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11,
        interval: 1,
        formatter: v => v === '未知' ? v : `${v}时`
      }
    },
    yAxis: {
      ...axis,
      type: 'value',
      axisLabel: { color: '#94a3b8', fontSize: 11 }
    },
    series: [{
      type: 'bar',
      barMaxWidth: 14,
      data: rows.map(r => {
        const isSelected = hour.value !== '' && String(r.dep_hour) === String(hour.value)
        const dimmed = hour.value !== '' && !isSelected
        return {
          value: r.planned,
          itemStyle: {
            color: isSelected ? '#7dd3fc' : '#38bdf8',
            opacity: dimmed ? 0.28 : 0.9,
            borderRadius: [3, 3, 0, 0]
          }
        }
      })
    }]
  }
})

const mapOption = computed(() => {
  const isRoutes = page.value === 'routes'
  let points = (data.value?.airports || []).filter(r => !outlying(r.origin)).map(r => ({
    name: r.origin,
    value: [airports.value[r.origin].lon, airports.value[r.origin].lat, r.delay_rate == null ? -1 : r.delay_rate * 100, r.planned],
    itemStyle: { color: colour(r.delay_rate) }
  }))
  const routes = (data.value?.routes || []).filter(r => !outlying(r.origin) && !outlying(r.dest))
  if (isRoutes) {
    const seen = new Set(points.map(r => r.name))
    for (const r of routes) {
      if (!seen.has(r.dest)) {
        points.push({
          name: r.dest,
          value: [airports.value[r.dest].lon, airports.value[r.dest].lat, r.delay_rate == null ? -1 : r.delay_rate * 100, r.planned],
          itemStyle: { color: colour(r.delay_rate) }
        })
        seen.add(r.dest)
      }
    }
  }
  const max = Math.max(1, ...points.map(p => p.value[3]))
  const maxRoutePlanned = Math.max(1, ...routes.map(r => r.planned || 0))
  const topHubs = new Set(points.slice().sort((a, b) => b.value[3] - a.value[3]).slice(0, isRoutes ? 5 : 6).map(p => p.name))
  if (origin.value) topHubs.add(origin.value)
  if (isRoutes && dest.value) topHubs.add(dest.value)

  const styledPoints = points.map(p => {
    const isPinned = p.name === origin.value || (isRoutes && p.name === dest.value)
    const showLabel = topHubs.has(p.name)
    const isDimmed = isRoutes && dest.value && p.name !== origin.value && p.name !== dest.value
    return {
      ...p,
      itemStyle: {
        ...p.itemStyle,
        borderColor: isPinned ? '#f8fafc' : 'rgba(226, 232, 240, 0.55)',
        borderWidth: isPinned ? 1.8 : 0.7,
        opacity: isDimmed ? 0.35 : (isPinned ? 1 : 0.88)
      },
      label: showLabel ? {
        show: true,
        formatter: '{b}',
        position: 'top',
        distance: 4,
        color: isPinned ? '#f8fafc' : '#cbd5e1',
        fontSize: isPinned ? 11 : 10,
        fontWeight: isPinned ? 700 : 500,
        fontFamily: 'Cascadia Mono, Consolas, monospace',
        backgroundColor: 'rgba(9, 16, 29, 0.78)',
        borderColor: isPinned ? 'rgba(56, 189, 248, 0.65)' : 'rgba(51, 79, 115, 0.45)',
        borderWidth: isPinned ? 1 : 0.5,
        borderRadius: 3,
        padding: [2, 4]
      } : { show: false }
    }
  })

  const focusPoints = []
  if (origin.value && !outlying(origin.value)) {
    const p = points.find(item => item.name === origin.value)
    if (p) focusPoints.push({ ...p, itemStyle: { ...p.itemStyle, borderColor: '#7dd3fc', borderWidth: 1.5, shadowBlur: 10, shadowColor: 'rgba(56, 189, 248, 0.55)' } })
  }
  if (isRoutes && dest.value && dest.value !== origin.value && !outlying(dest.value)) {
    const p = points.find(item => item.name === dest.value)
    if (p) focusPoints.push({ ...p, itemStyle: { color: p.itemStyle.color, shadowBlur: 10, shadowColor: p.itemStyle.color } })
  }

  return {
    ...base,
    tooltip: {
      ...base.tooltip,
      trigger: 'item',
      formatter: p => {
        if (p.seriesType === 'lines' && p.data) {
          return `<div style="font-weight:600;margin-bottom:4px">${p.data.from} → ${p.data.to}</div><span style="color:#94a3b8">${airportName(p.data.from)} → ${airportName(p.data.to)}</span><br/>计划航班 ${num(p.data.planned)} 班 · 延误率 <b style="color:${colour(p.data.rate)}">${pct(p.data.rate)}</b>`
        }
        if (p.seriesType === 'scatter' || p.seriesType === 'effectScatter') {
          return `<div style="font-weight:600;margin-bottom:4px">${p.name} · ${airportName(p.name)}</div>计划航班 ${num(p.value[3])} 班<br/>到达延误率 <b style="color:${colour(p.value[2] < 0 ? null : p.value[2] / 100)}">${p.value[2] < 0 ? '—' : p.value[2].toFixed(1) + '%'}</b>`
        }
        return ''
      }
    },
    geo: {
      map: 'usa',
      roam: true,
      zoom: 1,
      left: '4%',
      right: '4%',
      top: '6%',
      bottom: '5%',
      itemStyle: { areaColor: '#16253c', borderColor: '#2d4463', borderWidth: 0.8 },
      emphasis: { disabled: true },
      silent: false
    },
    series: [
      {
        type: 'lines',
        coordinateSystem: 'geo',
        z: 2,
        emphasis: { lineStyle: { width: 3, opacity: 1 } },
        data: isRoutes
          ? routes.map(r => {
              const isSelected = Boolean(dest.value && r.dest === dest.value)
              const hasDest = Boolean(dest.value)
              return {
                from: r.origin,
                to: r.dest,
                planned: r.planned,
                rate: r.delay_rate,
                coords: [
                  [airports.value[r.origin].lon, airports.value[r.origin].lat],
                  [airports.value[r.dest].lon, airports.value[r.dest].lat]
                ],
                lineStyle: {
                  color: colour(r.delay_rate),
                  width: isSelected ? 2.8 : +(1.1 + (r.planned / maxRoutePlanned) * 1.4).toFixed(2),
                  opacity: hasDest ? (isSelected ? 0.94 : 0.16) : 0.58,
                  curveness: 0.17
                }
              }
            })
          : []
      },
      {
        type: 'scatter',
        coordinateSystem: 'geo',
        z: 3,
        symbolSize: value => 4 + Math.sqrt(value[3] / max) * 20,
        emphasis: {
          label: {
            show: true,
            formatter: '{b}',
            color: '#fff',
            position: 'top',
            backgroundColor: 'rgba(15, 29, 51, 0.9)',
            padding: [2, 5],
            borderRadius: 3
          },
          scale: 1.25
        },
        data: styledPoints
      },
      {
        type: 'effectScatter',
        coordinateSystem: 'geo',
        z: 4,
        showEffectOn: 'render',
        rippleEffect: { brushType: 'stroke', scale: 2.8, period: 4.5 },
        symbolSize: value => 6 + Math.sqrt(value[3] / max) * 20,
        data: focusPoints
      }
    ]
  }
})

function selectRoute(from, to) {
  const selected = origin.value === from && dest.value === to
  origin.value = from
  dest.value = selected ? '' : to
}

function selectRanking(p) {
  if (page.value === 'overview') {
    const code = p.data.code
    carrier.value = carrier.value === code ? '' : code
  } else {
    selectRoute(p.data.origin, p.data.dest)
  }
}

function selectHour(p) {
  if (page.value !== 'routes' || p.name === '未知') return
  stopPlayback()
  const next = String(p.name)
  hour.value = hour.value === next ? '' : next
}

function mapClick(p) {
  if (p.seriesType === 'scatter' || p.seriesType === 'effectScatter') {
    if (page.value === 'routes' && p.name !== origin.value) {
      dest.value = dest.value === p.name ? '' : p.name
    } else {
      origin.value = origin.value === p.name && page.value === 'overview' ? '' : p.name
    }
  } else if (p.seriesType === 'lines' && page.value === 'routes' && p.data?.to) {
    selectRoute(p.data.from, p.data.to)
  }
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="changePage('overview')">
        <span class="brand-mark">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 19L19 5M10 5h9v9" />
          </svg>
        </span>
        <span>AEROLENS<small>航空运行分析</small></span>
      </a>
      <div class="nav-label">分析工作台</div>
      <nav aria-label="分析页面">
        <button :class="{ selected: page === 'overview' }" @click="changePage('overview')">
          <svg class="nav-icon" aria-hidden="true" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 10h18M10 10v11" /></svg>
          运行驾驶舱
        </button>
        <button :class="{ selected: page === 'routes' }" @click="changePage('routes')">
          <svg class="nav-icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M4 18l7-12 9 12M4 18h16" /><circle cx="4" cy="18" r="2" /><circle cx="11" cy="6" r="2" /><circle cx="20" cy="18" r="2" /></svg>
          航线与时段
        </button>
        <button :class="{ selected: page === 'risk' }" @click="changePage('risk')">
          <svg class="nav-icon" aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><path d="M12 3v4m9 5h-4" /></svg>
          风险复盘
        </button>
        <button :class="{ selected: page === 'experiments' }" @click="changePage('experiments')">
          <svg class="nav-icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M4 21V3m0 18h17M9 17v-6m5 6V6m5 11V9" /></svg>
          实验验证
        </button>
      </nav>
      <div class="sidebar-note">
        <span class="status-dot"></span>官方历史数据
        <small>BTS · Reporting Carrier<br>2024 年上半年</small>
      </div>
      <div class="sidebar-bottom">
        数据处理环境
        <small>HDFS · Spark Standalone<br>本地批处理与历史复盘</small>
      </div>
    </aside>

    <main>
      <header class="page-header">
        <div>
          <div class="eyebrow">BTS 历史档案 <span aria-hidden="true">/</span> {{ sections[page] }}</div>
          <h1>{{ titles[page][0] }}</h1>
          <p>{{ titles[page][1] }}</p>
        </div>
        <div class="archive-tag">
          <span class="status-dot"></span>历史档案分析
          <small>非实时航班跟踪</small>
        </div>
      </header>

      <section v-if="['overview', 'routes'].includes(page)" class="filter-panel" aria-label="数据筛选">
        <div class="filter-bar">
          <label>
            <span>月份</span>
            <select aria-label="月份" v-model="month">
              <option value="">全部月份</option>
              <option v-for="v in choices.month" :key="v" :value="v">{{ v }}</option>
            </select>
          </label>
          <label>
            <span>航空公司</span>
            <select aria-label="航空公司" v-model="carrier">
              <option value="">全部航司</option>
              <option v-for="v in choices.carrier" :key="v" :value="v">{{ carrierLabel(v) }}</option>
            </select>
          </label>
          <label class="airport-filter">
            <span>出发机场</span>
            <select aria-label="出发机场" v-model="origin">
              <option value="">全部机场</option>
              <option v-for="v in choices.origin" :key="v" :value="v">{{ v }} · {{ airportName(v) }}</option>
            </select>
          </label>
          <label v-if="page === 'routes'" class="airport-filter">
            <span>到达机场</span>
            <select aria-label="到达机场" v-model="dest">
              <option value="">全部目的地</option>
              <option v-for="v in choices.dest" :key="v" :value="v">{{ v }} · {{ airportName(v) }}</option>
            </select>
          </label>
          <button class="reset" @click="reset" :disabled="!active">
            <svg class="inline-icon" aria-hidden="true" viewBox="0 0 16 16">
              <path d="M3 8a5 5 0 1 0 1.4-3.5L3 6m0-3v3h3" />
            </svg>
            重置筛选
          </button>
          <span class="filter-hint">
            <span>{{ scope }}</span>
            <strong>{{ num(summary.planned) }} 条计划航班</strong>
          </span>
        </div>

        <div v-if="activeChips.length" class="active-chips" aria-label="当前生效筛选条件">
          <span class="chips-title">已选条件</span>
          <button v-for="chip in activeChips" :key="chip.key" class="filter-chip" @click="chip.clear" :aria-label="'移除筛选：' + chip.label + ' ' + chip.value">
            <span class="chip-k">{{ chip.label }}</span>
            <b>{{ chip.value }}</b>
            <svg class="chip-close" aria-hidden="true" viewBox="0 0 12 12">
              <path d="M3 3l6 6M9 3L3 9" />
            </svg>
          </button>
        </div>
      </section>

      <div v-if="error && ['overview', 'routes'].includes(page)" class="error" role="alert">
        {{ error }} <button @click="retry">重新加载</button>
      </div>
      <div v-if="busy && ['overview', 'routes'].includes(page)" class="loading" role="status">
        正在读取所选范围的真实统计…
      </div>

      <div v-if="data && ['overview', 'routes'].includes(page)" class="content" :class="{ pending: busy }">
        <section class="kpi-grid">
          <article class="kpi">
            <div class="kpi-head"><span>计划航班量</span></div>
            <strong>{{ num(summary.planned) }}<small>班</small></strong>
            <p>当前筛选范围内的计划记录</p>
          </article>
          <article class="kpi kpi-accent" :class="rateTone(summary.delay_rate)">
            <div class="kpi-head">
              <span>到达延误率 <em>≥15 分钟</em></span>
              <span v-if="rateTag(summary.delay_rate)" class="kpi-badge" :class="rateTone(summary.delay_rate)">{{ rateTag(summary.delay_rate) }}</span>
            </div>
            <strong :class="rateTone(summary.delay_rate)">{{ pct(summary.delay_rate) }}</strong>
            <p>{{ num(summary.delayed) }} / {{ num(summary.eligible) }} 个有效到达</p>
          </article>
          <article class="kpi">
            <div class="kpi-head"><span>航班取消率</span></div>
            <strong class="amber">{{ pct(summary.cancellation_rate) }}</strong>
            <p>{{ num(summary.cancelled) }} 班取消 · 分母为计划航班</p>
          </article>
          <article class="kpi">
            <div class="kpi-head"><span>平均到达延误</span></div>
            <strong>{{ summary.mean_arrival_delay == null ? '—' : summary.mean_arrival_delay.toFixed(1) }}<small>分钟</small></strong>
            <p>包含提前到达的负值</p>
          </article>
        </section>

        <OperationsBrief :data="data" :routes="page === 'routes'" :city="airportName" @explore="exploreAirport" />

        <section v-if="page === 'routes'" class="playback panel" aria-label="计划出发小时回放">
          <div class="playback-meta">
            <h2>逐小时回放</h2>
            <p>当地时间 · 联动地图、排行与 KPI</p>
          </div>
          <button class="playback-toggle" :class="{ active: playing }" @click="playback" :aria-label="playing ? '暂停小时回放' : '播放小时回放'">
            <svg v-if="!playing" class="inline-icon" aria-hidden="true" viewBox="0 0 16 16"><path d="M5 3.5l8 4.5-8 4.5z" fill="currentColor" stroke="none" /></svg>
            <svg v-else class="inline-icon" aria-hidden="true" viewBox="0 0 16 16"><path d="M5 3.5h2.2v9H5zm4.8 0H12v9H9.8z" fill="currentColor" stroke="none" /></svg>
            {{ playing ? '暂停' : '回放' }}
          </button>
          <div class="playback-track">
            <input aria-label="计划出发小时" type="range" min="0" max="23" step="1" :value="hour === '' ? 0 : hour" @input="stopPlayback(); hour = $event.target.value">
            <div class="playback-ticks" aria-hidden="true">
              <span v-for="tick in hourTicks" :key="tick">{{ tick }}</span>
            </div>
          </div>
          <span class="playback-badge" :class="{ active: hour !== '' }">{{ hourWindowText }}</span>
          <button class="text-button" :disabled="hour === ''" @click="stopPlayback(); hour = ''">恢复全天</button>
        </section>

        <div class="main-grid">
          <section class="panel map-panel">
            <div class="panel-heading">
              <div>
                <h2>{{ page === 'overview' ? '机场运行分布' : '主要航线连接' }}</h2>
                <p>{{ page === 'overview' ? '气泡大小表示航班量 · 颜色表示历史延误率 · 点击机场筛选' : '按航班量展示前 20 条航线 · 弧线颜色表示延误率 · 点击航线或目的地筛选' }}</p>
              </div>
              <span class="pill">{{ mapPillText }}</span>
            </div>
            <Chart v-if="ready" :option="mapOption" label="美国本土机场与历史延误分布地图，可点击机场筛选" @select="mapClick" />
            <div class="map-footer">
              <span class="legend-group">
                <span><i class="dot-low"></i>≤20% 平稳</span>
                <span><i class="dot-mid"></i>20—35% 中等</span>
                <span><i class="dot-high"></i>&gt;35% 偏高</span>
              </span>
              <span class="map-tip">{{ page === 'overview' ? '滚轮缩放 · 默认标注 Top 6 枢纽' : '滚轮缩放 · 弧线为示意连接，线宽反映航班量' }}</span>
            </div>
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <h2>{{ page === 'overview' ? '航司延误比较' : '主要目的地延误比较' }}</h2>
                <p>按航班量选取前 8 项 · 点击条形联动筛选</p>
              </div>
              <span v-if="page === 'overview' && carrier" class="pill">{{ carrierShort(carrier) }}</span>
              <span v-else-if="page === 'routes' && dest" class="pill">{{ dest }} · {{ airportName(dest) }}</span>
            </div>
            <Chart :option="ranking" label="主要航司或目的地的到达延误率比较" @select="selectRanking" />
          </section>
        </div>

        <div class="lower-grid">
          <section class="panel">
            <div class="panel-heading">
              <div>
                <h2>{{ page === 'overview' ? '月度延误趋势' : '计划出发小时分布' }}</h2>
                <p>{{ page === 'overview' ? '有效到达航班中的延误比例 · 虚线为当前范围均值' : '全天各小时计划航班量 · 点击柱形切换时段，再次点击恢复全天' }}</p>
              </div>
              <span v-if="page === 'routes' && hour !== ''" class="pill">{{ hourWindowText }}</span>
            </div>
            <Chart :option="page === 'overview' ? trend : hours" label="月份延误率趋势或计划起飞小时航班量" @select="selectHour" />
          </section>

          <section class="panel">
            <div class="panel-heading">
              <div>
                <h2>星期与时段热力图</h2>
                <p>出发机场当地时间 · 空白表示无有效样本</p>
              </div>
            </div>
            <Chart :option="heat" label="星期与计划出发小时的到达延误率热力图" />
          </section>
        </div>

        <section class="panel coverage-panel">
          <div class="coverage-top">
            <div class="coverage-title">
              <h2>{{ origin ? (page === 'routes' && dest ? `${origin} → ${dest} · ${airportName(origin)}至${airportName(dest)}` : `${origin} · ${airportName(origin)}`) : '数据范围与地图覆盖' }}</h2>
              <p>{{ origin ? (airports[origin]?.name || '未匹配机场名称') : '全部指标均保留阿拉斯加、夏威夷、属地及无坐标机场记录' }}</p>
            </div>
            <div class="coverage-metrics">
              <div><span>坐标匹配</span><strong>{{ airportCoverage }} 个出发机场</strong></div>
              <div><span>备降航班</span><strong>{{ num(summary.diverted) }} 班</strong></div>
              <div><span>统计来源</span><strong>BTS / 2024</strong></div>
            </div>
          </div>
          <div v-if="offmap.length" class="coverage-offmap">
            <span class="offmap-label">主图外机场（可点击筛选）</span>
            <div class="offmap-list">
              <button
                v-for="row in offmap"
                :key="row.origin"
                :class="{ selected: origin === row.origin }"
                @click="origin = origin === row.origin && page === 'overview' ? '' : row.origin"
              >
                <b>{{ row.origin }}</b>
                <span>{{ num(row.planned) }} 班</span>
                <em :class="rateTone(row.delay_rate)">{{ pct(row.delay_rate) }}</em>
              </button>
            </div>
          </div>
        </section>

        <div v-if="summary.planned === 0" class="empty">当前组合没有航班记录，请调整筛选条件。比例显示为“—”。</div>
      </div>

      <RiskPage v-if="page === 'risk'" />
      <ExperimentsPage v-if="page === 'experiments'" />

      <footer>
        <span>来源：BTS Reporting Carrier · 地图：Natural Earth / OurAirports <a href="/maps/sources.json" target="_blank" rel="noreferrer">来源与快照 ↗</a></span>
        <span>历史统计关联不代表因果 · {{ elapsed }} ms</span>
      </footer>
    </main>
  </div>
</template>
