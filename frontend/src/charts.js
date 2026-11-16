import * as echarts from 'echarts/core'
import { BarChart, LineChart, ScatterChart, LinesChart, HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, GeoComponent, VisualMapComponent, AriaComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([BarChart, LineChart, ScatterChart, LinesChart, HeatmapChart, GridComponent, TooltipComponent, GeoComponent, VisualMapComponent, AriaComponent, CanvasRenderer])
export default echarts
