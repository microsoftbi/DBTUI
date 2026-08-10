<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Folder } from '@element-plus/icons-vue'
import { listProjects, parseProject, getProfiles, saveProfiles } from '@/api/projects'
import {
  createModel,
  deleteModel,
  getModelSql,
  listModels,
  updateModel,
  type Model,
} from '@/api/models'
import {
  createTest,
  deleteTest,
  getTestSql,
  listTests,
  type Test,
} from '@/api/tests'
import {
  addSourceTable,
  createSource,
  deleteSource,
  deleteSourceTable,
  listSources,
  updateSource,
  updateSourceTable,
  type SourceDefinition,
  type SourceTable,
} from '@/api/sources'
import {
  createLayer,
  deleteLayer,
  listLayers,
  updateLayer,
  type LayerDefinition,
} from '@/api/layers'
import { listRuns, getRunDetail, type RunHistory } from '@/api/runs'
import {
  getData,
  getDdl,
  listDatabases,
  listTables,
  type DataPreview,
  type TableInfo,
} from '@/api/dataViewer'
import RunDialog from '@/components/RunDialog.vue'
import DagGraph from '@/components/DagGraph.vue'
import SqlEditor from '@/components/SqlEditor.vue'
import type { Project } from '@/types'
import { Codemirror } from 'vue-codemirror'
import { sql } from '@codemirror/lang-sql'
import { DataAnalysis, Grid, View, Refresh } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const project = ref<Project | null>(null)
const models = ref<Model[]>([])
const tests = ref<Test[]>([])
const runs = ref<RunHistory[]>([])
const loading = ref(false)
const activeTab = ref('models')
const dagVersion = ref(0)
const liveStatuses = ref<Record<string, string>>({})

const runDialog = ref<InstanceType<typeof RunDialog>>()

// ---------- 加载 ----------
async function loadProject() {
  try {
    const list = (await listProjects()).data
    project.value = list.find((p) => p.id === projectId) ?? null
    if (!project.value) {
      ElMessage.error('项目不存在')
      router.replace('/')
    }
  } catch {
    /* http interceptor 已提示 */
  }
}
async function loadModels() {
  models.value = (await listModels(projectId)).data
}
async function loadTests() {
  tests.value = (await listTests(projectId)).data
}
async function loadRuns() {
  runs.value = (await listRuns(projectId)).data
}
async function load() {
  loading.value = true
  try {
    await Promise.all([loadModels(), loadTests(), loadSources(), loadLayers(), loadRuns()])
  } finally {
    loading.value = false
  }
}

async function doParse() {
  loading.value = true
  try {
    await parseProject(projectId)
    ElMessage.success('解析成功')
    dagVersion.value++
    await load()
  } finally {
    loading.value = false
  }
}

// ---------- 运行 ----------
function openRun(selection: string, runType: 'run' | 'test' | 'compile' | 'build') {
  runDialog.value?.open()
  setTimeout(() => runDialog.value?.setRun(selection, runType), 0)
}
function onRunDone() {
  liveStatuses.value = {}
  dagVersion.value++
  load()
}
// 记录每个节点进入 running 的时刻，用于统计 running→最终状态 的耗时
const runningAt = ref<Record<string, number>>({})

function onNodeStatus(payload: { name: string; status: string }) {
  liveStatuses.value = { ...liveStatuses.value, [payload.name]: payload.status }
}

function onRunning(names: string[]) {
  const next = { ...liveStatuses.value }
  const nowAt = { ...runningAt.value }
  const ts = Date.now()
  names.forEach((n) => {
    next[n] = 'running'
    nowAt[n] = ts
  })
  liveStatuses.value = next
  runningAt.value = nowAt
}
function onDagRun(payload: { selection: string; runType: string }) {
  openRun(payload.selection, payload.runType as 'run' | 'test' | 'compile' | 'build')
}

// ---------- Model CRUD ----------
const modelCreate = ref(false)
const modelForm = ref({ name: '', sql: 'SELECT 1 AS id\n', subdir: 'staging' })
async function submitModel() {
  if (!modelForm.value.name.trim()) {
    ElMessage.warning('请输入模型名称')
    return
  }
  await createModel(projectId, { ...modelForm.value })
  ElMessage.success('模型已创建')
  modelCreate.value = false
  modelForm.value = { name: '', sql: 'SELECT 1 AS id\n', subdir: 'staging' }
  dagVersion.value++
  await loadModels()
}
async function removeModel(model: Model) {
  await ElMessageBox.confirm(`确定删除模型「${model.name}」？`, '删除确认', {
    type: 'warning',
  })
  await deleteModel(projectId, model.id)
  ElMessage.success('已删除')
  dagVersion.value++
  await loadModels()
}

