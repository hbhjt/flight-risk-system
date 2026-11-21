<script setup>
import { computed, onMounted, ref } from 'vue'
import Chart from './Chart.vue'
import ThresholdPanel from './ThresholdPanel.vue'
import { chartAxis, chartBase } from './charts.js'

const data = ref(null), error = ref(''), model = ref('B3'), dimension = ref('Origin')
const models = {
  B0: { name: '分层历史延误率', colour: '#a1afc1' }, B1: { name: '逻辑回归', colour: '#b0a1ef' },
  B2: { name: '基础随机森林', colour: '#2dd4bf' }, B3: { name: '随机森林＋历史特征', colour: '#38bdf8' }
}
const fmt = v => v == null ? '—' : Number(v).toFixed(4)
const count = v => v.toLocaleString('zh-CN')
const signed = (v, digits) => (v > 0 ? '+' : '') + v.toFixed(digits)
async function load() {
  error.value = ''
  try {
    const response = await fetch('/api/experiments')
    if (!response.ok) throw Error('实验结果暂不可用，请重试。')
    data.value = await response.json()
    model.value = data.value.metrics.selection.recommended_model
  } catch (e) { error.value = e.message }
}
onMounted(load)

const rows = computed(() => Object.entries(data.value?.metrics.test || {}).map(([id, v]) => ({ id, ...v })))
const current = computed(() => data.value.metrics.test[model.value])
const config = computed(() => data.value.metrics.configuration)
const engine = computed(() => data.value.engineering)
const stages = computed(() => [
  ['历史预热', config.value.warmup_month],
  ['训练', config.value.train_months[0] + ' — ' + config.value.train_months.at(-1)],
  ['验证', config.value.validation_month], ['留出测试', config.value.test_month]
])
const groups = computed(() => (data.value?.groups[dimension.value] || []).slice().sort((a, b) => b.n - a.n).slice(0, 10))
const pairedTrials = computed(() => {
  const trials = data.value.metrics.selection.trials
  return trials.filter(t => t.model === 'B2').flatMap(base => {
    const enhanced = trials.find(t => t.model === 'B3' && t.candidate === base.candidate)
    return enhanced ? [{ depth: base.parameters.maxDepth, base: base.validation.pr_auc, enhanced: enhanced.validation.pr_auc }] : []
  })
})

const unitAxis = { ...chartAxis, type: 'value', min: 0, max: 1, interval: 0.25, nameLocation: 'middle', nameTextStyle: { color: '#b4c5dc', fontSize: 11 } }
const pr = computed(() => ({
  ...chartBase,
  grid: { left: 59, right: 22, top: 46, bottom: 46 },
  xAxis: { ...unitAxis, name: '召回率 Recall', nameGap: 28 },
  yAxis: { ...unitAxis, name: '精确率 Precision', nameGap: 40 },
  legend: { top: 6, right: 16, textStyle: { color: '#cbd5e1', fontSize: 11 }, itemWidth: 18 },
  tooltip: { ...chartBase.tooltip, trigger: 'axis', confine: true },
  series: rows.value.map(r => ({
    name: r.id, type: 'line', showSymbol: false, data: r.pr_curve.map(p => [p.recall, p.precision]),
    lineStyle: { color: models[r.id].colour, width: r.id === model.value ? 3 : 1.5 },
    itemStyle: { color: models[r.id].colour }, z: r.id === model.value ? 4 : 2
  }))
}))
const calibration = computed(() => ({
  ...chartBase,
  grid: { left: 59, right: 22, top: 24, bottom: 46 },
  xAxis: { ...unitAxis, name: '分箱平均分数', nameGap: 28 },
  yAxis: { ...unitAxis, name: '实际延误率', nameGap: 40 },
  tooltip: { ...chartBase.tooltip, trigger: 'item', confine: true,
    formatter: p => '平均分数 ' + fmt(p.value[0]) + '<br>实际延误率 ' + fmt(p.value[1]) + '<br>样本 ' + count(p.value[2]) + ' 班' },
  series: [
    { name: '理想参考线', type: 'line', data: [[0, 0], [1, 1]], showSymbol: false, silent: true, lineStyle: { type: 'dashed', color: '#637c99' } },
    { name: model.value, type: 'line', data: current.value.reliability.filter(b => b.n).map(b => [b.mean_score, b.observed_rate, b.n]),
      symbolSize: 7, lineStyle: { color: models[model.value].colour }, itemStyle: { color: models[model.value].colour } }
  ]
}))

