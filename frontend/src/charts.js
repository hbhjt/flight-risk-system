import * as echarts from 'echarts/core'
import { BarChart, LineChart, ScatterChart, LinesChart, HeatmapChart } from 'echarts/charts'
import { LegendComponent, GridComponent, TooltipComponent, GeoComponent, VisualMapComponent, AriaComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([BarChart, LineChart, ScatterChart, LinesChart, HeatmapChart, LegendComponent, GridComponent, TooltipComponent, GeoComponent, VisualMapComponent, AriaComponent, CanvasRenderer])
export default echarts
