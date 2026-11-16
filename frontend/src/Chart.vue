<script setup>
import { onMounted, onBeforeUnmount, watch, ref } from 'vue'
import echarts from './charts.js'
const props = defineProps({ option: Object, label: String })
const emit = defineEmits(['select'])
const root = ref(null)
let chart, observer
onMounted(() => {
  chart = echarts.init(root.value, null, { renderer: 'canvas' })
  chart.setOption(props.option, true)
  chart.on('click', p => emit('select', p))
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(root.value)
})
watch(() => props.option, value => chart?.setOption(value, true), { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>
<template><div ref="root" class="chart" role="img" :aria-label="label"></div></template>
