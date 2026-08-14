<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
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
  createMacro,
  deleteMacro,
  getMacroSql,
  listMacros,
  updateMacro,
  type Macro,
} from '@/api/macros'
import {
  createSnapshot,
  deleteSnapshot,
  getSnapshotSql,
  listSnapshots,
  updateSnapshot,
  type Snapshot,
} from '@/api/snapshots'
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
const { t } = useI18n()
const projectId = Number(route.params.id)

const project = ref<Project | null>(null)
const models = ref<Model[]>([])
const tests = ref<Test[]>([])
const snapshots = ref<Snapshot[]>([])
const macros = ref<Macro[]>([])
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
      ElMessage.error(t('projectDetail.projectNotFound'))
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
async function loadMacros() {
  macros.value = (await listMacros(projectId)).data
}
async function loadSnapshots() {
  snapshots.value = (await listSnapshots(projectId)).data
}
async function loadRuns() {
  runs.value = (await listRuns(projectId)).data
}
async function load() {
  loading.value = true
  try {
    await Promise.all([loadModels(), loadTests(), loadSnapshots(), loadMacros(), loadSources(), loadLayers(), loadRuns()])
  } finally {
    loading.value = false
  }
}

async function doParse() {
  loading.value = true
  try {
    await parseProject(projectId)
    ElMessage.success(t('projectDetail.parseSuccess'))
    dagVersion.value++
    await load()
  } finally {
    loading.value = false
  }
}

// ---------- 运行 ----------
function openRun(selection: string, runType: 'run' | 'test' | 'compile' | 'build' | 'snapshot') {
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
  openRun(payload.selection, payload.runType as 'run' | 'test' | 'compile' | 'build' | 'snapshot')
}

// ---------- Model CRUD ----------
const modelCreate = ref(false)
const modelForm = ref({ name: '', sql: 'SELECT 1 AS id\n', subdir: 'staging' })
async function submitModel() {
  if (!modelForm.value.name.trim()) {
    ElMessage.warning(t('dialog.enterModelName'))
    return
  }
  await createModel(projectId, { ...modelForm.value })
  ElMessage.success(t('dialog.modelCreated'))
  modelCreate.value = false
  modelForm.value = { name: '', sql: 'SELECT 1 AS id\n', subdir: 'staging' }
  dagVersion.value++
  await loadModels()
}
async function removeModel(model: Model) {
  await ElMessageBox.confirm(t('dialog.modelDeleteConfirm', { name: model.name }), t('dialog.modelDeleteTitle'), {
    type: 'warning',
  })
  await deleteModel(projectId, model.id)
  ElMessage.success(t('dialog.modelDeleted'))
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
  ElMessage.success(t('dialog.modelSaved'))
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
    ElMessage.warning(t('dialog.enterTestName'))
    return
  }
  if (testForm.value.testId === null) {
    await createTest(projectId, { name: testForm.value.name, sql: testForm.value.sql })
    ElMessage.success(t('dialog.testCreated'))
  } else {
    await deleteTest(projectId, testForm.value.testId) // singular test 用删除重建方式
    await createTest(projectId, { name: testForm.value.name, sql: testForm.value.sql })
    ElMessage.success(t('dialog.testSaved'))
  }
  testEdit.value = false
  dagVersion.value++
  await loadTests()
}
async function removeTest(test: Test) {
  await ElMessageBox.confirm(t('dialog.testDeleteConfirm', { name: test.name }), t('dialog.testDeleteTitle'), {
    type: 'warning',
  })
  await deleteTest(projectId, test.id)
  ElMessage.success(t('dialog.testDeleted'))
  dagVersion.value++
  await loadTests()
}

