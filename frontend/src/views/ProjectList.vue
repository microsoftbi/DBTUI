<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createProject,
  deleteProject,
  listProjects,
  updateProject,
} from '@/api/projects'
import type { Project } from '@/types'

const { t } = useI18n()
const router = useRouter()

const ADAPTERS = ['sqlserver', 'postgres', 'snowflake', 'bigquery']

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
    ElMessage.warning(t('projectList.enterName'))
    return
  }
  saving.value = true
  try {
    if (editingId.value === null) {
      await createProject({ ...form })
      ElMessage.success(t('projectList.created'))
    } else {
      await updateProject(editingId.value, { ...form })
      ElMessage.success(t('projectList.updated'))
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row: Project) {
  await ElMessageBox.confirm(
    t('projectList.deleteConfirm', { name: row.name }),
    t('projectList.deleteTitle'),
    { type: 'warning', confirmButtonText: t('common.delete'), cancelButtonText: t('common.cancel') },
  )
  await deleteProject(row.id)
  ElMessage.success(t('projectList.deleted'))
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
        <h1>{{ t('projectList.title') }}</h1>
        <p class="subtitle">{{ t('projectList.subtitle') }}</p>
      </div>
      <el-button type="primary" @click="openCreate">{{ t('projectList.newProject') }}</el-button>
    </header>

    <el-table
      v-loading="loading"
      :data="projects"
      stripe
      :empty-text="t('projectList.noProjects')"
    >
      <el-table-column :prop="'name'" :label="t('projectList.projectName')" min-width="160" />
      <el-table-column :prop="'slug'" :label="t('projectList.slug')" min-width="140" />
      <el-table-column :prop="'adapter'" :label="t('projectList.adapter')" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ row.adapter }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column
        :prop="'dbt_version'"
        :label="t('projectList.dbtVersion')"
        width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ row.dbt_version || '-' }}
        </template>
      </el-table-column>
      <el-table-column :prop="'description'" :label="t('projectList.description')" min-width="160" show-overflow-tooltip />
      <el-table-column :label="t('projectList.createdAt')" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column :label="t('projectList.actions')" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/projects/${row.id}`)">
            {{ t('projectList.open') }}
          </el-button>
          <el-button link type="primary" @click="openEdit(row)">{{ t('projectList.edit') }}</el-button>
          <el-button link type="danger" @click="remove(row)">{{ t('projectList.delete') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建 / 编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? t('projectList.newProject') : t('projectList.editProject')"
      width="520px"
    >
      <el-form label-width="90px">
        <el-form-item :label="t('projectList.projectName')" required>
          <el-input v-model="form.name" :placeholder="t('projectList.placeholderName')" />
        </el-form-item>
        <el-form-item :label="t('projectList.adapter')">
          <el-select v-model="form.adapter" style="width: 100%">
            <el-option
              v-for="a in ADAPTERS"
              :key="a"
              :label="a"
              :value="a"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('projectList.description')">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            :placeholder="t('projectList.placeholderDesc')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="submit">{{ t('common.confirm') }}</el-button>
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