// 模型编辑器
const MATERIALIZED = ['view', 'table', 'incremental', 'ephemeral']
const modelEdit = ref(false)
const editForm = ref({
  modelId: 0,
  name: '',
  sql: '',
  originalName: '',
  materialized: 'view',
})
async function openModelEdit(model: Model) {
  const res = await getModelSql(projectId, model.id)
  editForm.value = {
    modelId: model.id,
    name: res.data.name,
    sql: res.data.sql,
    originalName: res.data.name,
    materialized: res.data.materialized || 'view',
  }
  modelEdit.value = true
}
async function saveModel() {
  await updateModel(projectId, editForm.value.modelId, {
    name: editForm.value.name,
    sql: editForm.value.sql,
    materialized: editForm.value.materialized,
  })
  ElMessage.success('已保存')
  modelEdit.value = false
  dagVersion.value++
  await loadModels()
}

// ---------- Test CRUD ----------
const testEdit = ref(false)
const testForm = ref({
  testId: null as number | null,
  name: '',
  sql: "SELECT * FROM {{ ref('example') }} WHERE 1 = 0\n",
})
function openTestCreate() {
  testForm.value = { testId: null, name: '', sql: "SELECT * FROM {{ ref('example') }} WHERE 1 = 0\n" }
  testEdit.value = true
}
async function openTestEdit(test: Test) {
  const res = await getTestSql(projectId, test.id)
  testForm.value = {
    testId: test.id,
    name: res.data.name,
    sql: res.data.sql,
  }
  testEdit.value = true
}
async function saveTest() {
  if (!testForm.value.name.trim()) {
    ElMessage.warning('请输入测试名称')
    return
  }
  if (testForm.value.testId === null) {
    await createTest(projectId, { name: testForm.value.name, sql: testForm.value.sql })
    ElMessage.success('测试已创建')
  } else {
    await deleteTest(projectId, testForm.value.testId) // singular test 用删除重建方式
    await createTest(projectId, { name: testForm.value.name, sql: testForm.value.sql })
    ElMessage.success('测试已保存')
  }
  testEdit.value = false
  dagVersion.value++
  await loadTests()
}
async function removeTest(test: Test) {
  await ElMessageBox.confirm(`确定删除测试「${test.name}」？`, '删除确认', {
    type: 'warning',
  })
  await deleteTest(projectId, test.id)
  ElMessage.success('已删除')
  dagVersion.value++
  await loadTests()
}

// ---------- Source CRUD ----------
const sources = ref<SourceDefinition[]>([])
const activeSource = ref<string>('')

async function loadSources() {
  sources.value = (await listSources(projectId)).data
  if (!activeSource.value && sources.value.length > 0) {
    activeSource.value = sources.value[0].source_name
  }
}

const currentSource = computed(() =>
  sources.value.find((s) => s.source_name === activeSource.value) || null,
)

const sourcesTreeData = computed(() =>
  sources.value.map((s) => ({
    key: `source:${s.subdir}:${s.source_name}`,
    type: 'source',
    sourceName: s.source_name,
    subdir: s.subdir,
    label: s.source_name,
    children: s.tables.map((t) => ({
      key: `table:${s.subdir}:${s.source_name}.${t.name}`,
      type: 'table',
      sourceName: s.source_name,
      label: t.name,
    })),
  })),
)

function onSourceTreeNodeClick(data: {
  type: string
  sourceName: string
  label: string
}) {
  if (data.type === 'source') {
    activeSource.value = data.sourceName
  } else {
    // 点击表时，先选中对应的 source
    activeSource.value = data.sourceName
  }
}

// 新建/编辑 source 弹窗
const SOURCE_DIRS = [
  { value: 'staging', label: 'Stage 层（staging）' },
  { value: 'core', label: 'Core 层（core）' },
  { value: 'marts', label: 'Mart 层（marts）' },
  { value: '', label: '根目录（models）' },
]
const sourceDialogVisible = ref(false)
const sourceDialogMode = ref<'create' | 'edit'>('create')
const sourceForm = ref({
  source_name: '',
  database: '',
  schema: '',
  loader: '',
  description: '',
  subdir: 'staging',
})

function openSourceCreate() {
  sourceDialogMode.value = 'create'
  sourceForm.value = {
    source_name: '',
    database: '',
    schema: '',
    loader: '',
    description: '',
    subdir: 'staging',
  }
  sourceDialogVisible.value = true
}

function openSourceEdit() {
  if (!currentSource.value) return
  sourceDialogMode.value = 'edit'
  sourceForm.value = {
    source_name: currentSource.value.source_name,
    database: currentSource.value.database,
    schema: currentSource.value.schema,
    loader: currentSource.value.loader,
    description: currentSource.value.description,
    subdir: currentSource.value.subdir,
  }
  sourceDialogVisible.value = true
}

async function saveSource() {
  if (!sourceForm.value.source_name.trim()) {
    ElMessage.warning('请输入源名称')
    return
  }
  if (sourceDialogMode.value === 'create') {
    await createSource(projectId, { ...sourceForm.value, tables: [] })
    ElMessage.success('数据源已创建')
  } else {
    await updateSource(projectId, activeSource.value, { ...sourceForm.value })
    ElMessage.success('已保存')
  }
  sourceDialogVisible.value = false
  dagVersion.value++
  await loadSources()
  await loadModels()
}

