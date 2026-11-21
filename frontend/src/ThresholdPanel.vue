<script setup>
import { computed, ref, watch } from 'vue'
const props = defineProps({ model: String, current: Object, scenarios: Array })
const setting = ref('published')
watch(() => props.model, () => { setting.value = 'published' })
const matrix = computed(() => props.scenarios?.find(row => row.threshold === setting.value) || props.current.confusion)
const measures = [
  { title: '发出预警', value: m => m.tp + m.fp },
  { title: '命中延误', value: m => m.tp },
  { title: '误报', value: m => m.fp },
  { title: '漏报', value: m => m.fn }
]
const pct = v => (100 * v).toFixed(1) + '%'
const count = v => v.toLocaleString('zh-CN')
function changeFromPublished(value) {
  const diff = value(matrix.value) - value(props.current.confusion)
  return diff > 0 ? '+' + count(diff) : count(diff)
}
</script>

<template>
  <section v-if="scenarios?.length" class="threshold-panel panel" aria-label="预警阈值推演">
    <div class="threshold-heading">
      <div><h2>预警阈值推演 <span class="pill">{{ model }}</span></h2><p>在同一批六月航班上切换阈值，观察命中、误报和漏报的变化。</p></div>
      <div class="threshold-options" role="group" aria-label="演示阈值">
        <button class="published-option" :aria-pressed="setting==='published'" @click="setting='published'">发布值 {{pct(current.threshold)}}</button>
        <button v-for="row in scenarios" :key="row.threshold" :aria-pressed="setting===row.threshold" @click="setting=row.threshold">{{pct(row.threshold)}}</button>
      </div>
    </div>
    <div class="threshold-numbers" aria-live="polite">
      <div v-for="measure in measures" :key="measure.title"><span>{{measure.title}}</span><strong>{{count(measure.value(matrix))}}</strong><small>{{setting==='published'?'发布阈值下的班次':'较发布值 '+changeFromPublished(measure.value)+' 班'}}</small></div>
    </div>
    <p>三档演示值用于观察误报与漏报的取舍。正式指标和单班复盘始终使用五月验证集选定的发布阈值。</p>
  </section>
</template>
