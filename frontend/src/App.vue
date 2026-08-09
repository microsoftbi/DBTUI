<script setup lang="ts">
// 应用外壳：顶部导航 + 路由视图
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">DBT UI</div>
    </header>
    <main class="content">
      <router-view />
    </main>
  </div>
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
.content {
  padding-bottom: 40px;
}
</style>