async function removeSource() {
  if (!currentSource.value) return
  await ElMessageBox.confirm(
    `确定删除数据源「${currentSource.value.source_name}」？其下所有表定义也会被删除。`,
    '删除确认',
    { type: 'warning' },
  )
  await deleteSource(projectId, currentSource.value.source_name)
  ElMessage.success('已删除')
  activeSource.value = ''
  dagVersion.value++
  await loadSources()
  await loadModels()
}

// 表管理弹窗
const tableDialogVisible = ref(false)
const tableDialogMode = ref<'add' | 'edit'>('add')
const editingTableName = ref('')
const tableForm = ref<SourceTable>({
  name: '',
  identifier: '',
  description: '',
})

function openTableAdd() {
  tableDialogMode.value = 'add'
  editingTableName.value = ''
  tableForm.value = { name: '', identifier: '', description: '' }
  tableDialogVisible.value = true
}

function openTableEdit(table: SourceTable) {
  tableDialogMode.value = 'edit'
  editingTableName.value = table.name
  tableForm.value = { ...table }
  tableDialogVisible.value = true
}

async function saveTable() {
  if (!tableForm.value.name.trim()) {
    ElMessage.warning('请输入表名')
    return
  }
  if (!currentSource.value) return
  if (tableDialogMode.value === 'add') {
    await addSourceTable(projectId, currentSource.value.source_name, {
      ...tableForm.value,
    })
    ElMessage.success('表已添加')
  } else {
    await updateSourceTable(
      projectId,
      currentSource.value.source_name,
      editingTableName.value,
      { ...tableForm.value },
    )
    ElMessage.success('已保存')
  }
  tableDialogVisible.value = false
  dagVersion.value++
  await loadSources()
  await loadModels()
}

async function removeTable(table: SourceTable) {
  if (!currentSource.value) return
  await ElMessageBox.confirm(`确定删除表「${table.name}」？`, '删除确认', {
    type: 'warning',
  })
  await deleteSourceTable(projectId, currentSource.value.source_name, table.name)
  ElMessage.success('已删除')
  dagVersion.value++
  await loadSources()
  await loadModels()
}

// ---------- Layer 分层配置 ----------
const layers = ref<LayerDefinition[]>([])
const layersDialogVisible = ref(false)
const layerDialogVisible = ref(false)
const layerDialogMode = ref<'create' | 'edit'>('create')
const editingLayerName = ref('')
const layerForm = ref({
  name: '',
  display_name: '',
  database: '',
  schema: '',
  materialized: 'view',
})

const MATERIALIZED_OPTIONS = ['view', 'table', 'incremental', 'ephemeral']

async function loadLayers() {
  layers.value = (await listLayers(projectId)).data
}

function openLayersDialog() {
  loadLayers()
  layersDialogVisible.value = true
}

function openLayerCreate() {
  layerDialogMode.value = 'create'
  editingLayerName.value = ''
  layerForm.value = {
    name: '',
    display_name: '',
    database: '',
    schema: '',
    materialized: 'view',
  }
  layerDialogVisible.value = true
}

function openLayerEdit(layer: LayerDefinition) {
  layerDialogMode.value = 'edit'
  editingLayerName.value = layer.is_root ? '__root__' : layer.name
  layerForm.value = {
    name: layer.name,
    display_name: layer.display_name,
    database: layer.database,
    schema: layer.schema,
    materialized: layer.materialized,
  }
  layerDialogVisible.value = true
}

async function saveLayer() {
  if (!layerForm.value.name.trim() && layerDialogMode.value === 'create') {
    ElMessage.warning('请输入目录名')
    return
  }
  if (layerDialogMode.value === 'create') {
    await createLayer(projectId, { ...layerForm.value })
    ElMessage.success('分层已创建')
  } else {
    await updateLayer(projectId, editingLayerName.value, { ...layerForm.value })
    ElMessage.success('已保存')
  }
  layerDialogVisible.value = false
  dagVersion.value++
  await loadLayers()
  await loadModels()
}

async function removeLayer(layer: LayerDefinition) {
  if (layer.is_root) {
    ElMessage.warning('根目录不能删除')
    return
  }
  await ElMessageBox.confirm(
    `确定删除分层「${layer.display_name || layer.name}」？\n仅删除配置，目录和文件会保留。`,
    '删除确认',
    { type: 'warning' },
  )
  await deleteLayer(projectId, layer.name)
  ElMessage.success('已删除')
  dagVersion.value++
  await loadLayers()
  await loadModels()
}

// 给新建模型用的层级选项（从 layers 动态生成）
const modelLayerOptions = computed(() => {
  const opts = layers.value
    .filter((l) => !l.is_root)
    .map((l) => ({
      value: l.name,
      label: l.display_name || l.name,
      database: l.database,
    }))
  // 加上根目录
  const root = layers.value.find((l) => l.is_root)
  if (root) {
    opts.push({ value: '', label: '根目录（models）', database: root.database || '—' })
  }
  return opts
})

