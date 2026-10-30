import { rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

// Os testes rodam num banco próprio e numa porta própria: nunca tocam em data/contas.db.
const PORT = 8010
const dataDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'test-results', 'e2e-data')
const python = process.platform === 'win32' ? '..\\.venv\\Scripts\\python.exe' : '../.venv/bin/python'
if (!process.env.TEST_WORKER_INDEX) rmSync(dataDir, { recursive: true, force: true })

export default defineConfig({
  testDir: './tests/e2e',
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: 'on-first-retry' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
    { name: 'mobile', use: { ...devices['iPhone 13'], browserName: 'chromium', channel: 'chrome' } },
  ],
  webServer: {
    command: `${python} -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    env: { DIVISAO_DATA_DIR: dataDir },
  },
})
