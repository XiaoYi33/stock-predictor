<script setup>
import Tip from './Tip.vue'

const props = defineProps({
  indicators: { type: Object, required: true },
  signals: { type: Array, default: () => [] },
})

const items = [
  { key: 'ma5', label: 'MA5', tip: '5日均线，反映最近一周的价格趋势' },
  { key: 'ma10', label: 'MA10', tip: '10日均线，反映两周左右的趋势' },
  { key: 'ma20', label: 'MA20', tip: '20日均线，中期趋势线，站上/跌破常被视为多空分界' },
  { key: 'ma60', label: 'MA60', tip: '60日均线，长期趋势线' },
  { key: 'macd_dif', label: 'MACD·DIF', tip: '差离值 = 12日EMA − 26日EMA，反映短期动能与长期动能的差距' },
  { key: 'macd_dea', label: 'MACD·DEA', tip: '信号线 = DIF 的 9 日 EMA，与 DIF 交叉形成金叉/死叉' },
  { key: 'macd_hist', label: 'MACD·柱', tip: '柱状值 = (DIF − DEA) × 2，红柱/绿柱反映动能强弱' },
  { key: 'rsi6', label: 'RSI6', tip: '6日相对强弱指标，>80 超买（短期回调风险），<20 超卖' },
  { key: 'rsi12', label: 'RSI12', tip: '12日相对强弱指标' },
  { key: 'rsi24', label: 'RSI24', tip: '24日相对强弱指标，反映中期强弱' },
  { key: 'kdj_k', label: 'KDJ·K', tip: '随机指标快线，K 上穿 D 为金叉（买入信号）' },
  { key: 'kdj_d', label: 'KDJ·D', tip: '随机指标慢线（信号线）' },
  { key: 'kdj_j', label: 'KDJ·J', tip: 'J 值 = 3K − 2D，>100 超买，<0 超卖，比 K/D 更灵敏' },
  { key: 'vol_ratio', label: '量比', tip: '今日成交量 / 过去5日均量，>1.5 放量，<0.5 缩量' },
]

function sentiCls(s) {
  return { positive: 'pos', negative: 'neg', neutral: 'neu' }[s] || 'neu'
}
</script>

<template>
  <div class="ind-wrap">
    <div class="grid">
      <Tip v-for="it in items" :key="it.key" :text="it.tip">
        <div class="item">
          <span class="label">{{ it.label }}</span>
          <span class="val">{{ indicators[it.key] }}</span>
        </div>
      </Tip>
    </div>

    <div class="right">
      <div v-if="signals.length" class="signals">
        <div class="sig-title">信号（悬停查看含义）</div>
        <Tip
          v-for="(s, i) in signals"
          :key="i"
          :text="'多空信号：红色=偏多，绿色=偏空，灰色=中性'"
        >
          <div class="sig">
            <span class="tag" :class="sentiCls(s.sentiment)">{{ s.label }}</span>
            <span class="txt">{{ s.text }}</span>
          </div>
        </Tip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ind-wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
  align-content: start;
}
.item {
  background: #f7f9fc; border-radius: 8px; padding: 8px 10px;
  display: flex; justify-content: space-between; font-size: 13px;
}
.item .label { color: var(--muted); }
.item .val { font-weight: 600; }
.signals { display: flex; flex-direction: column; gap: 6px; }
.sig-title { font-size: 12px; color: var(--muted); margin-bottom: 2px; }
.sig { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.tag {
  flex-shrink: 0; padding: 2px 8px; border-radius: 4px; font-size: 12px;
  font-weight: 600;
}
.tag.pos { background: #fdeef0; color: var(--up); }
.tag.neg { background: #e6f6ef; color: var(--down); }
.tag.neu { background: #eef1f5; color: var(--muted); }
.txt { color: var(--text); }
</style>
