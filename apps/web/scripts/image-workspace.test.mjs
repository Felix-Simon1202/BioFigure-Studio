import assert from 'node:assert/strict'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToString } from 'react-dom/server'
import { createServer } from 'vite'

test('an empty image workspace renders without dereferencing a missing asset', async () => {
  const server = await createServer({
    root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  })
  try {
    const { default: ImageWorkspace } = await server.ssrLoadModule('/src/ImageWorkspace.tsx')
    const html = renderToString(createElement(ImageWorkspace, { onBack() {} }))
    assert.match(html, /图像工作台/)
    assert.match(html, /打开图像项目/)
    assert.doesNotMatch(html, /测量所选区域/)
  } finally {
    await server.close()
  }
})
