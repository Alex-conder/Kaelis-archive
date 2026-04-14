/**
 * E2E Tests for Knowledge Graph Flywheel
 * 
 * Tests: Extract → Query → Inspect 闭环
 */
import { test, expect } from '@playwright/test';

test.describe('Knowledge Graph Flywheel', () => {
  
  test.beforeEach(async ({ page }) => {
    // 访问 KgFlywheel 页面
    await page.goto('/api/static/kg-flywheel.html');
    
    // 等待页面加载完成
    await page.waitForSelector('#chatMessages', { timeout: 10000 });
    
    // 等待 WebSocket 连接
    await page.waitForFunction(() => {
      const status = document.getElementById('statusText');
      return status?.textContent === '已连接' || status?.textContent === '就绪';
    }, { timeout: 10000 });
  });

  test.describe('Page Load', () => {
    test('should display correct title and pipeline', async ({ page }) => {
      await expect(page.locator('h1')).toContainText('Knowledge Graph Flywheel');
      
      // 验证流水线阶段
      await expect(page.locator('#stage-extract')).toContainText('Extract');
      await expect(page.locator('#stage-query')).toContainText('Query');
      await expect(page.locator('#stage-inspect')).toContainText('Inspect');
    });

    test('should show initial welcome message', async ({ page }) => {
      const chatMessages = page.locator('#chatMessages .bubble');
      await expect(chatMessages.first()).toContainText('欢迎使用知识图谱飞轮');
    });

    test('should display stats panel', async ({ page }) => {
      await expect(page.locator('#statEntities')).toHaveText('0');
      await expect(page.locator('#statRelations')).toHaveText('0');
    });
  });

  test.describe('Extraction Flow', () => {
    test('should extract triples from text', async ({ page }) => {
      const inputText = '提取：阿里巴巴由马云于1999年在杭州创立';
      await page.fill('#userInput', inputText);
      await page.click('#sendBtn');
      
      await page.waitForTimeout(2000);
      
      // 验证 Agent 回复
      const agentMessages = page.locator('.message-agent .bubble');
      await expect(agentMessages.last()).toContainText('提取', { timeout: 10000 });
    });
  });

  test.describe('Query Flow', () => {
    test('should query graph with natural language', async ({ page }) => {
      await page.fill('#userInput', '查询所有实体');
      await page.click('#sendBtn');
      await page.waitForTimeout(2000);
      
      const agentMessages = page.locator('.message-agent .bubble');
      await expect(agentMessages.last()).toContainText('查询', { timeout: 10000 });
    });
  });

  test.describe('Inspection Flow', () => {
    test('should run quality check', async ({ page }) => {
      await page.fill('#userInput', '运行质量检查');
      await page.click('#sendBtn');
      await page.waitForTimeout(3000);
      
      const agentMessages = page.locator('.message-agent .bubble');
      await expect(agentMessages.last()).toContainText('质检', { timeout: 10000 });
    });
  });

  test.describe('Flywheel Pipeline', () => {
    test('should complete full flywheel cycle', async ({ page }) => {
      await page.fill('#userInput', '执行飞轮：百度由李彦宏创立');
      await page.click('#sendBtn');
      await page.waitForTimeout(5000);
      
      const agentMessages = page.locator('.message-agent .bubble');
      await expect(agentMessages.last()).toContainText('飞轮', { timeout: 15000 });
    });
  });
});
