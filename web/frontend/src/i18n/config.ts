/**
 * B-2: 多语言国际化配置
 *
 * 支持语言：zh-CN（默认）, en-US
 * 语言检测顺序：localStorage > 浏览器语言 > zh-CN
 */

import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import zhCN from './locales/zh-CN.json'
import enUS from './locales/en-US.json'

const resources = {
  'zh-CN': { translation: zhCN },
  'zh': { translation: zhCN },
  'en-US': { translation: enUS },
  'en': { translation: enUS },
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'zh-CN',
    supportedLngs: ['zh-CN', 'en-US', 'zh', 'en'],
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'kaelis_language',
      caches: ['localStorage'],
    },
  })

export default i18n
