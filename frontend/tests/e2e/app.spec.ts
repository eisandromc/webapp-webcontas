import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('opens the financial dashboard and navigates', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Painel de custos' })).toBeVisible()
  await page.getByRole('link', { name: 'Lançamentos', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Todos os lançamentos' })).toBeVisible()
  await page.getByRole('link', { name: 'Histórico' }).click()
  await expect(page.getByRole('heading', { name: 'Histórico da casa' })).toBeVisible()
})

test('has no horizontal page overflow on mobile', async ({ page }) => {
  await page.goto('/')
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }))
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.client)
})

test('has no critical accessibility violations', async ({ page }) => {
  await page.goto('/')
  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.filter(violation => violation.impact === 'critical')).toEqual([])
})

test('adds, edits and removes a monthly entry with immediate refresh', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Mutation flow runs once per run against the isolated e2e database.')
  const bootstrap = await (await page.request.get('/api/bootstrap')).json()
  const period = bootstrap.current_period as string
  const original = `Teste E2E ${Date.now()}`
  const edited = `${original} editado`
  let entryId: number | undefined

  try {
    await page.goto(`/mes/${period}`)
    await page.getByRole('button', { name: 'Novo lançamento' }).click()
    const addPanel = page.getByRole('dialog', { name: 'Novo lançamento' })
    await addPanel.getByLabel('Descrição').fill(original)
    await addPanel.getByRole('textbox', { name: 'Valor' }).fill('12,34')
    await addPanel.getByRole('button', { name: 'Salvar', exact: true }).click()
    await expect(page.locator('#conteudo').getByText(original, { exact: true })).toBeVisible()

    const month = await (await page.request.get(`/api/months/${period}`)).json()
    entryId = month.entries.find((item: { description: string }) => item.description === original)?.id
    expect(entryId).toBeTruthy()

    await page.getByRole('button', { name: `Editar ${original}` }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('Descrição').fill(edited)
    await dialog.getByLabel('Valor').fill('23,45')
    await dialog.getByRole('button', { name: 'Salvar' }).click()
    await expect(page.locator('#conteudo').getByText(edited, { exact: true })).toBeVisible()
    await expect(page.getByText('R$ 23,45', { exact: true }).first()).toBeVisible()

    await page.getByRole('button', { name: `Excluir ${edited}` }).click()
    await page.getByRole('dialog', { name: 'Excluir item' }).getByRole('button', { name: 'Excluir', exact: true }).click()
    await expect(page.locator('#conteudo').getByText(edited, { exact: true })).toHaveCount(0)
    entryId = undefined
  } finally {
    if (entryId) await page.request.delete(`/api/entries/${entryId}`)
  }
})

test('a closed month locks its records', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Mutation flow runs once per run against the isolated e2e database.')
  const period = '2031-01'
  await page.request.post(`/api/months/${period}/entries`, { data: { description: 'Conta travada', amount_cents: 1000, category_slug: 'contas' } })
  await page.request.put(`/api/months/${period}/closed`, { data: { closed: true } })
  try {
    await page.goto(`/mes/${period}`)
    await expect(page.getByText('Mês fechado.', { exact: false }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Novo lançamento' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Editar Conta travada' })).toHaveCount(0)
    const blocked = await page.request.post(`/api/months/${period}/entries`, { data: { description: 'Outra', amount_cents: 1, category_slug: 'contas' } })
    expect(blocked.status()).toBe(400)
  } finally {
    await page.request.put(`/api/months/${period}/closed`, { data: { closed: false } })
  }
})
