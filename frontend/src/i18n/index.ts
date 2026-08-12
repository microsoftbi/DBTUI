import { createI18n } from 'vue-i18n'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import enEp from 'element-plus/es/locale/lang/en'
import en from './locales/en'
import zh from './locales/zh'

const STORAGE_KEY = 'dbt_ui_locale'

function getDefaultLocale(): string {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved && (saved === 'en' || saved === 'zh')) {
    return saved
  }
  return 'en'
}

const i18n = createI18n({
  legacy: false,
  locale: getDefaultLocale(),
  fallbackLocale: 'en',
  messages: {
    en,
    zh,
  },
})

export function setLocale(lang: 'en' | 'zh') {
  i18n.global.locale.value = lang
  localStorage.setItem(STORAGE_KEY, lang)
}

export function getLocale(): string {
  return i18n.global.locale.value
}

export function getElementPlusLocale(lang: string) {
  return lang === 'zh' ? zhCn : enEp
}

export default i18n
