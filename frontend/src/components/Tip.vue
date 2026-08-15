<script setup>
import { ref } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  width: { type: String, default: '220px' },
})

const show = ref(false)
</script>

<template>
  <span
    class="tip-wrap"
    @mouseenter="show = true"
    @mouseleave="show = false"
  >
    <slot />
    <span v-if="show && text" class="tip-bubble" :style="{ width }">
      {{ text }}
    </span>
  </span>
</template>

<style scoped>
.tip-wrap { position: relative; display: inline-block; cursor: help; }
.tip-bubble {
  position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%);
  z-index: 999; padding: 8px 10px; border-radius: 8px;
  background: rgba(30, 34, 42, 0.95); color: #fff; font-size: 12px; line-height: 1.5;
  box-shadow: 0 6px 20px rgba(0,0,0,.15); pointer-events: none; text-align: left;
  font-weight: 400; white-space: normal;
}
.tip-bubble::after {
  content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
  border: 6px solid transparent; border-top-color: rgba(30, 34, 42, 0.95);
}
</style>
