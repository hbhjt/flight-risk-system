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
