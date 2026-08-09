<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { getDag, type DagEdge, type DagNode } from '@/api/dag'

const props = defineProps<{
  projectId: number
  refreshKey?: number
  liveStatus?: Record<string, string>
}>()
const emit = defineEmits<{
  (e: 'run', payload: { selection: string; runType: string }): void
}>()

const nodes = ref<DagNode[]>([])
const edges = ref<DagEdge[]>([])
const loading = ref(false)
const scale = ref(1)

const search = ref('')
const typeFilter = ref<string[]>(['model', 'test', 'source', 'seed', 'snapshot'])
const selected = ref<string | null>(null)

const NODE_W = 150
const NODE_H = 42
const H_GAP = 40
const V_GAP = 90

const TYPES = ['model', 'test', 'source', 'seed', 'snapshot']
const TYPE_COLOR: Record<string, string> = {
  model: '#409eff',
  test: '#e6a23c',
  source: '#67c23a',
  seed: '#909399',
  snapshot: '#f56c6c',
}
const STATUS_COLOR: Record<string, string> = {
  success: '#67c23a',
  pass: '#67c23a',
  error: '#f56c6c',
  fail: '#f56c6c',
  skipped: '#c0c4cc',
  warn: '#e6a23c',
  running: '#409eff',
}

// 血缘计算
const lineage = computed(() => {
  if (!selected.value) return null
  const target = selected.value
  const out = new Map<string, string[]>()
  const inn = new Map<string, string[]>()
  nodes.value.forEach((n) => {
    out.set(n.id, [])
    inn.set(n.id, [])
  })
  edges.value.forEach((e) => {
    out.get(e.source)?.push(e.target)
    inn.get(e.target)?.push(e.source)
  })
  const up = new Set<string>()
  const down = new Set<string>()
  const bfs = (start: string, adj: Map<string, string[]>, set: Set<string>) => {
    const q = [start]
    while (q.length) {
      const cur = q.shift()!
      for (const nb of adj.get(cur) ?? []) {
        if (!set.has(nb)) {
          set.add(nb)
          q.push(nb)
        }
      }
    }
  }
  bfs(target, inn, up) // 祖先
  bfs(target, out, down) // 后代
  return { target, up, down }
})

// 过滤后的可见节点
const visibleNodes = computed(() => {
  const typeOk = (n: DagNode) => typeFilter.value.includes(n.type)
  const searchOk = (n: DagNode) =>
    !search.value || n.label.toLowerCase().includes(search.value.toLowerCase())
  const lg = lineage.value
  if (lg) {
    return nodes.value.filter((n) => {
      if (!typeOk(n) || !searchOk(n)) return false
      return n.id === lg.target || lg.up.has(n.id) || lg.down.has(n.id)
    })
  }
  return nodes.value.filter((n) => typeOk(n) && searchOk(n))
})

// 布局只对可见节点计算
const layout = computed(() => {
  const visible = visibleNodes.value
  const idSet = new Set(visible.map((n) => n.id))
  const visEdges = edges.value.filter((e) => idSet.has(e.source) && idSet.has(e.target))
  const inDeg = new Map<string, number>()
  visible.forEach((n) => inDeg.set(n.id, 0))
  visEdges.forEach((e) => inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1))

  const childMap = new Map<string, string[]>()
  visEdges.forEach((e) => {
    if (!childMap.has(e.source)) childMap.set(e.source, [])
    childMap.get(e.source)!.push(e.target)
  })

  const level = new Map<string, number>()
  visible.forEach((n) => level.set(n.id, 0))
  const queue = visible.filter((n) => (inDeg.get(n.id) ?? 0) === 0).map((n) => n.id)
  const visited = new Set<string>()
  const q = [...queue]
  while (q.length) {
    const cur = q.shift()!
    if (visited.has(cur)) continue
    visited.add(cur)
    for (const child of childMap.get(cur) ?? []) {
      level.set(child, Math.max(level.get(child) ?? 0, (level.get(cur) ?? 0) + 1))
      q.push(child)
    }
  }
  visible.forEach((n) => {
    if (!visited.has(n.id)) level.set(n.id, 0)
  })

  const byLevel = new Map<number, string[]>()
  visible.forEach((n) => {
    const l = level.get(n.id) ?? 0
    if (!byLevel.has(l)) byLevel.set(l, [])
    byLevel.get(l)!.push(n.id)
  })
  const levels = [...byLevel.keys()].sort((a, b) => a - b)
  const maxCount = Math.max(1, ...levels.map((l) => byLevel.get(l)!.length))
  const width = (maxCount - 1) * (NODE_W + H_GAP) + NODE_W

  const pos = new Map<string, { x: number; y: number }>()
  levels.forEach((l) => {
    const ids = byLevel.get(l)!
    const startX = (width - ids.length * (NODE_W + H_GAP)) / 2
    ids.forEach((id, i) => {
      pos.set(id, { x: startX + i * (NODE_W + H_GAP), y: l * (NODE_H + V_GAP) })
    })
  })

  return {
    pos,
    width,
    height: (levels.length - 1) * (NODE_H + V_GAP) + NODE_H,
  }
})

