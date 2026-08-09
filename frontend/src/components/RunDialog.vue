<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { cancelRun } from '@/api/runs'

const props = defineProps<{ projectId: number }>()
const emit = defineEmits<{
  (e: 'done'): void
  (e: 'status', payload: { name: string; status: string }): void
  (e: 'running', names: string[]): void
}>()

const visible = ref(false)
const running = ref(false)
const selection = ref('')
const runType = ref<'run' | 'test' | 'compile' | 'build'>('run')
const lines = ref<string[]>([])
const autoscroll = ref(true)
const logBox = ref<HTMLElement>()
const currentRunId = ref<number | null>(null)

let ws: WebSocket | null = null

function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/projects/${props.projectId}/runs`
}

function open() {
  visible.value = true
  lines.value = []
  running.value = false
}

function setRun(selectionVal: string, type?: 'run' | 'test' | 'compile' | 'build') {
  selection.value = selectionVal
  if (type) runType.value = type
}

defineExpose({ open, setRun })

function start() {
  lines.value = []
  running.value = true
  currentRunId.value = null
  ws = new WebSocket(wsUrl())
  ws.onopen = () => {
    ws?.send(JSON.stringify({ run_type: runType.value, selection: selection.value }))
  }
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.type === 'start') {
      currentRunId.value = msg.run_id
      push(`▶ 开始运行 #${msg.run_id}`)
    } else if (msg.type === 'running') {
      emit('running', msg.names ?? [])
    } else if (msg.type === 'log') {
      push(msg.line.replace(/\n$/, ''))
    } else if (msg.type === 'node_status') {
      emit('status', { name: msg.name, status: msg.status })
    } else if (msg.type === 'done') {
      running.value = false
      currentRunId.value = null
      push(
        msg.cancelled
          ? '✕ 运行已取消'
          : msg.returncode === 0
            ? '✔ 运行完成（returncode 0）'
            : `✘ 运行失败（returncode ${msg.returncode}）`,
      )
      emit('done')
    } else if (msg.type === 'error') {
      push(`✘ ${msg.message}`)
      running.value = false
      currentRunId.value = null
    }
  }
  ws.onerror = () => {
    running.value = false
    currentRunId.value = null
    push('✘ WebSocket 连接失败')
    ElMessage.error('连接失败，请确认后端已启动')
  }
  ws.onclose = () => {
    running.value = false
  }
}

async function cancel() {
  if (currentRunId.value === null) return
  await cancelRun(props.projectId, currentRunId.value)
  push('✕ 正在取消…')
}

function push(text: string) {
  lines.value.push(text)
  if (autoscroll.value) {
    requestAnimationFrame(() => {
      if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
    })
  }
}

function close() {
  ws?.close()
  ws = null
  visible.value = false
}

onBeforeUnmount(close)
</script>

<template>
  <el-dialog
    v-model="visible"
    title="运行"
    width="720px"
    :close-on-click-modal="false"
    @closed="close"
  >
    <div class="controls">
      <el-select v-model="runType" style="width: 130px" :disabled="running">
        <el-option label="run" value="run" />
        <el-option label="test" value="test" />
        <el-option label="compile" value="compile" />
        <el-option label="build" value="build" />
      </el-select>
      <el-input
        v-model="selection"
        placeholder="--select 表达式，如 example 或 example+"
        style="flex: 1"
        :disabled="running"
      />
      <el-button type="primary" :loading="running" @click="start">
        {{ running ? '运行中…' : '开始运行' }}
      </el-button>
      <el-button v-if="running" type="danger" plain @click="cancel">取消</el-button>
    </div>

    <div ref="logBox" class="log-box">
      <pre v-if="lines.length === 0" class="placeholder">运行日志将在此实时显示…</pre>
      <div v-for="(line, i) in lines" :key="i" class="log-line">{{ line }}</div>
    </div>
  </el-dialog>
</template>

<style scoped>
.controls {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.log-box {
  height: 360px;
  overflow: auto;
  background: #1e1e1e;
  border-radius: 6px;
  padding: 12px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
}
.log-line {
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
}
.placeholder {
  color: #888;
}
</style>
