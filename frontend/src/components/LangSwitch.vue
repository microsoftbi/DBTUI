<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'

const { locale } = useI18n()

const options = [
  { value: 'en', label: 'English' },
  { value: 'zh', label: '中文' },
]

function handleChange(val: string) {
  setLocale(val as 'en' | 'zh')
  // 通知 App.vue 切换 Element Plus 语言
  window.dispatchEvent(new CustomEvent('locale-change', { detail: val }))
}
</script>

<template>
  <el-select
    :model-value="locale"
    @change="handleChange"
    size="small"
    style="width: 110px"
  >
    <el-option
      v-for="opt in options"
      :key="opt.value"
      :label="opt.label"
      :value="opt.value"
    />
  </el-select>
</template>
