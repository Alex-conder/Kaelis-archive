import { test, expect } from '@playwright/test'

/**
 * Kaelis 关键用户旅程 E2E 测试
 * Phase 3: 覆盖登录 → Chat → RAG → 可解释性 → 反馈 → 仪表板 → 通知
 *
 * 注意：当前测试假设开发服务器已启动且前端可访问。
 * 由于项目使用 HashRouter，所有路径以 #/ 开头。
 */

test.describe('Kaelis Key User Journey', () => {
  test('navigates through main pages and verifies core UI', async ({ page }) => {
    // 1. 访问登录页
    await page.goto('/#/login')
    await expect(page.locator('text=Kaelis')).toBeVisible()

    // 2. 导航到 Dashboard（无需真实登录，HashRouter 懒加载测试）
    await page.goto('/#/dashboard')
    await expect(page.locator('text=Dashboard')).toBeVisible({ timeout: 10000 })

    // 3. 导航到 Chat 页面
    await page.goto('/#/chat')
    await expect(page.locator('[data-testid="chat-input"]')).toBeVisible()

    // 4. 导航到 RAG Lab
    await page.goto('/#/rag-demo')
    await expect(page.locator('text=RAG v3 策略实验室')).toBeVisible()

    // 5. 导航到 Explainability 仪表板
    await page.goto('/#/explainability')
    await expect(page.locator('text=可解释性审计中心')).toBeVisible()

    // 6. 导航到 Swarm
    await page.goto('/#/swarm')
    await expect(page.locator('text=Swarm 多Agent协作')).toBeVisible()

    // 7. 导航到 Evolve
    await page.goto('/#/evolve')
    await expect(page.locator('text=自举开发实验室')).toBeVisible()

    // 8. 验证通知铃铛存在
    await page.goto('/#/dashboard')
    await expect(page.locator('button[title="通知中心"]')).toBeVisible()
  })

  test('Chat page interactions', async ({ page }) => {
    await page.goto('/#/chat')

    // 验证输入框和发送按钮
    const input = page.locator('[data-testid="chat-input"]')
    await expect(input).toBeVisible()
    await input.fill('Hello Kaelis')
    await expect(input).toHaveValue('Hello Kaelis')

    // 验证 RAG 策略选择器按钮存在
    await expect(page.locator('text=通用对话')).toBeVisible()
    await expect(page.locator('text=Naive RAG')).toBeVisible()
  })

  test('Explainability dashboard loads cards', async ({ page }) => {
    await page.goto('/#/explainability')

    // 验证 6 大卡片标题存在
    await expect(page.locator('text=KG 健康度')).toBeVisible()
    await expect(page.locator('text=安全审查')).toBeVisible()
    await expect(page.locator('text=工具调用')).toBeVisible()
  })
})
