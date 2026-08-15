<script setup>
import Tip from './Tip.vue'

const props = defineProps({
  predictions: { type: Object, required: true },
})

const ORDER = ['1', '5', '20']

function pct(v) {
  return v.toFixed(1) + '%'
}

const CONF_TEXT = {
  high: '高：模型判断非常明确',
  medium: '中：模型有一定倾向',
  low: '低：概率接近50%，不确定性大',
}
</script>

<template>
  <div class="cards">
    <div
      v-for="h in ORDER"
      :key="h"
      class="card"
      :class="props.predictions[h].direction"
    >
      <Tip :text="`预测未来 ${h === '1' ? '1' : h === '5' ? '5' : '20'} 个交易日的涨跌方向，基于 27 个技术指标特征（均线/MACD/RSI/KDJ/量能/波动率等）`">
        <div class="horizon">{{ props.predictions[h].horizon }}</div>
      </Tip>
      <Tip :text="props.predictions[h].direction === 'up' ? '模型综合判断：上涨概率较大' : '模型综合判断：下跌概率较大'">
        <div class="dir">
          {{ props.predictions[h].direction === 'up' ? '看涨' : '看跌' }}
        </div>
      </Tip>
      <Tip text="模型预测该股上涨的概率（0~100%）。超过50%视为看涨，越接近100%越强">
        <div class="prob">{{ pct(props.predictions[h].prob_up) }}</div>
      </Tip>
      <Tip text="概率条：红色填充表示看涨，比例即上涨概率。灰色部分为剩余概率空间">
        <div class="bar">
          <div class="fill" :style="{ width: pct(props.predictions[h].prob_up) }"></div>
        </div>
      </Tip>
      <Tip :text="CONF_TEXT[props.predictions[h].confidence]">
        <div class="conf">
          置信度:
          <b :class="props.predictions[h].confidence">
            {{ { high: '高', medium: '中', low: '低' }[props.predictions[h].confidence] }}
          </b>
        </div>
      </Tip>
    </div>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px; text-align: center;
}
.card.up { border-top: 3px solid var(--up); }
.card.down { border-top: 3px solid var(--down); }
.horizon { color: var(--muted); font-size: 13px; }
.dir { font-size: 20px; font-weight: 700; margin: 6px 0 2px; }
.card.up .dir, .card.up .prob { color: var(--up); }
.card.down .dir, .card.down .prob { color: var(--down); }
.prob { font-size: 26px; font-weight: 700; }
.bar {
  height: 8px; background: #eef1f5; border-radius: 4px;
  overflow: hidden; margin: 8px 0; cursor: help;
}
.fill { height: 100%; background: var(--up); }
.conf { font-size: 12px; color: var(--muted); }
.conf b.high { color: var(--up); }
.conf b.medium { color: #d97706; }
.conf b.low { color: var(--muted); }
</style>
