<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ data: { type: Object, required: true }, routes: Boolean, city: Function })
defineEmits(['explore'])
const count = value => value.toLocaleString('zh-CN')
const pct = value => (100 * value).toFixed(1) + '%'
const filters = computed(() => props.data.scope.filters)
const period = computed(() => {
  const months = props.data.scope.months
  return filters.value.month || [months[0], months.at(-1)].filter((v, i, a) => v && a.indexOf(v) === i).join(' — ')
})
const leaders = computed(() => props.data.airports.filter(row => row.delayed > 0)
  .slice().sort((a, b) => b.delayed - a.delayed || a.origin.localeCompare(b.origin)).slice(0, 3))
const leader = computed(() => leaders.value[0])

const slots = [
  { name: '凌晨', time: '00–05' }, { name: '上午', time: '06–11' },
  { name: '下午', time: '12–17' }, { name: '晚间', time: '18–23' }
]
const first = ref(1), second = ref(3)
const bands = computed(() => {
  const rows = slots.map(slot => ({ ...slot, eligible: 0, delayed: 0, rate: null }))
  for (const row of props.data.comparison_hours) {
    if (!Number.isInteger(row.dep_hour) || row.dep_hour < 0 || row.dep_hour > 23) continue
    const band = rows[Math.floor(row.dep_hour / 6)]
    band.eligible += row.eligible
    band.delayed += row.delayed
  }
  for (const band of rows) band.rate = band.eligible ? band.delayed / band.eligible : null
  return rows
})
const gap = computed(() => {
  const a = bands.value[first.value].rate, b = bands.value[second.value].rate
  return a === null || b === null ? null : Number(((b - a) * 100).toFixed(1))
})
const selectedBands = computed(() => [bands.value[first.value], bands.value[second.value]])
function setBand(side, value) {
  if (side === 0) first.value = Number(value)
  else second.value = Number(value)
}
</script>

<template>
  <section v-if="!routes" class="brief-sheet" aria-label="机场延误班次简报">
    <div class="brief-story">
      <div class="brief-kicker">机场运行简报 <span>{{period}}</span></div>
      <template v-if="leader">
        <h2><b>{{leader.origin}}</b> {{data.airports.length === 1 ? '出发航班延误' : '出发的延误航班最多'}}</h2>
        <p>{{city(leader.origin)}}出发的有效到达中，<strong>{{count(leader.delayed)}}</strong> 班延误，延误率为 <strong>{{pct(leader.delay_rate)}}</strong>。</p>
        <button class="brief-link" @click="$emit('explore',leader.origin)">探索 {{leader.origin}} 的航线与时段 <span aria-hidden="true">→</span></button>
      </template>
      <template v-else><h2>{{data.summary.eligible ? '本范围内没有延误航班' : '本范围内没有有效到达'}}</h2><p>可调整月份、航司或出发机场查看其他记录。</p></template>
    </div>
    <div class="brief-ledger" v-if="leaders.length">
      <div class="ledger-heading"><strong>出发机场</strong><span>延误班次 / 占所选范围延误总数</span></div>
      <button v-for="row in leaders" :key="row.origin" class="ledger-row" @click="$emit('explore',row.origin)" :aria-label="'探索 '+row.origin+' 的航线'">
        <b>{{row.origin}}</b><i aria-hidden="true"><u :style="{width:pct(row.delayed / leader.delayed)}"></u></i><strong>{{count(row.delayed)}}</strong><span>{{pct(row.delayed / data.summary.delayed)}}</span>
      </button>
    </div>
  </section>
  <section v-else class="brief-sheet route-brief" aria-label="航线时段对照">
    <div class="brief-story">
      <div class="brief-kicker">出发时段对照 <span>{{period}}</span></div>
      <h2><b>{{filters.origin || '全部机场'}} <small>→</small> {{filters.dest || '全部目的地'}}</b></h2>
      <p v-if="gap !== null" class="gap-line">{{slots[second].name}}较{{slots[first].name}}的延误率差为 <strong>{{gap > 0 ? '+' : ''}}{{gap.toFixed(1)}}</strong> 个百分点。</p>
      <p v-else>至少一个时段没有有效到达，无法计算差值。</p>
      <p class="brief-foot">同月份、航司和机场范围 · 当地计划出发小时。下方逐小时回放独立于此对照。</p>
    </div>
    <div class="brief-ledger">
      <div class="ledger-heading"><strong>比较时段</strong><span>延误 / 有效到达</span></div>
      <div v-for="(band,side) in selectedBands" :key="side" class="band-row">
        <select :aria-label="side===0?'基准时段':'对照时段'" :value="side===0?first:second" @change="setBand(side,$event.target.value)">
          <option v-for="(slot,index) in slots" :key="index" :value="index" :disabled="index===(side===0?second:first)">{{slot.name}} {{slot.time}} 时</option>
        </select>
        <strong>{{band.rate === null ? '—' : pct(band.rate)}}</strong>
        <span>{{count(band.delayed)}} / {{count(band.eligible)}}</span>
      </div>
    </div>
  </section>
</template>
