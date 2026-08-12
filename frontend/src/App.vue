<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { getElementPlusLocale } from '@/i18n'
import LangSwitch from '@/components/LangSwitch.vue'

const { locale } = useI18n()

// Element Plus 动态语言切换
const epLocale = ref(getElementPlusLocale(locale.value))

function handleLocaleChange(e: Event) {
  const lang = (e as CustomEvent).detail
  epLocale.value = getElementPlusLocale(lang)
}

onMounted(() => {
  window.addEventListener('locale-change', handleLocaleChange)
})

onBeforeUnmount(() => {
  window.removeEventListener('locale-change', handleLocaleChange)
})
</script>

<template>
  <el-config-provider :locale="epLocale">
    <div class="layout">
      <header class="topbar">
        <div class="brand">DBT UI</div>
        <div class="spacer" />
        <LangSwitch />
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </el-config-provider>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: #f5f7fa;
}
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.brand {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.spacer {
  flex: 1;
}
.content {
  padding-bottom: 40px;
}
</style>
