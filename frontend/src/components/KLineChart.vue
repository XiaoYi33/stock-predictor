<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  code: { type: String, default: '' },
  data: { type: Object, default: null },
})

const el = ref(null)
let chart = null

function render() {
  if (!props.data || !el.value) return
  if (!chart) chart = echarts.init(el.value)

  const d = JSON.parse(JSON.stringify(props.data))
  const klines = (d.klines || []).map(k => [Number(k[0]), Number(k[1]), Number(k[2]), Number(k[3])])
  const volumes = (d.volumes || []).map(v => (v / 10000).toFixed(2))

  chart.clear()
  chart.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: function (params) {
        if (!params || !params.length) return ''
        const date = params[0].axisValue
        const idx = params[0].dataIndex
        const k = klines[idx] || []
        const vol = volumes[idx] || 0
        const ma5 = (d.ma5 || [])[idx]
        const ma20 = (d.ma20 || [])[idx]
        const ma60 = (d.ma60 || [])[idx]
        let html = '<div style="font-size:13px;font-weight:600;margin-bottom:4px">' + date + '</div>'
        const isUp = Number(k[1]) >= Number(k[0])
        const dotColor = isUp ? '#d03050' : '#00a05a'
        html += '<span style="color:' + dotColor + '">●</span> K线<br/>'
        html += '&nbsp;&nbsp;开: ' + Number(k[0]).toFixed(2) + '<br/>'
        html += '&nbsp;&nbsp;收: ' + Number(k[1]).toFixed(2) + '<br/>'
        html += '&nbsp;&nbsp;低: ' + Number(k[2]).toFixed(2) + '<br/>'
        html += '&nbsp;&nbsp;高: ' + Number(k[3]).toFixed(2) + '<br/>'
        html += '&nbsp;&nbsp;成交量: ' + Number(vol).toFixed(0) + '万手<br/>'
        html += '<span style="color:#eab308">─</span> 5日均线: ' + (ma5 != null ? Number(ma5).toFixed(2) : '-') + '<br/>'
        html += '<span style="color:#3b82f6">─</span> 20日均线: ' + (ma20 != null ? Number(ma20).toFixed(2) : '-') + '<br/>'
        html += '<span style="color:#a855f7">─</span> 60日均线: ' + (ma60 != null ? Number(ma60).toFixed(2) : '-')
        return html
      },
    },
    legend: { data: ['5日均线', '20日均线', '60日均线'], top: 0 },
    grid: [
      { left: 56, right: 20, top: 30, height: '60%' },
      { left: 56, right: 20, top: '75%', height: '15%' },
    ],
    xAxis: [
      { type: 'category', data: d.dates || [], boundaryGap: true },
      { type: 'category', gridIndex: 1, data: d.dates || [], axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 40, end: 100 }],
    series: [
      {
        type: 'candlestick',
        name: props.code,
        data: klines,
        itemStyle: {
          color: '#d03050', color0: '#00a05a',
          borderColor: '#d03050', borderColor0: '#00a05a',
        },
      },
      { type: 'line', name: '5日均线', data: d.ma5 || [],
        smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#eab308' } },
      { type: 'line', name: '20日均线', data: d.ma20 || [],
        smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#3b82f6' } },
      { type: 'line', name: '60日均线', data: d.ma60 || [],
        smooth: true, showSymbol: false, lineStyle: { width: 1, color: '#a855f7' } },
      {
        type: 'bar', name: '成交量(万手)', xAxisIndex: 1, yAxisIndex: 1,
        data: volumes, itemStyle: { color: '#9ca3af' },
      },
    ],
  })
}

function resize() { chart && chart.resize() }

watch(() => props.data, render)
onMounted(() => { render(); window.addEventListener('resize', resize) })
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  if (chart) { chart.clear(); chart.dispose(); chart = null }
})
</script>

<template>
  <div ref="el" class="chart"></div>
</template>

<style scoped>
.chart { width: 100%; height: 460px; }
</style>