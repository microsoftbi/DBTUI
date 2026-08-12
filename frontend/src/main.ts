import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'

import App from './App.vue'
import router from './router'
import i18n, { getLocale } from './i18n'
import './style.css'

const app = createApp(App)

// 根据当前语言设置 Element Plus locale
const epLocale = getLocale() === 'zh' ? zhCn : en

app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(ElementPlus, { locale: epLocale })

app.mount('#app')
