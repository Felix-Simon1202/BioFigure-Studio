import type { Locale } from './i18n'

export const BIODOT_NAME = 'Biodot'
export const biodotGreeting: Record<Locale, string> = {
  en: "Hi, I'm Biodot, your drawing assistant. Tell me what you want to show, and we'll work through the figure together.",
  'zh-CN': '你好，我是 Biodot，你的绘图助手。告诉我你想表达什么，我们一起把图做好。',
}

// Social replies are local UI text. They do not call a model or consume a
// provider request, and do not send user text to an external service.
export function biodotReply(input: string, locale: Locale): string | null {
  const text = input.trim().replace(/[.!！。?？]+$/u, '').trim().toLowerCase()
  if (/^(?:(?:hi|hello|hey|你好|您好|嗨)(?:[,，\s]+biodot)?|你是谁|你叫什么|who are you|what is your name)$/.test(text))
    return biodotGreeting[locale]
  if (/^(help|what can you do|你能做什么|帮助)$/.test(text))
    return locale === 'zh-CN'
      ? '我是 Biodot。我可以帮你准备受支持的合成图表草案、检查图像信息，并进入图版或图示编辑器。先核对草案，再由你确认执行；连接器能否使用取决于本机配置。'
      : "I'm Biodot. I can help prepare supported synthetic chart drafts, inspect image metadata, and guide you into figure or illustration editors. Review each draft before confirming it; connector availability depends on your local setup."
  return null
}