const confusionCells = [
  { key: 'tn', label: '正确排除', tone: 'tone-low' }, { key: 'fp', label: '误报', tone: 'tone-mid' },
  { key: 'fn', label: '漏报', tone: 'tone-high' }, { key: 'tp', label: '命中延误', tone: 'tone-low' }
]
</script>

<template>
  <div v-if="error" role="alert" class="error">{{ error }} <button @click="load">重试</button></div>
  <div v-else-if="!data" class="loading" role="status">正在读取已验证的实验结果…</div>
  <div v-else class="evaluation">
    <section class="study-strip" aria-label="测试样本与实验划分">
      <div class="study-sample"><span>有效测试航班</span><strong>{{ count(data.verification.test_rows) }}<small>班</small></strong></div>
      <dl class="study-periods"><div v-for="[label, period] in stages" :key="label"><dt>{{ label }}</dt><dd>{{ period }}</dd></div></dl>
    </section>
    <nav class="study-links" aria-label="实验章节">
      <a href="#model-evaluation">模型比较</a>
      <a v-if="data.verification.models[model]?.operating_points?.length" href="#operating-point">阈值推演</a>
      <a href="#error-breakdown">分组错误</a><a href="#storage-benchmark">存储实验</a>
    </nav>

    <section id="model-evaluation" class="panel experiment-table">
      <div class="panel-heading"><div><h2>统一测试集模型比较</h2><p>选择一行查看该模型的阈值、曲线和混淆矩阵。主指标为完整 PR 曲线的梯形积分面积。</p></div><span class="pill">{{ data.metrics.version }}</span></div>
      <div class="table-scroll"><table><thead><tr>
        <th scope="col">模型</th><th scope="col">PR-AUC ↑</th><th scope="col">ROC-AUC ↑</th><th scope="col">Precision</th><th scope="col">Recall</th><th scope="col">F1</th><th scope="col">Brier ↓</th><th scope="col">发布阈值</th>
      </tr></thead><tbody>
        <tr v-for="r in rows" :key="r.id" :class="{ highlight: r.id === model }" @click="model = r.id">
          <td><button class="model-choice" :aria-pressed="model === r.id" @click.stop="model = r.id">
            <i aria-hidden="true"></i><b>{{ r.id }}</b> {{ models[r.id].name }}<small v-if="r.id === data.metrics.selection.recommended_model">验证集推荐</small>
          </button></td>
          <td class="primary-metric">{{ fmt(r.pr_auc) }}</td><td>{{ fmt(r.roc_auc) }}</td><td>{{ fmt(r.precision) }}</td>
          <td>{{ fmt(r.recall) }}</td><td>{{ fmt(r.f1) }}</td><td>{{ fmt(r.brier) }}</td><td>{{ fmt(r.threshold) }}</td>
        </tr>
      </tbody></table></div>
      <div class="comparison-note"><b>B3 − B2 测试 PR-AUC <strong>{{ signed(data.metrics.b3_minus_b2_pr_auc, 6) }}</strong></b>
        <span>各自选优深度为 {{ data.metrics.selection.selected.B3.parameters.maxDepth }} 和 {{ data.metrics.selection.selected.B2.parameters.maxDepth }}，同深度对照见下方配对验证。</span></div>
    </section>

    <ThresholdPanel id="operating-point" :model="model" :current="current" :scenarios="data.verification.models[model]?.operating_points" />
    <div class="review-columns experiment-charts">
      <section class="panel"><div class="panel-heading"><div><h2>Precision–Recall 曲线</h2><p>曲线抽样显示，PR-AUC 使用全部点计算。</p></div></div>
        <Chart :option="pr" label="四个模型在六月测试集上的精确率与召回率曲线" /></section>
      <section class="panel"><div class="panel-heading"><div><h2>分数可靠性</h2><p>{{ config.reliability_bins }} 个等宽分箱 · 虚线表示平均分数等于实际延误率</p></div><span class="pill">{{ model }}</span></div>
        <Chart :option="calibration" :label="model + ' 分数与实际延误率的可靠性图'" /></section>
    </div>
    <div class="review-columns diagnostic-grid">
      <section class="panel confusion">
        <div class="panel-heading"><div><h2>发布阈值混淆矩阵</h2><p>行表示实际结果，列表示模型判断。</p></div><span class="pill">{{ model }} · {{ (current.threshold * 100).toFixed(1) }}%</span></div>
        <table class="matrix"><thead><tr><td></td><th scope="col">预测未延误</th><th scope="col">预测延误</th></tr></thead><tbody>
          <tr v-for="(label, i) in ['实际未延误', '实际延误']" :key="label"><th scope="row">{{ label }}</th>
            <td v-for="cell in confusionCells.slice(2*i, 2*i+2)" :key="cell.key"><small :class="cell.tone">{{ cell.label }} · {{ cell.key.toUpperCase() }}</small><strong>{{ count(current.confusion[cell.key]) }}</strong></td>
          </tr></tbody></table>
      </section>
      <section class="panel paired"><div class="panel-heading"><div><h2>同深度配对验证</h2><p>五月验证集 · B2 与 B3 使用相同训练样本、随机种子和搜索预算。</p></div></div>
        <div class="table-scroll"><table><thead><tr><th>树深度</th><th>B2 PR-AUC</th><th>B3 PR-AUC</th><th>B3 − B2</th></tr></thead><tbody>
          <tr v-for="row in pairedTrials" :key="row.depth"><td>{{ row.depth }}</td><td>{{ fmt(row.base) }}</td><td>{{ fmt(row.enhanced) }}</td><td>{{ signed(row.enhanced - row.base, 6) }}</td></tr>
        </tbody></table></div>
      </section>
    </div>
    <section id="error-breakdown" class="panel error-table"><div class="panel-heading"><div><h2>B3 分组错误分析</h2><p>按样本量列出前 10 组，小样本组的差异仅作描述。</p></div>
      <select aria-label="错误分析维度" v-model="dimension"><option value="Origin">出发机场</option><option value="dep_hour">计划小时</option><option value="support_band">航线历史支持数</option></select></div>
      <div class="table-scroll"><table><thead><tr><th>分组</th><th>样本量</th><th>误报 FP</th><th>漏报 FN</th><th>Brier</th></tr></thead><tbody>
        <tr v-for="g in groups" :key="g[dimension]"><td>{{ g[dimension] }}</td><td>{{ count(g.n) }}</td><td>{{ count(g.fp) }}</td><td>{{ count(g.fn) }}</td><td>{{ fmt(g.brier) }}</td></tr>
      </tbody></table></div>
    </section>
    <section id="storage-benchmark" class="panel engineering">
      <div class="panel-heading"><div><h2>CSV 与 Parquet 查询实验</h2><p v-if="engine">{{ count(engine.records) }} 条清洗记录 · 同字段、同分组查询 · 每种格式交替执行 {{ engine.repetitions }} 轮</p></div>
        <span v-if="engine" class="pill">查询结果{{ engine.consistent ? '一致' : '存在差异' }}</span></div>
      <div v-if="!engine" class="empty">尚无工程实验产物。</div>
      <template v-else>
        <div class="engineering-summary">
          <div><span>CSV / Parquet 耗时中位数</span><strong>{{ engine.medians.parquet > 0 ? (engine.medians.csv / engine.medians.parquet).toFixed(2) + '×' : '—' }}</strong></div>
          <div><span>Parquet 占 CSV 存储体积</span><strong>{{ engine.storage.csv.bytes > 0 ? (100 * engine.storage.parquet.bytes / engine.storage.csv.bytes).toFixed(2) + '%' : '—' }}</strong></div>
        </div>
        <div class="table-scroll"><table><thead><tr><th>格式</th><th>体积（MiB）</th><th v-for="n in engine.repetitions" :key="n">第 {{ n }} 轮（秒）</th><th>中位数（秒）</th></tr></thead><tbody>
          <tr v-for="f in ['csv','parquet']" :key="f"><td>{{ f.toUpperCase() }}</td><td>{{ (engine.storage[f].bytes / 1048576).toFixed(2) }}</td>
            <td v-for="r in engine.runs.filter(r => r.format === f)" :key="r.round">{{ r.seconds.toFixed(3) }}</td><td>{{ engine.medians[f].toFixed(3) }}</td></tr>
        </tbody></table></div>
        <div class="experiment-footnote"><p>每轮清除 Spark 显式缓存，保留操作系统与 HDFS 缓存。计时仅覆盖查询，体积按存储文件计算。</p>
          <p>Standalone · {{ engine.executor_cores }} 核 · 执行器 {{ engine.executor_memory }} / Driver {{ engine.driver_memory }} · {{ engine.partitions }} 分区 · {{ engine.application_id }}</p></div>
      </template>
    </section>
    <div class="experiment-footnote"><p>单一半年划分，随机种子 {{ config.seed }}。B3 的测试 PR-AUC 高于 B2，两者 F1 接近，B1 的 Brier 更低。跨年份表现与统计显著性仍待验证。</p>
      <p>历史回测按档案记录重建，未复原 BTS 当年的公开发布日期。独立复算通过 · BTS Reporting Carrier · {{ data.metrics.finished_at_utc }} · 配置 SHA256 {{ data.metrics.config_sha256.slice(0,16) }}…</p></div>
  </div>
</template>