function edgePath(e: DagEdge): string {
  const a = layout.value.pos.get(e.source)
  const b = layout.value.pos.get(e.target)
  if (!a || !b) return ''
  const x1 = a.x + NODE_W / 2
  const y1 = a.y + NODE_H
  const x2 = b.x + NODE_W / 2
  const y2 = b.y
  const midY = (y1 + y2) / 2
  return `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`
}

function isDimmed(n: DagNode): boolean {
  const lg = lineage.value
  if (!lg) return false
  return n.id !== lg.target && !lg.up.has(n.id) && !lg.down.has(n.id)
}

// 实时状态覆盖持久化状态
const _lastRenderStatus = new Map<string, string>()
function statusOf(n: DagNode): string {
  const s = props.liveStatus?.[n.label] ?? n.status
  _lastRenderStatus.set(n.id, s)
  return s
}

async function load() {
  loading.value = true
  try {
    const res = await getDag(props.projectId)
    nodes.value = res.data.nodes
    edges.value = res.data.edges
    _lastRenderStatus.clear()
  } finally {
    loading.value = false
  }
}

function zoom(dir: number) {
  scale.value = Math.min(2, Math.max(0.4, scale.value + dir * 0.2))
}

function clickNode(id: string) {
  selected.value = selected.value === id ? null : id
}

function runAction(runType: string) {
  if (!selected.value) return
  const n = nodes.value.find((x) => x.id === selected.value)
  emit('run', { selection: n?.label ?? '', runType })
}

onMounted(load)
watch(() => props.projectId, load)
watch(
  () => props.refreshKey,
  () => {
    if (props.refreshKey) load()
  },
)
</script>

