import { createI18n } from 'vue-i18n'
import { useStore } from '@/composables/store'
import zh_CN from './locales/zh-CN.json'
import en_US from './locales/en-US.json'
import ar_KSA from './locales/Ar-KSA.json'
import ja_JP from './locales/Ja-ja.json'
import ur_IN from './locales/Ur-Urdu.json'
import hi_IN from './locales/hi-IN.json'
import kn_IN from './locales/ka-In.json'
import ta_IN from './locales/ta-IN.json'
import te_IN from './locales/te-IN.json'
import sp_SPA from './locales/sp-SPA.json'

const { options } = useStore()

const getLocale = (lang) => {
  const translations = options.value.translations[lang]
  if (typeof translations === 'object') {
    return translations
  }
  return {}
}

const deepMerge = (target, ...sources) => {
  if (typeof target !== 'object' || target === null) {
    target = {}
  }
  sources.forEach((source) => {
    if (source !== null && typeof source === 'object') {
      Object.keys(source).forEach((key) => {
        if (source[key] && typeof source[key] === 'object') {
          if (!target[key]) {
            target[key] = Array.isArray(source[key]) ? [] : {}
          }
          deepMerge(target[key], source[key])
        } else {
          target[key] = source[key]
        }
      })
    }
  })
  return target
}

const i18n = createI18n({
  legacy: false,
  locale: options.value.locale || 'en-US',
  defaultLocale: 'en-US',
  messages: {
    'en-US': deepMerge(en_US, getLocale('en_US')),
    'zh-CN': deepMerge(zh_CN, getLocale('zh_CN')),
    'ar-KSA': deepMerge(ar_KSA, getLocale('ar_KSA')),
    'ja-JP': deepMerge(ja_JP, getLocale('ja_JP')),
    'ur-IN': deepMerge(ur_IN, getLocale('ur_IN')),
    'hi-IN': deepMerge(hi_IN, getLocale('hi_IN')),
    'kn-IN': deepMerge(kn_IN, getLocale('kn_IN')),
    'ta-IN': deepMerge(ta_IN, getLocale('ta_IN')),
    'te-IN': deepMerge(te_IN, getLocale('te_IN')),
    'sp-SPA': deepMerge(sp_SPA, getLocale('sp_SPA')),
  },
})

export default i18n
