<script setup lang="ts">
import { Codemirror } from 'vue-codemirror'
import { sql } from '@codemirror/lang-sql'

withDefaults(
  defineProps<{ height?: string; placeholder?: string }>(),
  { height: '300px', placeholder: '输入 SQL…' },
)

const model = defineModel<string>({ required: true })
</script>

<template>
  <div class="sql-editor" :style="{ height }">
    <Codemirror
      v-model="model"
      :extensions="[sql()]"
      :placeholder="placeholder"
      theme="dark"
      :style="{ height: '100%' }"
    />
  </div>
</template>

<style scoped>
.sql-editor {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
}
.sql-editor :deep(.cm-editor) {
  height: 100%;
  font-size: 13px;
}
</style>