<template>
  <div class="dag-wrap">
    <div class="dag-toolbar">
      <el-input
        v-model="search"
        placeholder="搜索节点…"
        clearable
        style="width: 180px"
      />
      <div class="legend">
        <label
          v-for="t in TYPES"
          :key="t"
          class="legend-item"
          :class="{ off: !typeFilter.includes(t) }"
        >
          <input
            type="checkbox"
            :value="t"
            v-model="typeFilter"
            :style="{ accentColor: TYPE_COLOR[t] }"
          />
          <i :style="{ background: TYPE_COLOR[t] }" />{{ t }}
        </label>
      </div>
      <el-button v-if="selected" link @click="selected = null">清除血缘</el-button>
      <div class="spacer" />
      <el-button-group>
        <el-button size="small" @click="zoom(-1)">−</el-button>
        <el-button size="small" @click="zoom(1)">＋</el-button>
      </el-button-group>
      <el-button size="small" :loading="loading" @click="load">刷新</el-button>
    </div>

    <div class="dag-canvas" v-loading="loading">
      <div class="transform" :style="{ transform: `scale(${scale})` }">
        <svg :width="layout.width + 40" :height="layout.height + 40">
          <g transform="translate(20 20)">
            <!-- 边 -->
            <path
              v-for="(e, i) in edges.filter(
                (x) => layout.pos.has(x.source) && layout.pos.has(x.target),
              )"
              :key="i"
              :d="edgePath(e)"
              fill="none"
              :stroke="
                selected && (lineage!.target === e.source || lineage!.target === e.target)
                  ? '#409eff'
                  : '#c0c4cc'
              "
              stroke-width="1.5"
              marker-end="url(#arrow)"
            />
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#c0c4cc" />
              </marker>
            </defs>

            <!-- 节点 -->
            <g
              v-for="n in nodes.filter((x) => layout.pos.has(x.id))"
              :key="n.id"
              :transform="`translate(${layout.pos.get(n.id)?.x ?? 0}, ${layout.pos.get(n.id)?.y ?? 0})`"
              class="node"
              :class="{ active: selected === n.id, dim: isDimmed(n), running: statusOf(n) === 'running' }"
              @click="clickNode(n.id)"
            >
              <rect
                :width="NODE_W"
                :height="NODE_H"
                rx="8"
                :fill="TYPE_COLOR[n.type] ?? '#909399'"
                :stroke="STATUS_COLOR[statusOf(n)] ?? 'transparent'"
                stroke-width="3"
              />
              <text :x="NODE_W / 2" :y="NODE_H / 2 + 4" text-anchor="middle" class="node-label">
                {{ n.label }}
              </text>
            </g>
          </g>
        </svg>
      </div>
      <div v-if="!loading && nodes.length === 0" class="empty">
        暂无节点，请先点击「重新解析」
      </div>
    </div>

    <!-- 选中节点：详情 + 运行 -->
    <div v-if="selected" class="node-info">
      <div class="info-head">
        <span class="info-label">{{ selected }}</span>
        <div class="spacer" />
        <el-button size="small" @click="runAction('run')">运行</el-button>
        <el-button size="small" @click="runAction('test')">测试</el-button>
        <el-button size="small" @click="runAction('build')">Build</el-button>
        <el-button size="small" @click="runAction('compile')">编译</el-button>
      </div>
      <div v-for="n in nodes.filter((x) => x.id === selected)" :key="n.id">
        类型：{{ n.type }}
        <template v-if="n.materialized"> · 物化：{{ n.materialized }}</template>
        <template v-if="n.status"> · 状态：{{ n.status }}</template>
      </div>
      <div v-if="lineage" class="lineage-summary">
        上游 {{ lineage.up.size }} 个 · 下游 {{ lineage.down.size }} 个
      </div>
    </div>
  </div>
</template>

<style scoped>
.dag-wrap {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}
.dag-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid #e4e7ed;
  flex-wrap: wrap;
}
.legend {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: #606266;
  flex-wrap: wrap;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.legend-item input {
  margin: 0;
}
.legend-item.off i {
  opacity: 0.3;
}
.legend-item i {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  display: inline-block;
}
.spacer {
  flex: 1;
}
.dag-canvas {
  min-height: 480px;
  max-height: 640px;
  overflow: auto;
  padding: 20px;
}
.transform {
  transform-origin: 0 0;
}
.node {
  cursor: pointer;
  transition: opacity 0.2s;
}
.node.dim {
  opacity: 0.25;
}
.node.active rect {
  stroke-width: 4;
}
@keyframes pulse {
  0%,
  100% {
    stroke-width: 3;
  }
  50% {
    stroke-width: 8;
  }
}
.node.running rect {
  animation: pulse 1.1s ease-in-out infinite;
}
.node-label {
  fill: #fff;
  font-size: 13px;
  font-weight: 600;
  pointer-events: none;
}
.empty {
  text-align: center;
  color: #909399;
  padding: 60px 0;
}
.node-info {
  padding: 10px 14px;
  border-top: 1px solid #e4e7ed;
  font-size: 13px;
  color: #303133;
  background: #fafafa;
}
.info-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.info-label {
  font-weight: 600;
  word-break: break-all;
}
.lineage-summary {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
}
</style>
