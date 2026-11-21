<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ data: { type: Object, required: true }, routes: Boolean, city: Function })
defineEmits(['explore'])

const count = value => value.toLocaleString('zh-CN')
const pct = value => (100 * value).toFixed(1) + '%'
const rateTone = value => value == null ? '' : value > 0.35 ? 'tone-high' : value > 0.2 ? 'tone-mid' : 'tone-low'

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
const gapTone = computed(() => {
  if (gap.value === null || gap.value === 0) return ''
  if (gap.value >= 10) return 'tone-high'
  if (gap.value > 0) return 'tone-mid'
  return 'tone-low'
})
const selectedBands = computed(() => [bands.value[first.value], bands.value[second.value]])
const routeCityCaption = computed(() => {
  const originText = filters.value.origin ? props.city(filters.value.origin) : '全美出发机场'
  const destText = filters.value.dest ? props.city(filters.value.dest) : '全部到达目的地'
  return `${originText} → ${destText}`
})

function setBand(side, value) {
  if (side === 0) first.value = Number(value)
  else second.value = Number(value)
}
</script>

<template>
  <section v-if="!routes" class="cockpit-brief" aria-label="机场延误班次简报">
    <div class="cockpit-story">
      <div class="cockpit-kicker">
        <span class="kicker-badge">机场运行简报</span>
        <span class="kicker-period">{{ period }}</span>
      </div>
      <template v-if="leader">
        <div class="cockpit-headline-row">
          <h2>
            <b class="iata-tag">{{ leader.origin }}</b>
            {{ data.airports.length === 1 ? '出发航班延误' : '出发的延误航班最多' }}
          </h2>
          <button class="cockpit-cta" @click="$emit('explore', leader.origin)">
            <span>探索 {{ leader.origin }} 航线与时段</span>
            <svg class="inline-icon" aria-hidden="true" viewBox="0 0 16 16">
              <path d="M3 8h10m-4-4 4 4-4 4" />
            </svg>
          </button>
        </div>
        <p class="cockpit-summary">
          {{ city(leader.origin) }} 出发的有效到达中，共有
          <strong>{{ count(leader.delayed) }}</strong> 班延误，延误率为
          <strong :class="rateTone(leader.delay_rate)">{{ pct(leader.delay_rate) }}</strong>。
        </p>
      </template>
      <template v-else>
        <h2>{{ data.summary.eligible ? '本范围内没有延误航班' : '本范围内没有有效到达' }}</h2>
        <p class="cockpit-summary">可调整月份、航司或出发机场查看其他记录。</p>
      </template>
    </div>

    <div class="cockpit-ledger" v-if="leaders.length">
      <div class="cockpit-ledger-heading">
        <strong>延误班次 Top {{ leaders.length }} 出发机场</strong>
        <span>延误班次 · 占当前延误总数</span>
      </div>
      <div class="cockpit-ledger-list">
        <button
          v-for="(row, idx) in leaders"
          :key="row.origin"
          class="cockpit-ledger-row"
          @click="$emit('explore', row.origin)"
          :aria-label="'探索 ' + row.origin + ' 的航线'"
        >
          <span class="rank-index">0{{ idx + 1 }}</span>
          <b class="rank-code">{{ row.origin }}</b>
          <span class="rank-bar" aria-hidden="true">
            <span
              class="rank-bar-fill"
              :class="rateTone(row.delay_rate)"
              :style="{ width: pct(row.delayed / leader.delayed) }"
            ></span>
          </span>
          <strong class="rank-count">{{ count(row.delayed) }}</strong>
          <span class="rank-share">{{ pct(row.delayed / data.summary.delayed) }}</span>
          <svg class="row-arrow" aria-hidden="true" viewBox="0 0 16 16">
            <path d="M6 4l4 4-4 4" />
          </svg>
        </button>
      </div>
    </div>
  </section>

  <section v-else class="cockpit-brief route-brief" aria-label="航线时段对照">
    <div class="cockpit-story">
      <div class="cockpit-kicker">
        <span class="kicker-badge">全天时段对照</span>
        <span class="kicker-period">{{ period }}</span>
        <span class="kicker-scope">独立于下方逐小时回放</span>
      </div>
      <div class="route-title-row">
        <h2>
          <b class="iata-tag">{{ filters.origin || '全部机场' }}</b>
          <svg class="route-arrow-icon" aria-hidden="true" viewBox="0 0 16 16">
            <path d="M3 8h10m-4-4 4 4-4 4" />
          </svg>
          <b class="iata-tag">{{ filters.dest || '全部目的地' }}</b>
        </h2>
        <span class="route-city-sub">{{ routeCityCaption }}</span>
      </div>
      <p v-if="gap !== null" class="cockpit-summary route-gap-line">
        {{ slots[second].name }}较{{ slots[first].name }}的到达延误率差为
        <strong class="gap-value" :class="gapTone">{{ gap > 0 ? '+' : '' }}{{ gap.toFixed(1) }}</strong>
        个百分点（按当地计划出发小时汇总）。
      </p>
      <p v-else class="cockpit-summary">至少一个时段没有有效到达，无法计算延误率差值。</p>
    </div>

    <div class="cockpit-ledger route-compare-ledger">
      <div class="cockpit-ledger-heading">
        <strong>选择对比时段（全天样本）</strong>
        <span>延误率 · 延误 / 有效到达</span>
      </div>
      <div class="band-compare-list">
        <div v-for="(band, side) in selectedBands" :key="side" class="band-compare-row">
          <select
            :aria-label="side === 0 ? '基准时段' : '对照时段'"
            :value="side === 0 ? first : second"
            @change="setBand(side, $event.target.value)"
          >
            <option
              v-for="(slot, index) in slots"
              :key="index"
              :value="index"
              :disabled="index === (side === 0 ? second : first)"
            >
              {{ slot.name }} {{ slot.time }} 时
            </option>
          </select>
          <span class="band-bar" aria-hidden="true">
            <span
              class="band-bar-fill"
              :class="rateTone(band.rate)"
              :style="{ width: (band.rate ?? 0) * 100 + '%' }"
            ></span>
          </span>
          <strong class="band-rate" :class="rateTone(band.rate)">{{ band.rate === null ? '—' : pct(band.rate) }}</strong>
          <span class="band-frac">{{ count(band.delayed) }} / {{ count(band.eligible) }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