// ---------- Macro CRUD ----------
const macroEdit = ref(false)
const macroForm = ref({
  macroId: null as number | null,
  name: '',
  sql: '{% macro example_macro() %}\n  SELECT 1\n{% endmacro %}\n',
  subdir: '',
  originalName: '',
})
function openMacroCreate() {
  macroForm.value = {
    macroId: null,
    name: '',
    sql: '{% macro example_macro() %}\n  SELECT 1\n{% endmacro %}\n',
    subdir: '',
    originalName: '',
  }
  macroEdit.value = true
}
async function openMacroEdit(macro: Macro) {
  const res = await getMacroSql(projectId, macro.id)
  macroForm.value = {
    macroId: macro.id,
    name: res.data.name,
    sql: res.data.sql,
    subdir: '',
    originalName: res.data.name,
  }
  macroEdit.value = true
}
async function saveMacro() {
  if (!macroForm.value.name.trim()) {
    ElMessage.warning(t('dialog.enterMacroName'))
    return
  }
  if (macroForm.value.macroId === null) {
    await createMacro(projectId, {
      name: macroForm.value.name,
      sql: macroForm.value.sql,
      subdir: macroForm.value.subdir,
    })
    ElMessage.success(t('dialog.macroCreated'))
  } else {
    await updateMacro(projectId, macroForm.value.macroId, {
      name: macroForm.value.name,
      sql: macroForm.value.sql,
    })
    ElMessage.success(t('dialog.macroSaved'))
  }
  macroEdit.value = false
  dagVersion.value++
  await loadMacros()
}
async function removeMacro(macro: Macro) {
  await ElMessageBox.confirm(
    t('dialog.macroDeleteConfirm', { name: macro.name }),
    t('dialog.macroDeleteTitle'),
    { type: 'warning' },
  )
  await deleteMacro(projectId, macro.id)
  ElMessage.success(t('dialog.macroDeleted'))
  dagVersion.value++
  await loadMacros()
}

// ---------- Snapshot CRUD ----------
const snapshotEdit = ref(false)
const snapshotForm = ref({
  snapshotId: null as number | null,
  name: '',
  sql: `{% snapshot snapshot_name %}

{{
    config(
      target_schema='snapshots',
      unique_key='id',
      strategy='timestamp',
      updated_at='updated_at',
    )
}}

select * from {{ ref('source_table') }}

{% endsnapshot %}
`,
  originalName: '',
})
function openSnapshotCreate() {
  snapshotForm.value = {
    snapshotId: null,
    name: '',
    sql: `{% snapshot snapshot_name %}

{{
    config(
      target_schema='snapshots',
      unique_key='id',
      strategy='timestamp',
      updated_at='updated_at',
    )
}}

select * from {{ ref('source_table') }}

{% endsnapshot %}
`,
    originalName: '',
  }
  snapshotEdit.value = true
}
async function openSnapshotEdit(snapshot: Snapshot) {
  const res = await getSnapshotSql(projectId, snapshot.id)
  snapshotForm.value = {
    snapshotId: snapshot.id,
    name: res.data.name,
    sql: res.data.sql,
    originalName: res.data.name,
  }
  snapshotEdit.value = true
}
async function saveSnapshot() {
  if (!snapshotForm.value.name.trim()) {
    ElMessage.warning(t('dialog.enterSnapshotName'))
    return
  }
  if (snapshotForm.value.snapshotId === null) {
    await createSnapshot(projectId, {
      name: snapshotForm.value.name,
      sql: snapshotForm.value.sql,
    })
    ElMessage.success(t('dialog.snapshotCreated'))
  } else {
    await updateSnapshot(projectId, snapshotForm.value.snapshotId, {
      name: snapshotForm.value.name,
      sql: snapshotForm.value.sql,
    })
    ElMessage.success(t('dialog.snapshotSaved'))
  }
  snapshotEdit.value = false
  dagVersion.value++
  await loadSnapshots()
}
async function removeSnapshot(snapshot: Snapshot) {
  await ElMessageBox.confirm(
    t('dialog.snapshotDeleteConfirm', { name: snapshot.name }),
    t('dialog.snapshotDeleteTitle'),
    { type: 'warning' },
  )
  await deleteSnapshot(projectId, snapshot.id)
  ElMessage.success(t('dialog.snapshotDeleted'))
  dagVersion.value++
  await loadSnapshots()
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
const sourceDirOptions = computed(() => [
  { value: 'staging', label: t('dialog.dirStaging') },
  { value: 'core', label: t('dialog.dirCore') },
  { value: 'marts', label: t('dialog.dirMarts') },
  { value: '', label: t('dialog.dirRoot') },
])
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
    ElMessage.warning(t('dialog.enterSourceName'))
    return
  }
  if (sourceDialogMode.value === 'create') {
    await createSource(projectId, { ...sourceForm.value, tables: [] })
    ElMessage.success(t('dialog.sourceCreated'))
  } else {
    await updateSource(projectId, activeSource.value, { ...sourceForm.value })
    ElMessage.success(t('dialog.sourceSaved'))
  }
  sourceDialogVisible.value = false
  dagVersion.value++
  await loadSources()
  await loadModels()
}

