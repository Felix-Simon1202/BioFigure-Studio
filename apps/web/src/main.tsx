import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import Screen from './Screen'
import { LanguageProvider } from './i18n'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LanguageProvider><Screen /></LanguageProvider>
  </StrictMode>,
)
