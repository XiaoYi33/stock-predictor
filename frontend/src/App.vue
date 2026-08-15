<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import StockSearch from './components/StockSearch.vue'
import PredictionCards from './components/PredictionCards.vue'
import IndicatorPanel from './components/IndicatorPanel.vue'
import MarketAnalysis from './components/MarketAnalysis.vue'
import KLineChart from './components/KLineChart.vue'
import { getStock, getAnalysis, getBacktest, getKline, getModelStatus } from './api.js'

const code = ref('')
const stock = ref(null)
const kline = ref(null)
const analysis = ref(null)
const backtest = ref(null)
const error = ref('')
const loading = ref(false)
const modelStatus = ref(null)
const pollTimer = ref(null)

// ---------- 自选股 (localStorage) ----------
const WL_KEY = 'stock-predictor-watchlist'
const watchlist = ref([])

function loadWatchlist() {
  try {
    watchlist.value = JSON.parse(localStorage.getItem(WL_KEY) || '[]')
  } catch { watchlist.value = [] }
}

function saveWatchlist() {
  localStorage.setItem(WL_KEY, JSON.stringify(watchlist.value))
}

const inWatchlist = computed(() =>
  watchlist.value.some((w) => w.code === code.value))

const modelLabel = computed(() => {
  const mi = modelStatus.value && modelStatus.value.model_info
  if (!mi || !mi.base_models) return ''
  const names = mi.base_models.map((b) => b.name).join('+')
  return `堆叠(${names}) → ${mi.meta_model}`
})

function toggleWatch() {
  const cur = stock.value
  if (!cur) return
  if (inWatchlist.value) {
    watchlist.value = watchlist.value.filter((w) => w.code !== code.value)
  } else {
    watchlist.value.push({ code: cur.code, name: cur.name, accuracy: null })
    refreshWatchAccuracy()
  }
  saveWatchlist()
}

function removeWatch(w) {
  watchlist.value = watchlist.value.filter((x) => x.code !== w.code)
  saveWatchlist()
}

async function refreshWatchAccuracy() {
  await Promise.all(watchlist.value.map(async (w) => {
    try {
      const b = await getBacktest(w.code)
      w.accuracy = b.accuracy
    } catch { w.accuracy = null }
  }))
}

function fmtAcc(v) {
  return v == null ? '--' : v + '%'
}
function accCls(v) {
  if (v == null) return 'acc-none'
  return v >= 60 ? 'acc-good' : v < 40 ? 'acc-bad' : 'acc-mid'
}
function dirCls(d) { return d === 'up' ? 'up' : 'down' }
function retCls(r) { return r > 0 ? 'up' : r < 0 ? 'down' : 'neu' }

