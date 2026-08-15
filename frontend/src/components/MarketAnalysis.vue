<script setup>
import Tip from './Tip.vue'

const props = defineProps({
  data: { type: Object, default: null },
})

function cls(chg) {
  return chg > 0 ? 'up' : chg < 0 ? 'down' : 'neu'
}

function fmt(chg) {
  if (chg == null) return '-'
  return (chg > 0 ? '+' : '') + chg.toFixed(2) + '%'
}

const SENTIMENT_CLS = {
  '偏多': 'pos', '中性偏多': 'pos', '中性': 'neu',
  '中性偏空': 'neg', '偏空': 'neg',
}
</script>

<template>
  <div v-if="props.data" class="mkt">
    <!-- 大盘指数 -->
    <div class="row">
      <div class="row-label">大盘指数</div>
      <div class="chips">
        <Tip
          v-for="m in props.data.market"
          :key="m.name"
          text="今日该指数涨跌幅，红色=上涨，绿色=下跌"
        >
          <div class="chip" :class="cls(m.change_pct)">
            <span class="m-name">{{ m.name }}</span>
            <span class="m-price">{{ m.price.toFixed(2) }}</span>
            <span class="m-chg">{{ fmt(m.change_pct) }}</span>
          </div>
        </Tip>
        <div v-if="!props.data.market || !props.data.market.length" class="none">
          指数数据暂不可用
        </div>
      </div>
    </div>

    <!-- 所属板块 -->
    <div class="row" v-if="props.data.sector">
      <div class="row-label">所属板块</div>
      <Tip text="该股所属行业板块今日的涨跌幅">
        <div class="chip big" :class="cls(props.data.sector.change_pct)">
          <span class="m-name">{{ props.data.sector.name }}</span>
          <span class="m-chg">{{ fmt(props.data.sector.change_pct) }}</span>
        </div>
      </Tip>
    </div>

    <!-- 领涨/领跌板块 -->
    <div class="row">
      <div class="row-label">板块热点</div>
      <div class="two-col">
        <div class="sect-col">
          <div class="col-title up-t">领涨</div>
          <div v-for="s in props.data.sector_top" :key="s.name" class="sect-line">
            <span class="s-name">{{ s.name }}</span>
            <span class="s-chg" :class="cls(s.change_pct)">{{ fmt(s.change_pct) }}</span>
          </div>
        </div>
        <div class="sect-col">
          <div class="col-title down-t">领跌</div>
          <div v-for="s in props.data.sector_bottom" :key="s.name" class="sect-line">
            <span class="s-name">{{ s.name }}</span>
            <span class="s-chg" :class="cls(s.change_pct)">{{ fmt(s.change_pct) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 综合分析 -->
    <div class="analysis" v-if="props.data.analysis">
      <div class="verdict" :class="SENTIMENT_CLS[props.data.analysis.sentiment]">
        {{ props.data.analysis.sentiment }}
      </div>
      <div class="summary">{{ props.data.analysis.summary }}</div>
      <ul class="points">
        <li v-for="(p, i) in props.data.analysis.points" :key="i">{{ p }}</li>
      </ul>
    </div>
  </div>
  <div v-else class="none">分析加载中...</div>
</template>

<style scoped>
.mkt { display: flex; flex-direction: column; gap: 14px; }
.row { display: flex; align-items: flex-start; gap: 12px; }
.row-label {
  flex-shrink: 0; width: 58px; padding-top: 6px;
  font-size: 13px; color: var(--muted);
}
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; border-radius: 8px; background: #f7f9fc;
  font-size: 13px;
}
.chip.big { padding: 8px 14px; font-size: 14px; }
.chip .m-name { color: var(--muted); }
.chip .m-price { font-weight: 600; }
.chip .m-chg { font-weight: 600; }
.up { color: var(--up); }
.down { color: var(--down); }
.neu { color: var(--text); }
.none { color: var(--muted); font-size: 13px; }
.two-col { display: flex; gap: 28px; }
.sect-col { flex: 1; }
.col-title { font-size: 12px; margin-bottom: 4px; font-weight: 600; }
.col-title.up-t { color: var(--up); }
.col-title.down-t { color: var(--down); }
.sect-line {
  display: flex; justify-content: space-between; padding: 3px 0;
  font-size: 13px; border-bottom: 1px dashed #eef1f5;
}
.s-name { color: var(--text); }
.s-chg { font-weight: 600; }
.analysis {
  border-top: 1px solid var(--border); padding-top: 12px;
  display: flex; flex-direction: column; gap: 8px;
}
.verdict {
  align-self: flex-start; padding: 3px 12px; border-radius: 20px;
  font-size: 13px; font-weight: 700;
}
.verdict.pos { background: #fdeef0; color: var(--up); }
.verdict.neg { background: #e6f6ef; color: var(--down); }
.verdict.neu { background: #eef1f5; color: var(--muted); }
.summary { font-size: 14px; font-weight: 600; }
.points { list-style: none; display: flex; flex-direction: column; gap: 5px; }
.points li { font-size: 13px; color: #444; padding-left: 14px; position: relative; }
.points li::before { content: '·'; position: absolute; left: 2px; color: var(--muted); }
</style>