function statusTag(status: string) {
  if (!status) return ''
  const map: Record<string, string> = {
    success: 'success',
    pass: 'success',
    error: 'danger',
    fail: 'danger',
    skipped: 'info',
    warn: 'warning',
  }
  return map[status] ?? 'info'
}
function fmtTime(iso: string | null) {
  return iso ? new Date(iso).toLocaleString() : '-'
}

// 运行日志查看
const runLog = ref({ visible: false, title: '', log: '' })
async function openLog(run: RunHistory) {
  const res = await getRunDetail(projectId, run.id)
  runLog.value = {
    visible: true,
    title: `运行 #${run.id} · ${run.run_type} · ${run.selection || '全部'}`,
    log: res.data.log || '(无日志)',
  }
}

// 连接配置（profiles.yml）
const profilesDialog = ref(false)
const profilesContent = ref('')
const profilesSaving = ref(false)
async function openProfiles() {
  const res = await getProfiles(projectId)
  profilesContent.value = res.data.content
  profilesDialog.value = true
}
async function saveProfilesAction() {
  profilesSaving.value = true
  try {
    await saveProfiles(projectId, profilesContent.value)
    ElMessage.success('连接配置已保存')
    profilesDialog.value = false
  } finally {
    profilesSaving.value = false
  }
}

// ---------- 数据查看器 ----------
const dvLoading = ref(false)
const dvDatabases = ref<string[]>([])
const dvActiveDb = ref('')
const dvTables = ref<TableInfo[]>([])
const dvViews = ref<TableInfo[]>([])
const dvSelected = ref<{ database: string; schema: string; table: string; type: 'table' | 'view' } | null>(null)
const dvDdl = ref('')
const dvDdlType = ref<'table' | 'view'>('table')
const dvData = ref<DataPreview | null>(null)
const dvDataLoading = ref(false)
const dvDdlLoading = ref(false)

// 树节点类型
interface DvTreeNode {
  key: string
  label: string
  type: 'database' | 'folder' | 'table'
  icon?: string
  children?: DvTreeNode[]
  database?: string
  tableType?: 'table' | 'view'
  schema?: string
  tableName?: string
}

const dvTreeData = ref<DvTreeNode[]>([])
const dvTreeKey = ref(0)

async function refreshDataViewer() {
  dvSelected.value = null
  dvDdl.value = ''
  dvData.value = null
  dvTreeKey.value++
  await loadDataViewer()
  ElMessage.success('已刷新')
}

async function loadDataViewer() {
  dvLoading.value = true
  try {
    const res = await listDatabases(projectId)
    dvDatabases.value = res.data.databases
    // 构建树（数据库节点为一级，子节点通过 lazy 加载）
    dvTreeData.value = dvDatabases.value.map((db) => ({
      key: `db:${db}`,
      label: db,
      type: 'database',
      database: db,
    }))
    if (dvDatabases.value.length > 0 && !dvActiveDb.value) {
      dvActiveDb.value = dvDatabases.value[0]
    }
  } finally {
    dvLoading.value = false
  }
}

// el-tree lazy 模式加载函数
function dvLoadNode(
  node: { level: number; data: DvTreeNode },
  resolve: (children: DvTreeNode[]) => void,
) {
  const data = node.data
  if (data.type === 'database' && data.database) {
    dvActiveDb.value = data.database
    // 返回「表」和「视图」两个文件夹
    resolve([
      {
        key: `db:${data.database}:tables`,
        label: '表',
        type: 'folder',
        icon: 'table',
        database: data.database,
        tableType: 'table',
      },
      {
        key: `db:${data.database}:views`,
        label: '视图',
        type: 'folder',
        icon: 'view',
        database: data.database,
        tableType: 'view',
      },
    ])
  } else if (data.type === 'folder' && data.database && data.tableType) {
    // 加载表/视图列表
    listTables(projectId, data.database, data.tableType)
      .then((res) => {
        const children = res.data.tables.map((t) => ({
          key: `tbl:${data.database}:${data.tableType}:${t.schema}.${t.name}`,
          label: t.name,
          type: 'table' as const,
          database: data.database,
          tableType: data.tableType,
          schema: t.schema,
          tableName: t.name,
        }))
        if (data.tableType === 'table') {
          dvTables.value = res.data.tables
        } else {
          dvViews.value = res.data.tables
        }
        resolve(children)
      })
      .catch(() => {
        resolve([])
      })
  } else {
    resolve([])
  }
}

async function onDvNodeClick(data: DvTreeNode) {
  if (data.type === 'table' && data.database && data.tableName && data.schema && data.tableType) {
    // 点击表/视图，加载 DDL 和数据
    dvSelected.value = {
      database: data.database,
      schema: data.schema,
      table: data.tableName,
      type: data.tableType,
    }
    loadDvDdl(data.database, data.schema, data.tableName)
    loadDvData(data.database, data.schema, data.tableName)
  }
}