// ---------- 数据加载 ----------
async function load(codeStr) {
  if (!codeStr) return
  error.value = ''
  loading.value = true
  code.value = codeStr
  try {
    const s = await getStock(codeStr)
    stock.value = s
    kline.value = await getKline(codeStr, 250)
    getAnalysis(codeStr).then((a) => (analysis.value = a))
      .catch(() => (analysis.value = null))
    getBacktest(codeStr).then((b) => {
      backtest.value = b
      const w = watchlist.value.find((x) => x.code === codeStr)
      if (w) w.accuracy = b.accuracy
    }).catch(() => (backtest.value = null))
  } catch (e) {
    stock.value = null
    kline.value = null
    analysis.value = null
    backtest.value = null
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// ---------- 模型状态 ----------
async function checkModel() {
  try {
    modelStatus.value = await getModelStatus()
  } catch { /* ignore */ }
}

onMounted(async () => {
  loadWatchlist()
  refreshWatchAccuracy()
  await checkModel()
  pollTimer.value = setInterval(async () => {
    if (modelStatus.value && (modelStatus.value.training || !modelStatus.value.trained)) {
      await checkModel()
    }
  }, 5000)
})

function fmtPrice(v) {
  return v == null ? '-' : Number(v).toFixed(2)
}
</script>

<template>
  <div class="page">
    <header>
      <h1>A股涨跌预测</h1>
      <StockSearch v-model="code" @select="(s) => load(s.code)" />
      <div v-if="modelStatus" class="model-status" :class="modelStatus.trained ? 'ok' : 'busy'">
        {{
          modelStatus.training
            ? `模型训练中: ${modelStatus.message}`
            : modelStatus.trained
              ? `模型: ${modelLabel || modelStatus.message}`
              : `模型: ${modelStatus.message}`
        }}
      </div>
    </header>

    <div class="layout">
      <!-- 左侧自选栏 -->
      <aside class="sidebar">
        <div class="sidebar-title">
          自选股
          <span class="hint">近30日准确率</span>
        </div>
        <div class="watch-list">
          <div
            v-for="w in watchlist"
            :key="w.code"
            class="watch-item"
            :class="{ active: w.code === code }"
            @click="load(w.code)"
          >
            <div class="w-top">
              <span class="w-name">{{ w.name }}</span>
              <span class="w-del" title="移除" @click.stop="removeWatch(w)">×</span>
            </div>
            <div class="w-bottom">
              <span class="w-code">{{ w.code }}</span>
              <span class="w-acc" :class="accCls(w.accuracy)">{{ fmtAcc(w.accuracy) }}</span>
            </div>
          </div>
          <div v-if="!watchlist.length" class="watch-empty">
            暂无自选<br />搜索股票后点「加入自选」
          </div>
        </div>
      </aside>

      <!-- 主内容 -->
      <main class="content">
        <div v-if="error" class="error">{{ error }}</div>
        <div v-if="loading && !stock" class="loading">加载中...</div>

        <template v-if="stock">
          <!-- 实时行情头 -->
          <section class="quote">
            <div class="left">
              <div class="stock-name">{{ stock.name }} <span class="stock-code">{{ stock.code }}</span></div>
              <div class="last-date">净值日期: {{ stock.last_date }}</div>
            </div>
            <div class="price-area" v-if="stock.realtime">
              <div class="price" :class="stock.realtime.change_pct >= 0 ? 'up' : 'down'">
                {{ fmtPrice(stock.realtime.price) }}
              </div>
              <div class="chg" :class="stock.realtime.change_pct >= 0 ? 'up' : 'down'">
                {{ stock.realtime.change_pct >= 0 ? '+' : '' }}{{ stock.realtime.change_pct }}%
                ({{ stock.realtime.change >= 0 ? '+' : '' }}{{ stock.realtime.change }})
              </div>
            </div>
            <button class="watch-btn" :class="{ added: inWatchlist }" @click="toggleWatch">
              {{ inWatchlist ? '★ 移出自选' : '☆ 加入自选' }}
            </button>
          </section>

          <!-- 昨日预估 vs 今日实际 -->
          <div v-if="backtest && backtest.last" class="bt-strip">
            <span class="bt-item">
              近30日准确率 <b :class="accCls(backtest.accuracy)">{{ backtest.accuracy }}%</b>
              <span class="bt-dim">({{ backtest.total }}天)</span>
            </span>
            <span class="bt-sep">|</span>
            <span class="bt-item">
              昨日({{ backtest.last.date }})预估
              <b :class="dirCls(backtest.last.pred)">{{ backtest.last.pred === 'up' ? '看涨' : '看跌' }}</b>
              {{ backtest.last.prob_up }}%
            </span>
            <span class="bt-arrow">→</span>
            <span class="bt-item">
              今日({{ backtest.last.target_date }})实际
              <b :class="retCls(backtest.last.ret)">{{ backtest.last.ret > 0 ? '+' : '' }}{{ backtest.last.ret }}%</b>
            </span>
            <span class="bt-hit" :class="backtest.last.correct ? 'hit' : 'miss'">
              {{ backtest.last.correct ? '✓ 命中' : '✗ 未命中' }}
            </span>
          </div>

          <!-- 预测卡片 -->
          <section class="panel">
            <h2>涨跌预测 <span class="hint">(多模型堆叠 · 悬停任意数字查看说明)</span></h2>
            <PredictionCards v-if="stock.predictions" :predictions="stock.predictions" />
          </section>

          <!-- 指标 + 信号 -->
          <section class="panel">
            <h2>技术指标 & 信号 <span class="hint">(悬停查看含义)</span></h2>
            <IndicatorPanel :indicators="stock.indicators" :signals="stock.signals" />
          </section>

          <!-- 市场与板块分析 -->
          <section class="panel">
            <h2>市场与板块分析</h2>
            <MarketAnalysis :data="analysis" />
          </section>

          <!-- K线 -->
          <section class="panel">
            <h2>K线走势</h2>
            <KLineChart :key="stock.code" :code="stock.code" :data="kline" />
          </section>
        </template>

        <template v-else-if="!loading">
          <div class="placeholder">
            <p>输入股票代码, 开始预测</p>
            <p class="tip">例如: 300750 · 600519 · 000858</p>
          </div>
        </template>
      </main>
    </div>

    <footer>
      免责声明: 预测结果基于历史数据的技术指标与统计模型, 仅作参考, 不构成投资建议。股市有风险, 入市需谨慎。
    </footer>
  </div>
</template>

<style scoped>
.page { max-width: 1280px; margin: 0 auto; padding: 20px 16px 40px; }
header { display: flex; align-items: center; gap: 20px; margin-bottom: 14px; flex-wrap: wrap; }
h1 { font-size: 20px; white-space: nowrap; }
.model-status { font-size: 12px; padding: 4px 10px; border-radius: 20px; }
.model-status.busy { background: #fff7e6; color: #b8860b; }
.model-status.ok { background: #e6f6ef; color: var(--down); }

.layout { display: flex; gap: 16px; align-items: flex-start; }

/* 左侧自选栏 */
.sidebar {
  width: 190px; flex-shrink: 0;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 14px 12px;
  position: sticky; top: 16px;
}
.sidebar-title {
  font-size: 14px; font-weight: 700; margin-bottom: 10px;
  display: flex; align-items: baseline; justify-content: space-between;
}
.hint { font-size: 11px; color: var(--muted); font-weight: 400; }
.watch-list { display: flex; flex-direction: column; gap: 8px; max-height: 70vh; overflow-y: auto; }
.watch-item {
  border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px;
  cursor: pointer; background: #fafbfd;
}
.watch-item:hover { border-color: #c7d6f5; }
.watch-item.active { background: #e8f0fe; border-color: #3b82f6; }
.w-top { display: flex; justify-content: space-between; align-items: center; }
.w-name { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.w-del { color: var(--muted); font-size: 15px; padding: 0 2px; }
.w-del:hover { color: var(--up); }
.w-bottom { display: flex; justify-content: space-between; align-items: center; margin-top: 3px; }
.w-code { font-size: 11px; color: var(--muted); }
.w-acc { font-size: 12px; font-weight: 700; }
.acc-good { color: var(--down); }
.acc-bad { color: var(--up); }
.acc-mid { color: #d97706; }
.acc-none { color: var(--muted); }
.watch-empty { text-align: center; color: var(--muted); font-size: 12px; padding: 20px 4px; line-height: 1.7; }

/* 主内容 */
.content { flex: 1; min-width: 0; }

.error { background: #fdeef0; color: var(--up); padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; }
.loading { text-align: center; padding: 60px; color: var(--muted); }

.quote {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px 20px; display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
}
.stock-name { font-size: 20px; font-weight: 700; }
.stock-code { color: var(--muted); font-weight: 400; font-size: 15px; margin-left: 6px; }
.last-date { color: var(--muted); font-size: 12px; margin-top: 4px; }
.price { font-size: 34px; font-weight: 700; }
.chg { font-size: 16px; margin-top: 2px; }
.up { color: var(--up); }
.down { color: var(--down); }
.neu { color: var(--text); }
.watch-btn {
  padding: 8px 14px; border: 1px solid #3b82f6; color: #3b82f6;
  background: #fff; border-radius: 8px; cursor: pointer; font-size: 13px;
}
.watch-btn:hover { background: #f0f4ff; }
.watch-btn.added { background: #3b82f6; color: #fff; border-color: #3b82f6; }

/* 昨日预估条 */
.bt-strip {
  background: #f7f9fc; border: 1px solid var(--border); border-radius: 10px;
  padding: 9px 14px; margin-bottom: 14px; font-size: 13px;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.bt-item { color: #444; }
.bt-item b { font-size: 14px; }
.bt-dim { color: var(--muted); font-size: 12px; }
.bt-sep { color: #d5dae2; }
.bt-arrow { color: #aab; }
.bt-hit { padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.bt-hit.hit { background: #e6f6ef; color: var(--down); }
.bt-hit.miss { background: #fdeef0; color: var(--up); }

.panel { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; margin-bottom: 16px; }
.panel h2 { font-size: 15px; margin-bottom: 14px; color: var(--text); }
.hint { font-size: 12px; color: var(--muted); font-weight: 400; }

.placeholder { text-align: center; padding: 120px 0; color: var(--muted); }
.placeholder p { font-size: 16px; margin-bottom: 8px; }
.placeholder .tip { font-size: 13px; }

footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 20px; }
</style>
