import * as echarts from 'echarts/core'
import {
  BarChart,
  LineChart,
  ScatterChart,
  EffectScatterChart,
  LinesChart,
  HeatmapChart
} from 'echarts/charts'
import {
  LegendComponent,
  GridComponent,
  TooltipComponent,
  GeoComponent,
  VisualMapComponent,
  AriaComponent,
  MarkLineComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  ScatterChart,
  EffectScatterChart,
  LinesChart,
  HeatmapChart,
  LegendComponent,
  GridComponent,
  TooltipComponent,
  GeoComponent,
  VisualMapComponent,
  AriaComponent,
  MarkLineComponent,
  CanvasRenderer
])

export default echarts

export const chartBase = {
  animationDuration: 280,
  animationEasing: 'cubicOut',
  textStyle: { color: '#94a3b8', fontFamily: 'Inter, Segoe UI, PingFang SC, Microsoft YaHei, sans-serif' },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#0f1d33',
    borderColor: '#334f73',
    borderWidth: 1,
    padding: [10, 12],
    textStyle: { color: '#edf4ff', fontSize: 12 },
    extraCssText: 'box-shadow: 0 10px 26px rgba(3, 8, 18, 0.55); border-radius: 6px;'
  },
  grid: { left: 48, right: 20, top: 24, bottom: 28 }
}

export const chartAxis = {
  axisLine: { lineStyle: { color: '#24354d' } },
  axisTick: { show: false },
  axisLabel: { color: '#94a3b8', fontSize: 11 },
  splitLine: { lineStyle: { color: '#1b2a40', type: 'dashed' } }
}
