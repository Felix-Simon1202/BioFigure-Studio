/* oxlint-disable react/only-export-components -- The locale context intentionally shares its provider, hook, and pure translator. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Locale = 'en' | 'zh-CN'
export const LOCALE_STORAGE_KEY = 'biofigure.ui.locale'

export function translate(locale: Locale, zh: string, en: string): string {
  return locale === 'zh-CN' ? zh : en
}

function readLocale(): Locale {
  try {
    return window.localStorage.getItem(LOCALE_STORAGE_KEY) === 'zh-CN' ? 'zh-CN' : 'en'
  } catch {
    return 'en'
  }
}

type LanguageContextValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (zh: string, en: string) => string
}

const LanguageContext = createContext<LanguageContextValue>({
  locale: 'en',
  setLocale: () => {},
  t: (zh, en) => translate('en', zh, en),
})

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, updateLocale] = useState<Locale>(readLocale)
  const setLocale = useCallback((next: Locale) => {
    if (next !== 'en' && next !== 'zh-CN') return
    updateLocale(next)
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next)
    } catch {
      // The current session remains usable when persistence is unavailable.
    }
  }, [])
  useEffect(() => { document.documentElement.lang = locale }, [locale])
  const value = useMemo(() => ({ locale, setLocale, t: (zh: string, en: string) => translate(locale, zh, en) }), [locale, setLocale])
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useI18n() { return useContext(LanguageContext) }