async function loadDvDdl(database: string, schema: string, table: string) {
  dvDdlLoading.value = true
  try {
    const res = await getDdl(projectId, database, table, schema)
    dvDdl.value = res.data.ddl
    dvDdlType.value = res.data.type
  } finally {
    dvDdlLoading.value = false
  }
}

async function loadDvData(database: string, schema: string, table: string) {
  dvDataLoading.value = true
  try {
    const res = await getData(projectId, database, table, schema, 1000)
    dvData.value = res.data
  } finally {
    dvDataLoading.value = false
  }
}

onMounted(async () => {
  await loadProject()
  await load()
  // 预加载数据查看器数据库列表
  loadDataViewer()
})
</script>

<template>
  <div class="page">
    <div class="head">
      <el-button link @click="router.push('/')">← 返回</el-button>
      <h2>{{ project?.name ?? '加载中…' }}</h2>
      <el-tag v-if="project" size="small" type="info">{{ project.adapter }}</el-tag>
      <el-tag
        v-if="project"
        size="small"
        :type="project.parse_status === 'success' ? 'success' : 'info'"
      >
        {{ project.parse_status || '未解析' }}
      </el-tag>
      <div class="spacer" />
      <el-button @click="openLayersDialog">分层配置</el-button>
      <el-button @click="openProfiles">连接配置</el-button>
      <el-button :loading="loading" @click="doParse">重新解析</el-button>
    </div>

    <el-tabs v-model="activeTab">
      <!-- Models -->
      <el-tab-pane label="Models" name="models">
        <div class="toolbar">
          <span>{{ models.length }} 个模型</span>
          <div class="spacer" />
          <el-button type="primary" @click="modelCreate = true">新建模型</el-button>
        </div>
        <el-table :data="models" v-loading="loading" stripe empty-text="暂无模型">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="database" label="数据库" width="110">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.database }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="resource_type" label="类型" width="100" />
          <el-table-column prop="materialized" label="物化" width="110">
            <template #default="{ row }">
              <el-tag size="small">{{ row.materialized }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="file_path" label="文件" min-width="160" show-overflow-tooltip />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.run_status" size="small" :type="statusTag(row.run_status)">
                {{ row.run_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openModelEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="openRun(row.name, 'run')">运行</el-button>
              <el-button link type="primary" @click="openRun(row.name, 'test')">测试</el-button>
              <el-button link type="danger" @click="removeModel(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Sources -->
      <el-tab-pane label="Sources" name="sources">
        <div class="toolbar">
          <span>{{ sources.length }} 个数据源</span>
          <div class="spacer" />
          <el-button type="primary" @click="openSourceCreate">新建数据源</el-button>
        </div>
        <div class="sources-layout" v-loading="loading">
          <!-- 左侧源列表 -->
          <div class="sources-tree">
            <el-tree
              :data="sourcesTreeData"
              :props="{ label: 'label', children: 'children' }"
              node-key="key"
              :expand-on-click-node="false"
              default-expand-all
              @node-click="onSourceTreeNodeClick"
              empty-text="暂无数据源"
            >
              <template #default="{ data }">
                <span v-if="data.type === 'source'" class="tree-source">
                  <el-icon><Folder /></el-icon>
                  {{ data.label }}
                </span>
                <span v-else class="tree-table">
                  <el-icon><Document /></el-icon>
                  {{ data.label }}
                </span>
              </template>
            </el-tree>
          </div>

          <!-- 右侧详情 -->
          <div class="sources-detail">
            <div v-if="!currentSource" class="empty-detail">
              <el-empty description="请选择左侧数据源查看详情" />
            </div>
            <div v-else>
              <div class="detail-header">
                <h3>{{ currentSource.source_name }}</h3>
                <div class="spacer" />
                <el-button link type="primary" @click="openSourceEdit">编辑</el-button>
                <el-button link type="danger" @click="removeSource">删除</el-button>
              </div>
              <el-descriptions :column="2" border size="small" class="detail-desc">
                <el-descriptions-item label="保存目录">
                  <el-tag size="small" type="info">
                    {{ currentSource.subdir || '根目录' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="数据库">
                  {{ currentSource.database || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="Schema">
                  {{ currentSource.schema || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="加载器">
                  {{ currentSource.loader || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="描述" :span="2">
                  {{ currentSource.description || '-' }}
                </el-descriptions-item>
              </el-descriptions>

              <div class="tables-section">
                <div class="tables-header">
                  <span>表列表（{{ currentSource.tables.length }}）</span>
                  <div class="spacer" />
                  <el-button size="small" type="primary" @click="openTableAdd">
                    添加表
                  </el-button>
                </div>
                <el-table :data="currentSource.tables" stripe size="small" empty-text="暂无表">
                  <el-table-column prop="name" label="表名" min-width="140" />
                  <el-table-column prop="identifier" label="标识符" min-width="140">
                    <template #default="{ row }">
                      {{ row.identifier || row.name }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
                  <el-table-column label="操作" width="150" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="primary" @click="openTableEdit(row)">编辑</el-button>
                      <el-button link type="danger" @click="removeTable(row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tests -->
      <el-tab-pane label="Tests" name="tests">
        <div class="toolbar">
          <span>{{ tests.length }} 个测试</span>
          <div class="spacer" />
          <el-button type="primary" @click="openTestCreate">新建测试</el-button>
        </div>
        <el-table :data="tests" v-loading="loading" stripe empty-text="暂无测试（请先解析）">
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="type" label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="row.type === 'singular' ? 'warning' : ''">
                {{ row.type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="severity" label="级别" width="100" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.run_status" size="small" :type="statusTag(row.run_status)">
                {{ row.run_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openTestEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="openRun(row.name, 'test')">运行</el-button>
              <el-button link type="danger" @click="removeTest(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- DAG -->
      <el-tab-pane label="DAG" name="dag">
        <DagGraph
          :project-id="projectId"
          :refresh-key="dagVersion"
          :live-status="liveStatuses"
          @run="onDagRun"
        />
      </el-tab-pane>

      <!-- 数据查看器 -->
      <el-tab-pane label="数据查看器" name="data-viewer">
        <div class="data-viewer" v-loading="dvLoading">
          <!-- 左侧树 -->
          <div class="dv-tree">
            <div class="dv-tree-header">
              <span class="dv-tree-title">数据库</span>
              <el-button
                size="small"
                :icon="Refresh"
                text
                @click="refreshDataViewer"
              >
                刷新
              </el-button>
            </div>
            <el-tree
              :key="dvTreeKey"
              :data="dvTreeData"
              :props="{ label: 'label', children: 'children' }"
              node-key="key"
              :expand-on-click-node="false"
              lazy
              :load="dvLoadNode"
              @node-click="onDvNodeClick"
              empty-text="暂无数据库"
            >
              <template #default="{ data }">
                <span class="dv-tree-node">
                  <el-icon v-if="data.type === 'database'" class="dv-icon-db">
                    <DataAnalysis />
                  </el-icon>
                  <el-icon v-else-if="data.type === 'folder' && data.tableType === 'table'" class="dv-icon-table">
                    <Grid />
                  </el-icon>
                  <el-icon v-else-if="data.type === 'folder' && data.tableType === 'view'" class="dv-icon-view">
                    <View />
                  </el-icon>
                  <el-icon v-else-if="data.tableType === 'table'" class="dv-icon-table-sm">
                    <Grid />
                  </el-icon>
                  <el-icon v-else class="dv-icon-view-sm">
                    <View />
                  </el-icon>
                  {{ data.label }}
                </span>
              </template>
            </el-tree>
          </div>

          <!-- 右侧详情 -->
          <div class="dv-detail">
            <div v-if="!dvSelected" class="dv-empty">
              <el-empty description="请选择左侧的表或视图查看详情" />
            </div>
            <div v-else class="dv-detail-inner">
              <!-- 上半部分：DDL -->
              <div class="dv-section">
                <div class="dv-section-header">
                  <span>
                    创建脚本（{{ dvDdlType === 'view' ? '视图' : '表' }}）
                    <el-tag size="small" type="info" style="margin-left: 8px">
                      {{ dvSelected.database }}.{{ dvSelected.schema }}.{{ dvSelected.table }}
                    </el-tag>
                  </span>
                </div>
                <div class="dv-ddl-box" v-loading="dvDdlLoading">
                  <Codemirror
                    :model-value="dvDdl"
                    :extensions="[sql()]"
                    theme="dark"
                    :editable="false"
                    style="height: 100%"
                  />
                </div>
              </div>

              <!-- 下半部分：数据预览 -->
              <div class="dv-section">
                <div class="dv-section-header">
                  <span>
                    数据预览
                    <span v-if="dvData" style="margin-left: 8px; color: #909399; font-size: 12px">
                      显示前 {{ dvData.returned }} 行，共 {{ dvData.total }} 行
                    </span>
                  </span>
                </div>
                <div class="dv-data-box" v-loading="dvDataLoading">
                  <el-table
                    v-if="dvData"
                    :data="dvData.rows"
                    size="small"
                    stripe
                    border
                    height="100%"
                    empty-text="暂无数据"
                  >
                    <el-table-column
                      v-for="col in dvData.columns"
                      :key="col"
                      :prop="col"
                      :label="col"
                      min-width="120"
                      show-overflow-tooltip
                    />
                  </el-table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Runs -->
      <el-tab-pane label="运行历史" name="runs">
        <el-table :data="runs" v-loading="loading" stripe empty-text="暂无运行记录">
          <el-table-column prop="id" label="#" width="60" />
          <el-table-column prop="run_type" label="类型" width="100" />
          <el-table-column prop="selection" label="选择" min-width="160" show-overflow-tooltip />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTag(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始" width="170">
            <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openLog(row)">查看日志</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建模型 -->
    <el-dialog v-model="modelCreate" title="新建模型" width="620px">
      <el-form label-width="70px">
        <el-form-item label="名称" required>
          <el-input v-model="modelForm.name" placeholder="模型名（不含 .sql）" />
        </el-form-item>
        <el-form-item label="层级">
          <el-select v-model="modelForm.subdir" style="width: 100%">
            <el-option
              v-for="layer in modelLayerOptions"
              :key="layer.value"
              :label="layer.label"
              :value="layer.value"
            />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            不同层级对应不同的数据库（stage_db / core_db / mart_db）
          </div>
        </el-form-item>
        <el-form-item label="SQL">
          <SqlEditor v-model="modelForm.sql" height="200px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelCreate = false">取消</el-button>
        <el-button type="primary" @click="submitModel">创建</el-button>
      </template>
    </el-dialog>

    <!-- 模型编辑器 -->
    <el-dialog v-model="modelEdit" :title="`编辑模型：${editForm.originalName}`" width="720px">
      <el-form label-width="70px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="物化">
          <el-select v-model="editForm.materialized" style="width: 200px">
            <el-option v-for="m in MATERIALIZED" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="SQL">
          <SqlEditor v-model="editForm.sql" height="280px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelEdit = false">取消</el-button>
        <el-button type="primary" @click="saveModel">保存</el-button>
      </template>
    </el-dialog>

    <!-- 测试编辑器（新建/编辑共用） -->
    <el-dialog
      v-model="testEdit"
      :title="testForm.testId === null ? '新建测试' : `编辑测试：${testForm.name}`"
      width="720px"
    >
      <el-form label-width="70px">
        <el-form-item label="名称" required>
          <el-input v-model="testForm.name" placeholder="测试名（不含 .sql）" />
        </el-form-item>
        <el-form-item label="SQL">
          <SqlEditor v-model="testForm.sql" height="220px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testEdit = false">取消</el-button>
        <el-button type="primary" @click="saveTest">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑数据源 -->
    <el-dialog
      v-model="sourceDialogVisible"
      :title="sourceDialogMode === 'create' ? '新建数据源' : '编辑数据源'"
      width="520px"
    >
      <el-form label-width="80px">
        <el-form-item label="源名称" required>
          <el-input v-model="sourceForm.source_name" placeholder="如：sales_db" />
        </el-form-item>
        <el-form-item label="保存目录">
          <el-select v-model="sourceForm.subdir" style="width: 100%">
            <el-option
              v-for="layer in SOURCE_DIRS"
              :key="layer.value"
              :label="layer.label"
              :value="layer.value"
            />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            sources.yml 保存到 models/ 下的哪个子目录
          </div>
        </el-form-item>
        <el-form-item label="数据库">
          <el-input v-model="sourceForm.database" placeholder="数据库名" />
        </el-form-item>
        <el-form-item label="Schema">
          <el-input v-model="sourceForm.schema" placeholder="如：dbo / public" />
        </el-form-item>
        <el-form-item label="加载器">
          <el-input v-model="sourceForm.loader" placeholder="如：postgres / sqlserver" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="sourceForm.description"
            type="textarea"
            :rows="3"
            placeholder="可选"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSource">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑表 -->
    <el-dialog
      v-model="tableDialogVisible"
      :title="tableDialogMode === 'add' ? '添加表' : '编辑表'"
      width="520px"
    >
      <el-form label-width="80px">
        <el-form-item label="表名" required>
          <el-input v-model="tableForm.name" placeholder="表名" />
        </el-form-item>
        <el-form-item label="标识符">
          <el-input v-model="tableForm.identifier" placeholder="物理表名，默认同表名" />
          <div style="font-size: 12px; color: #909399; margin-top: -10px">
            当物理表名与逻辑名不同时填写
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="tableForm.description"
            type="textarea"
            :rows="2"
            placeholder="可选"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tableDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTable">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分层配置列表 -->
    <el-dialog v-model="layersDialogVisible" title="分层配置" width="720px">
      <div class="layers-toolbar">
        <span>{{ layers.length }} 个分层</span>
        <div class="spacer" />
        <el-button type="primary" size="small" @click="openLayerCreate">
          新增分层
        </el-button>
      </div>
      <el-table :data="layers" stripe empty-text="暂无分层">
        <el-table-column label="层级名称" min-width="140">
          <template #default="{ row }">
            <strong>{{ row.display_name || row.name }}</strong>
            <el-tag v-if="row.is_root" size="small" type="info" style="margin-left: 6px">
              根目录
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="目录" min-width="120">
          <template #default="{ row }">
            {{ row.is_root ? 'models/' : `models/${row.name}/` }}
          </template>
        </el-table-column>
        <el-table-column label="目标数据库" min-width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.database || '—' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认物化" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.materialized }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openLayerEdit(row)">编辑</el-button>
            <el-button
              link
              type="danger"
              :disabled="row.is_root"
              @click="removeLayer(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="font-size: 12px; color: #909399; margin-top: 12px">
        说明：模型文件放在哪个目录，就自动写入对应数据库。新建模型时的「层级」选择器与这里同步。
      </div>
    </el-dialog>

    <!-- 新建/编辑分层 -->
    <el-dialog
      v-model="layerDialogVisible"
      :title="layerDialogMode === 'create' ? '新增分层' : '编辑分层'"
      width="520px"
    >
      <el-form label-width="90px">
        <el-form-item label="显示名称">
          <el-input v-model="layerForm.display_name" placeholder="如：Stage 层" />
          <div style="font-size: 12px; color: #909399; margin-top: -10px">
            友好显示名，可选
          </div>
        </el-form-item>
        <el-form-item label="目录名" :required="layerDialogMode === 'create'">
          <el-input
            v-model="layerForm.name"
            :disabled="layerDialogMode === 'edit' && editingLayerName === '__root__'"
            placeholder="如：staging / core / marts"
          />
          <div style="font-size: 12px; color: #909399; margin-top: -10px">
            models/ 下的子目录名，修改会重命名目录
          </div>
        </el-form-item>
        <el-form-item label="目标数据库">
          <el-input v-model="layerForm.database" placeholder="+database 配置" />
        </el-form-item>
        <el-form-item label="目标 Schema">
          <el-input v-model="layerForm.schema" placeholder="+schema 配置，可选" />
        </el-form-item>
        <el-form-item label="默认物化">
          <el-select v-model="layerForm.materialized" style="width: 100%">
            <el-option
              v-for="m in MATERIALIZED_OPTIONS"
              :key="m"
              :label="m"
              :value="m"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="layerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveLayer">保存</el-button>
      </template>
    </el-dialog>

    <!-- 连接配置 -->
    <el-dialog v-model="profilesDialog" title="连接配置（profiles.yml）" width="700px">
      <el-input
        v-model="profilesContent"
        type="textarea"
        :rows="16"
        class="mono"
        placeholder="编辑数据源连接配置…"
      />
      <template #footer>
        <el-button @click="profilesDialog = false">取消</el-button>
        <el-button type="primary" :loading="profilesSaving" @click="saveProfilesAction">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 运行日志 -->
    <el-dialog v-model="runLog.visible" :title="runLog.title" width="760px">
      <pre class="run-log">{{ runLog.log }}</pre>
    </el-dialog>

    <RunDialog
      ref="runDialog"
      :project-id="projectId"
      @done="onRunDone"
      @status="onNodeStatus"
      @running="onRunning"
    />
  </div>
</template>

<style scoped>
.page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}
.head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.head h2 {
  margin: 0;
  font-size: 22px;
}
.spacer {
  flex: 1;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  color: #909399;
}
.mono :deep(textarea) {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}
.run-log {
  margin: 0;
  max-height: 420px;
  overflow: auto;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-all;
}
/* Sources 布局 */
.sources-layout {
  display: flex;
  gap: 16px;
  min-height: 480px;
}
.sources-tree {
  width: 260px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 8px;
  background: #fafafa;
  overflow-y: auto;
  max-height: 600px;
}
.sources-detail {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px;
  background: #fff;
}
.tree-source,
.tree-table {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.tree-source {
  font-weight: 500;
}
.tree-table {
  color: #606266;
  font-size: 13px;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.detail-header h3 {
  margin: 0;
  font-size: 18px;
}
.detail-desc {
  margin-bottom: 20px;
}
.tables-section {
  margin-top: 8px;
}
.tables-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  font-weight: 500;
  color: #303133;
}
.empty-detail {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}
.layers-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  color: #909399;
}
/* 数据查看器 */
.data-viewer {
  display: flex;
  gap: 16px;
  min-height: 600px;
}
.dv-tree {
  width: 280px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 8px;
  background: #fafafa;
  overflow-y: auto;
  max-height: 700px;
  display: flex;
  flex-direction: column;
}
.dv-tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 4px 8px;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 4px;
}
.dv-tree-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}
.dv-tree-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.dv-icon-db {
  color: #409eff;
}
.dv-icon-table {
  color: #67c23a;
}
.dv-icon-view {
  color: #e6a23c;
}
.dv-icon-table-sm,
.dv-icon-view-sm {
  font-size: 12px;
  color: #909399;
}
.dv-detail {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}
.dv-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}
.dv-detail-inner {
  display: flex;
  flex-direction: column;
  height: 700px;
}
.dv-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  border-bottom: 1px solid #e4e7ed;
}
.dv-section:last-child {
  border-bottom: none;
}
.dv-section-header {
  padding: 10px 16px;
  font-weight: 500;
  color: #303133;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 14px;
}
.dv-ddl-box {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.dv-ddl-box :deep(.cm-editor) {
  height: 100%;
  font-size: 12px;
}
.dv-data-box {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 8px;
}
</style>