async function removeSource() {
  if (!currentSource.value) return
  await ElMessageBox.confirm(
    t('dialog.sourceDeleteConfirm', { name: currentSource.value.source_name }),
    t('dialog.sourceDeleteTitle'),
    { type: 'warning' },
  )
  await deleteSource(projectId, currentSource.value.source_name)
  ElMessage.success(t('dialog.sourceDeleted'))
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
    ElMessage.warning(t('dialog.enterTableName'))
    return
  }
  if (!currentSource.value) return
  if (tableDialogMode.value === 'add') {
    await addSourceTable(projectId, currentSource.value.source_name, {
      ...tableForm.value,
    })
    ElMessage.success(t('dialog.tableAdded'))
  } else {
    await updateSourceTable(
      projectId,
      currentSource.value.source_name,
      editingTableName.value,
      { ...tableForm.value },
    )
    ElMessage.success(t('dialog.tableSaved'))
  }
  tableDialogVisible.value = false
  dagVersion.value++
  await loadSources()
  await loadModels()
}

async function removeTable(table: SourceTable) {
  if (!currentSource.value) return
  await ElMessageBox.confirm(t('dialog.tableDeleteConfirm', { name: table.name }), t('dialog.tableDeleteTitle'), {
    type: 'warning',
  })
  await deleteSourceTable(projectId, currentSource.value.source_name, table.name)
  ElMessage.success(t('dialog.tableDeleted'))
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
    ElMessage.warning(t('dialog.enterLayerName'))
    return
  }
  if (layerDialogMode.value === 'create') {
    await createLayer(projectId, { ...layerForm.value })
    ElMessage.success(t('dialog.layerCreated'))
  } else {
    await updateLayer(projectId, editingLayerName.value, { ...layerForm.value })
    ElMessage.success(t('dialog.layerSaved'))
  }
  layerDialogVisible.value = false
  dagVersion.value++
  await loadLayers()
  await loadModels()
}

