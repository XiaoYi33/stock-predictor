<script setup>
import { ref, watch } from 'vue'
import { searchStock } from '../api.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'select'])

const kw = ref(props.modelValue)
const suggestions = ref([])
const show = ref(false)
let timer = null

watch(() => props.modelValue, (v) => { kw.value = v })

watch(kw, (v) => {
  emit('update:modelValue', v)
  clearTimeout(timer)
  if (!v.trim()) { suggestions.value = []; return }
  timer = setTimeout(async () => {
    try {
      suggestions.value = await searchStock(v.trim())
      show.value = true
    } catch { suggestions.value = [] }
  }, 250)
})

function pick(item) {
  emit('select', item)
  kw.value = item.code
  suggestions.value = []
  show.value = false
}

function onKeyup(e) {
  if (e.key === 'Enter' && kw.value.trim()) {
    emit('select', { code: kw.value.trim(), name: '' })
    show.value = false
  }
  if (e.key === 'Escape') show.value = false
}
</script>

<template>
  <div class="search">
    <div class="input-wrap">
      <input
        v-model="kw"
        placeholder="输入6位股票代码, 如 300750"
        @keyup="onKeyup"
        @focus="kw && (show = true)"
        @blur="setTimeout(() => (show = false), 150)"
      />
      <button @click="kw.trim() && emit('select', { code: kw.trim(), name: '' })">
        预测
      </button>
    </div>
    <ul v-if="show && suggestions.length" class="suggest">
      <li v-for="s in suggestions" :key="s.code" @mousedown.prevent="pick(s)">
        <span class="code">{{ s.code }}</span>
        <span class="name">{{ s.name }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.search { position: relative; flex: 1; max-width: 480px; }
.input-wrap { display: flex; gap: 8px; }
input {
  flex: 1; padding: 9px 12px; border: 1px solid var(--border);
  border-radius: 8px; font-size: 14px; outline: none;
}
input:focus { border-color: #3b82f6; }
button {
  padding: 0 18px; border: none; border-radius: 8px;
  background: #3b82f6; color: #fff; font-size: 14px; cursor: pointer;
}
button:hover { background: #2f6fe0; }
.suggest {
  position: absolute; top: 100%; left: 0; right: 0; margin-top: 4px;
  background: #fff; border: 1px solid var(--border); border-radius: 8px;
  list-style: none; max-height: 260px; overflow: auto; z-index: 20;
  box-shadow: 0 6px 20px rgba(0,0,0,.08);
}
.suggest li { display: flex; justify-content: space-between; padding: 8px 12px; cursor: pointer; }
.suggest li:hover { background: #f0f4ff; }
.suggest .code { font-weight: 600; }
.suggest .name { color: var(--muted); }
</style>
