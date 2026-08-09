<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createProject,
  deleteProject,
  listProjects,
  updateProject,
} from '@/api/projects'
import type { Project } from '@/types'

const router = useRouter()

const ADAPTERS = ['sqlserver', 'postgres', 'duckdb', 'snowflake', 'bigquery']

const projects = ref<Project[]>([])
const loading = ref(false)

// 新建/编辑弹窗状态
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const form = reactive({ name: '', adapter: 'postgres', description: '' })

async function load() {
  loading.value = true
  try {
    const res = await listProjects()
    projects.value = res.data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.adapter = 'postgres'
  form.description = ''
  dialogVisible.value = true
}

function openEdit(row: Project) {
  editingId.value = row.id
  form.name = row.name
  form.adapter = row.adapter
  form.description = row.description
  dialogVisible.value = true
}

async function submit() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value === null) {
      await createProject({ ...form })
      ElMessage.success('项目创建成功')
    } else {
      await updateProject(editingId.value, { ...form })
      ElMessage.success('项目已更新')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row: Project) {
  await ElMessageBox.confirm(
    `确定删除项目「${row.name}」？将同时删除磁盘上的 dbt 项目目录。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteProject(row.id)
  ElMessage.success('项目已删除')
  await load()
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>DBT 项目</h1>
        <p class="subtitle">创建和管理 DBT 项目</p>
      </div>
      <el-button type="primary" @click="openCreate">新建项目</el-button>
    </header>

    <el-table
      v-loading="loading"
      :data="projects"
      stripe
      empty-text="暂无项目，点击「新建项目」开始"
    >
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="slug" label="Slug" min-width="140" />
      <el-table-column prop="adapter" label="Adapter" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ row.adapter }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="dbt_version"
        label="dbt 版本"
        width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ row.dbt_version || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/projects/${row.id}`)">
            打开
          </el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建 / 编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新建项目' : '编辑项目'"
      width="520px"
    >
      <el-form label-width="90px">
        <el-form-item label="项目名称" required>
          <el-input v-model="form.name" placeholder="如：My Analytics" />
        </el-form-item>
        <el-form-item label="Adapter">
          <el-select v-model="form.adapter" style="width: 100%">
            <el-option
              v-for="a in ADAPTERS"
              :key="a"
              :label="a"
              :value="a"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="项目描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.page-header h1 {
  margin: 0;
  font-size: 24px;
}
.subtitle {
  margin: 4px 0 0;
  color: #909399;
}
</style>