async function removeLayer(layer: LayerDefinition) {
  if (layer.is_root) {
    ElMessage.warning(t('dialog.rootCannotDelete'))
    return
  }
  await ElMessageBox.confirm(
    t('dialog.layerDeleteConfirm', { name: layer.display_name || layer.name }),
    t('dialog.layerDeleteTitle'),
    { type: 'warning' },
  )
  await deleteLayer(projectId, layer.name)
  ElMessage.success(t('dialog.layerDeleted'))
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
    opts.push({ value: '', label: t('dialog.dirRoot'), database: root.database || '—' })
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
    title: t('projectDetail.runLogTitle', { id: run.id, type: run.run_type, selection: run.selection || t('projectDetail.runAll') }),
    log: res.data.log || t('projectDetail.runNoLog'),
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
    ElMessage.success(t('dialog.connectionSaved'))
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
  ElMessage.success(t('projectDetail.dvRefreshed'))
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
        label: t('common.table'),
        type: 'folder',
        icon: 'table',
        database: data.database,
        tableType: 'table',
      },
      {
        key: `db:${data.database}:views`,
        label: t('common.view'),
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
      <el-button link @click="router.push('/')">{{ t('projectDetail.back') }}</el-button>
      <h2>{{ project?.name ?? t('projectDetail.loading') }}</h2>
      <el-tag v-if="project" size="small" type="info">{{ project.adapter }}</el-tag>
      <el-tag
        v-if="project"
        size="small"
        :type="project.parse_status === 'success' ? 'success' : 'info'"
      >
        {{ project.parse_status || t('projectDetail.notParsed') }}
      </el-tag>
      <div class="spacer" />
      <el-button @click="openLayersDialog">{{ t('projectDetail.layerConfig') }}</el-button>
      <el-button @click="openProfiles">{{ t('projectDetail.connectionConfig') }}</el-button>
      <el-button :loading="loading" @click="doParse">{{ t('projectDetail.reparse') }}</el-button>
    </div>

    <el-tabs v-model="activeTab">
      <!-- Models -->
      <el-tab-pane :label="t('projectDetail.tabModels')" name="models">
        <div class="toolbar">
          <span>{{ t('projectDetail.modelCount', { count: models.length }) }}</span>
          <div class="spacer" />
          <el-button type="primary" @click="modelCreate = true">{{ t('projectDetail.newModel') }}</el-button>
        </div>
        <el-table :data="models" v-loading="loading" stripe :empty-text="t('projectDetail.noModels')">
          <el-table-column prop="name" :label="t('projectDetail.modelName')" min-width="140" />
          <el-table-column prop="database" :label="t('projectDetail.modelDatabase')" width="110">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.database }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="resource_type" :label="t('projectDetail.modelType')" width="100" />
          <el-table-column prop="materialized" :label="t('projectDetail.modelMaterialized')" width="110">
            <template #default="{ row }">
              <el-tag size="small">{{ row.materialized }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="file_path" :label="t('projectDetail.modelFile')" min-width="160" show-overflow-tooltip />
          <el-table-column :label="t('projectDetail.modelStatus')" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.run_status" size="small" :type="statusTag(row.run_status)">
                {{ row.run_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('projectDetail.modelActions')" width="250" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openModelEdit(row)">{{ t('projectDetail.modelEdit') }}</el-button>
              <el-button link type="primary" @click="openRun(row.name, 'run')">{{ t('projectDetail.modelRun') }}</el-button>
              <el-button link type="primary" @click="openRun(row.name, 'test')">{{ t('projectDetail.modelTest') }}</el-button>
              <el-button link type="danger" @click="removeModel(row)">{{ t('projectDetail.modelDelete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Sources -->
      <el-tab-pane :label="t('projectDetail.tabSources')" name="sources">
        <div class="toolbar">
          <span>{{ t('projectDetail.sourceCount', { count: sources.length }) }}</span>
          <div class="spacer" />
          <el-button type="primary" @click="openSourceCreate">{{ t('projectDetail.newSource') }}</el-button>
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
              :empty-text="t('projectDetail.noSources')"
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
              <el-empty :description="t('projectDetail.selectSource')" />
            </div>
            <div v-else>
              <div class="detail-header">
                <h3>{{ currentSource.source_name }}</h3>
                <div class="spacer" />
                <el-button link type="primary" @click="openSourceEdit">{{ t('projectDetail.sourceEdit') }}</el-button>
                <el-button link type="danger" @click="removeSource">{{ t('projectDetail.sourceDelete') }}</el-button>
              </div>
              <el-descriptions :column="2" border size="small" class="detail-desc">
                <el-descriptions-item :label="t('projectDetail.saveDir')">
                  <el-tag size="small" type="info">
                    {{ currentSource.subdir || t('common.root') }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item :label="t('common.database')">
                  {{ currentSource.database || '-' }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('common.schema')">
                  {{ currentSource.schema || '-' }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('projectDetail.loader')">
                  {{ currentSource.loader || '-' }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('common.description')" :span="2">
                  {{ currentSource.description || '-' }}
                </el-descriptions-item>
              </el-descriptions>

              <div class="tables-section">
                <div class="tables-header">
                  <span>{{ t('projectDetail.tableList', { count: currentSource.tables.length }) }}</span>
                  <div class="spacer" />
                  <el-button size="small" type="primary" @click="openTableAdd">
                    {{ t('projectDetail.addTable') }}
                  </el-button>
                </div>
                <el-table :data="currentSource.tables" stripe size="small" :empty-text="t('projectDetail.noTables')">
                  <el-table-column prop="name" :label="t('projectDetail.tableName')" min-width="140" />
                  <el-table-column prop="identifier" :label="t('projectDetail.tableIdentifier')" min-width="140">
                    <template #default="{ row }">
                      {{ row.identifier || row.name }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="description" :label="t('projectDetail.tableDesc')" min-width="160" show-overflow-tooltip />
                  <el-table-column :label="t('common.operation')" width="150" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="primary" @click="openTableEdit(row)">{{ t('projectDetail.tableEdit') }}</el-button>
                      <el-button link type="danger" @click="removeTable(row)">{{ t('projectDetail.tableDelete') }}</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tests -->
      <el-tab-pane :label="t('projectDetail.tabTests')" name="tests">
        <div class="toolbar">
          <span>{{ t('projectDetail.testCount', { count: tests.length }) }}</span>
          <div class="spacer" />
          <el-button type="primary" @click="openTestCreate">{{ t('projectDetail.newTest') }}</el-button>
        </div>
        <el-table :data="tests" v-loading="loading" stripe :empty-text="t('projectDetail.noTests')">
          <el-table-column prop="name" :label="t('projectDetail.testName')" min-width="180" />
          <el-table-column prop="type" :label="t('projectDetail.testType')" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="row.type === 'singular' ? 'warning' : ''">
                {{ row.type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="severity" :label="t('projectDetail.testSeverity')" width="100" />
          <el-table-column :label="t('projectDetail.testStatus')" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.run_status" size="small" :type="statusTag(row.run_status)">
                {{ row.run_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('projectDetail.testActions')" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openTestEdit(row)">{{ t('projectDetail.testEdit') }}</el-button>
              <el-button link type="primary" @click="openRun(row.name, 'test')">{{ t('projectDetail.testRun') }}</el-button>
              <el-button link type="danger" @click="removeTest(row)">{{ t('projectDetail.testDelete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Snapshots -->
      <el-tab-pane :label="t('projectDetail.tabSnapshots')" name="snapshots">
        <div class="toolbar">
          <span>{{ t('projectDetail.snapshotCount', { count: snapshots.length }) }}</span>
          <div class="spacer" />
          <el-button type="primary" @click="openSnapshotCreate">{{ t('projectDetail.newSnapshot') }}</el-button>
        </div>
        <el-table :data="snapshots" v-loading="loading" stripe :empty-text="t('projectDetail.noSnapshots')">
          <el-table-column prop="name" :label="t('projectDetail.snapshotName')" min-width="200" />
          <el-table-column prop="snapshot_strategy" :label="t('projectDetail.snapshotStrategy')" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.snapshot_strategy" size="small" :type="row.snapshot_strategy === 'timestamp' ? 'success' : 'warning'">
                {{ row.snapshot_strategy }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="target_schema" :label="t('projectDetail.snapshotTargetSchema')" width="140">
            <template #default="{ row }">
              {{ row.target_schema || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="unique_key" :label="t('projectDetail.snapshotUniqueKey')" width="140" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.unique_key || '-' }}
            </template>
          </el-table-column>
          <el-table-column :label="t('projectDetail.snapshotDbSchema')" width="180">
            <template #default="{ row }">
              {{ row.database ? row.database + '.' : '' }}{{ row.schema_name || '-' }}
            </template>
          </el-table-column>
          <el-table-column :label="t('projectDetail.snapshotStatus')" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.run_status" size="small" :type="statusTag(row.run_status)">
                {{ row.run_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('projectDetail.snapshotActions')" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openSnapshotEdit(row)">{{ t('projectDetail.snapshotEdit') }}</el-button>
              <el-button link type="primary" @click="openRun(row.name, 'snapshot')">{{ t('projectDetail.snapshotRun') }}</el-button>
              <el-button link type="danger" @click="removeSnapshot(row)">{{ t('projectDetail.snapshotDelete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Macros -->
      <el-tab-pane :label="t('projectDetail.tabMacros')" name="macros">
        <div class="toolbar">
          <span>{{ t('projectDetail.macroCount', { count: macros.length }) }}</span>
          <div class="spacer" />
          <el-button type="primary" @click="openMacroCreate">{{ t('projectDetail.newMacro') }}</el-button>
        </div>
        <el-table :data="macros" v-loading="loading" stripe :empty-text="t('projectDetail.noMacros')">
          <el-table-column prop="name" :label="t('projectDetail.macroName')" min-width="200" />
          <el-table-column prop="file_path" :label="t('projectDetail.macroFile')" min-width="240" />
          <el-table-column :label="t('projectDetail.macroActions')" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openMacroEdit(row)">{{ t('projectDetail.macroEdit') }}</el-button>
              <el-button link type="danger" @click="removeMacro(row)">{{ t('projectDetail.macroDelete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- DAG -->
      <el-tab-pane :label="t('projectDetail.tabDag')" name="dag">
        <DagGraph
          :project-id="projectId"
          :refresh-key="dagVersion"
          :live-status="liveStatuses"
          @run="onDagRun"
        />
      </el-tab-pane>

      <!-- 数据查看器 -->
      <el-tab-pane :label="t('projectDetail.tabDataViewer')" name="data-viewer">
        <div class="data-viewer" v-loading="dvLoading">
          <!-- 左侧树 -->
          <div class="dv-tree">
            <div class="dv-tree-header">
              <span class="dv-tree-title">{{ t('projectDetail.dvDatabase') }}</span>
              <el-button
                size="small"
                :icon="Refresh"
                text
                @click="refreshDataViewer"
              >
                {{ t('projectDetail.dvRefresh') }}
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
              :empty-text="t('projectDetail.dvNoDatabase')"
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
              <el-empty :description="t('projectDetail.dvSelectTable')" />
            </div>
            <div v-else class="dv-detail-inner">
              <!-- 上半部分：DDL -->
              <div class="dv-section">
                <div class="dv-section-header">
                  <span>
                    {{ t('projectDetail.dvDdl', { type: dvDdlType === 'view' ? t('common.view') : t('common.table') }) }}
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
                    {{ t('projectDetail.dvDataPreview') }}
                    <span v-if="dvData" style="margin-left: 8px; color: #909399; font-size: 12px">
                      {{ t('projectDetail.dvRowCount', { returned: dvData.returned, total: dvData.total }) }}
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
                    :empty-text="t('projectDetail.dvNoData')"
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
      <el-tab-pane :label="t('projectDetail.tabRuns')" name="runs">
        <el-table :data="runs" v-loading="loading" stripe :empty-text="t('projectDetail.runNoRecords')">
          <el-table-column prop="id" :label="t('projectDetail.runId')" width="60" />
          <el-table-column prop="run_type" :label="t('projectDetail.runType')" width="100" />
          <el-table-column prop="selection" :label="t('projectDetail.runSelection')" min-width="160" show-overflow-tooltip />
          <el-table-column :label="t('projectDetail.runStatus')" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTag(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('projectDetail.runStarted')" width="170">
            <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column :label="t('projectDetail.runActions')" width="110" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openLog(row)">{{ t('projectDetail.runViewLog') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建模型 -->
    <el-dialog v-model="modelCreate" :title="t('dialog.newModel')" width="620px">
      <el-form label-width="70px">
        <el-form-item :label="t('dialog.modelNameLabel')" required>
          <el-input v-model="modelForm.name" :placeholder="t('dialog.modelNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.modelLayer')">
          <el-select v-model="modelForm.subdir" style="width: 100%">
            <el-option
              v-for="layer in modelLayerOptions"
              :key="layer.value"
              :label="layer.label"
              :value="layer.value"
            />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            {{ t('dialog.modelLayerHint') }}
          </div>
        </el-form-item>
        <el-form-item :label="t('dialog.modelSql')">
          <SqlEditor v-model="modelForm.sql" height="200px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelCreate = false">{{ t('dialog.modelCancel') }}</el-button>
        <el-button type="primary" @click="submitModel">{{ t('dialog.modelCreate') }}</el-button>
      </template>
    </el-dialog>

    <!-- 模型编辑器 -->
    <el-dialog v-model="modelEdit" :title="t('dialog.editModel', { name: editForm.originalName })" width="720px">
      <el-form label-width="70px">
        <el-form-item :label="t('dialog.modelNameLabel')">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item :label="t('projectDetail.modelMaterialized')">
          <el-select v-model="editForm.materialized" style="width: 200px">
            <el-option v-for="m in MATERIALIZED" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('dialog.modelSql')">
          <SqlEditor v-model="editForm.sql" height="280px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelEdit = false">{{ t('dialog.modelCancel') }}</el-button>
        <el-button type="primary" @click="saveModel">{{ t('dialog.modelSave') }}</el-button>
      </template>
    </el-dialog>

    <!-- 测试编辑器（新建/编辑共用） -->
    <el-dialog
      v-model="testEdit"
      :title="testForm.testId === null ? t('dialog.newTest') : t('dialog.editTest', { name: testForm.name })"
      width="720px"
    >
      <el-form label-width="70px">
        <el-form-item :label="t('dialog.testNameLabel')" required>
          <el-input v-model="testForm.name" :placeholder="t('dialog.testNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.testSql')">
          <SqlEditor v-model="testForm.sql" height="220px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testEdit = false">{{ t('dialog.testCancel') }}</el-button>
        <el-button type="primary" @click="saveTest">{{ t('dialog.testSave') }}</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑 Macro -->
    <el-dialog
      v-model="macroEdit"
      :title="macroForm.macroId === null ? t('dialog.newMacro') : t('dialog.editMacro', { name: macroForm.originalName })"
      width="720px"
    >
      <el-form label-width="80px">
        <el-form-item :label="t('dialog.macroNameLabel')" required>
          <el-input v-model="macroForm.name" :placeholder="t('dialog.macroNamePlaceholder')" />
        </el-form-item>
        <el-form-item v-if="macroForm.macroId === null" :label="t('dialog.macroDir')">
          <el-input v-model="macroForm.subdir" :placeholder="t('dialog.macroDirPlaceholder')" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            {{ t('dialog.macroDirHint') }}
          </div>
        </el-form-item>
        <el-form-item :label="t('dialog.macroSql')">
          <SqlEditor v-model="macroForm.sql" height="280px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="macroEdit = false">{{ t('dialog.macroCancel') }}</el-button>
        <el-button type="primary" @click="saveMacro">{{ macroForm.macroId === null ? t('dialog.macroCreate') : t('dialog.macroSave') }}</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑 Snapshot -->
    <el-dialog
      v-model="snapshotEdit"
      :title="snapshotForm.snapshotId === null ? t('dialog.newSnapshot') : t('dialog.editSnapshot', { name: snapshotForm.originalName })"
      width="720px"
    >
      <el-form label-width="80px">
        <el-form-item :label="t('dialog.snapshotNameLabel')" required>
          <el-input v-model="snapshotForm.name" :placeholder="t('dialog.snapshotNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.snapshotSql')">
          <SqlEditor v-model="snapshotForm.sql" height="320px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="snapshotEdit = false">{{ t('dialog.snapshotCancel') }}</el-button>
        <el-button type="primary" @click="saveSnapshot">{{ snapshotForm.snapshotId === null ? t('dialog.snapshotCreate') : t('dialog.snapshotSave') }}</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑数据源 -->
    <el-dialog
      v-model="sourceDialogVisible"
      :title="sourceDialogMode === 'create' ? t('dialog.newSource') : t('dialog.editSource')"
      width="520px"
    >
      <el-form label-width="80px">
        <el-form-item :label="t('dialog.sourceName')" required>
          <el-input v-model="sourceForm.source_name" :placeholder="t('dialog.sourceNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.sourceSaveDir')">
          <el-select v-model="sourceForm.subdir" style="width: 100%">
            <el-option
              v-for="layer in sourceDirOptions"
              :key="layer.value"
              :label="layer.label"
              :value="layer.value"
            />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            {{ t('dialog.sourceSaveDirHint') }}
          </div>
        </el-form-item>
        <el-form-item :label="t('dialog.sourceDatabase')">
          <el-input v-model="sourceForm.database" :placeholder="t('dialog.sourceDatabasePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.sourceSchema')">
          <el-input v-model="sourceForm.schema" :placeholder="t('dialog.sourceSchemaPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.sourceLoader')">
          <el-input v-model="sourceForm.loader" :placeholder="t('dialog.sourceLoaderPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.sourceDesc')">
          <el-input
            v-model="sourceForm.description"
            type="textarea"
            :rows="3"
            :placeholder="t('dialog.sourceDescPlaceholder')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">{{ t('dialog.sourceCancel') }}</el-button>
        <el-button type="primary" @click="saveSource">{{ t('dialog.sourceSave') }}</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑表 -->
    <el-dialog
      v-model="tableDialogVisible"
      :title="tableDialogMode === 'add' ? t('dialog.addTable') : t('dialog.editTable')"
      width="520px"
    >
      <el-form label-width="80px">
        <el-form-item :label="t('dialog.tableNameLabel')" required>
          <el-input v-model="tableForm.name" :placeholder="t('dialog.tableNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.tableIdentifierLabel')">
          <el-input v-model="tableForm.identifier" :placeholder="t('dialog.tableIdentifierPlaceholder')" />
          <div style="font-size: 12px; color: #909399; margin-top: -10px">
            {{ t('dialog.tableIdentifierHint') }}
          </div>
        </el-form-item>
        <el-form-item :label="t('dialog.tableDescLabel')">
          <el-input
            v-model="tableForm.description"
            type="textarea"
            :rows="2"
            :placeholder="t('dialog.tableDescPlaceholder')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tableDialogVisible = false">{{ t('dialog.tableCancel') }}</el-button>
        <el-button type="primary" @click="saveTable">{{ t('dialog.tableSave') }}</el-button>
      </template>
    </el-dialog>

    <!-- 分层配置列表 -->
    <el-dialog v-model="layersDialogVisible" :title="t('dialog.layerConfig')" width="720px">
      <div class="layers-toolbar">
        <span>{{ t('dialog.layerCount', { count: layers.length }) }}</span>
        <div class="spacer" />
        <el-button type="primary" size="small" @click="openLayerCreate">
          {{ t('dialog.newLayer') }}
        </el-button>
      </div>
      <el-table :data="layers" stripe :empty-text="t('dialog.noLayers')">
        <el-table-column :label="t('dialog.layerName')" min-width="140">
          <template #default="{ row }">
            <strong>{{ row.display_name || row.name }}</strong>
            <el-tag v-if="row.is_root" size="small" type="info" style="margin-left: 6px">
              {{ t('dialog.layerRoot') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" :label="t('dialog.layerDir')" min-width="120">
          <template #default="{ row }">
            {{ row.is_root ? 'models/' : `models/${row.name}/` }}
          </template>
        </el-table-column>
        <el-table-column :label="t('dialog.layerTargetDb')" min-width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.database || '—' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('dialog.layerDefaultMat')" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.materialized }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('dialog.layerActions')" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openLayerEdit(row)">{{ t('dialog.layerEdit') }}</el-button>
            <el-button
              link
              type="danger"
              :disabled="row.is_root"
              @click="removeLayer(row)"
            >
              {{ t('dialog.layerDelete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="font-size: 12px; color: #909399; margin-top: 12px">
        {{ t('dialog.layerHint') }}
      </div>
    </el-dialog>

    <!-- 新建/编辑分层 -->
    <el-dialog
      v-model="layerDialogVisible"
      :title="layerDialogMode === 'create' ? t('dialog.newLayerTitle') : t('dialog.editLayerTitle')"
      width="520px"
    >
      <el-form label-width="90px">
        <el-form-item :label="t('dialog.layerDisplayName')">
          <el-input v-model="layerForm.display_name" :placeholder="t('dialog.layerDisplayNamePlaceholder')" />
          <div style="font-size: 12px; color: #909399; margin-top: -10px">
            {{ t('dialog.layerDisplayNameHint') }}
          </div>
        </el-form-item>
        <el-form-item :label="t('dialog.layerDirName')" :required="layerDialogMode === 'create'">
          <el-input
            v-model="layerForm.name"
            :disabled="layerDialogMode === 'edit' && editingLayerName === '__root__'"
            :placeholder="t('dialog.layerDirPlaceholder')"
          />
          <div style="font-size: 12px; color: #909399; margin-top: -10px">
            {{ t('dialog.layerDirHint') }}
          </div>
        </el-form-item>
        <el-form-item :label="t('dialog.layerTargetDbLabel')">
          <el-input v-model="layerForm.database" :placeholder="t('dialog.layerTargetDbPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.layerTargetSchema')">
          <el-input v-model="layerForm.schema" :placeholder="t('dialog.layerTargetSchemaPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dialog.layerDefaultMatLabel')">
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
        <el-button @click="layerDialogVisible = false">{{ t('dialog.layerCancel') }}</el-button>
        <el-button type="primary" @click="saveLayer">{{ t('dialog.layerSave') }}</el-button>
      </template>
    </el-dialog>

    <!-- 连接配置 -->
    <el-dialog v-model="profilesDialog" :title="t('dialog.connectionTitle')" width="700px">
      <el-input
        v-model="profilesContent"
        type="textarea"
        :rows="16"
        class="mono"
        :placeholder="t('dialog.connectionPlaceholder')"
      />
      <template #footer>
        <el-button @click="profilesDialog = false">{{ t('dialog.connectionCancel') }}</el-button>
        <el-button type="primary" :loading="profilesSaving" @click="saveProfilesAction">
          {{ t('dialog.connectionSave') }}
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
