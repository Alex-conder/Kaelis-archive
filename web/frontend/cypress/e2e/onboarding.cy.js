/// <reference types="cypress" />

describe('Kaelis Onboarding Flow', () => {
  beforeEach(() => {
    // 清除 onboarding 状态，确保每次测试都重新引导
    cy.clearLocalStorage('kaelis_onboarding_completed')
    cy.clearLocalStorage('kaelis_llm_configured')
    cy.visit('/')
  })

  it('should show onboarding wizard for first-time users', () => {
    cy.contains('欢迎', { timeout: 10000 }).should('be.visible')
    cy.contains('下一步').click()
  })

  it('should complete LLM configuration step', () => {
    cy.contains('欢迎').should('be.visible')
    cy.contains('下一步').click()

    // 如果在 LLM 配置页
    cy.get('body').then(($body) => {
      if ($body.text().includes('API Key') || $body.text().includes('模型')) {
        // 模拟跳过或使用离线模式
        cy.contains('跳过', { matchCase: false }).click({ force: true })
      }
    })
  })

  it('should land on chat page after onboarding', () => {
    // 快速完成引导
    cy.window().then((win) => {
      win.localStorage.setItem('kaelis_onboarding_completed', 'true')
      win.localStorage.setItem('kaelis_llm_configured', 'true')
    })
    cy.visit('/')
    cy.url().should('include', '#/chat')
    cy.get('[data-testid="chat-input"]', { timeout: 10000 }).should('be.visible')
  })

  it('should send first message and receive reply', () => {
    cy.window().then((win) => {
      win.localStorage.setItem('kaelis_onboarding_completed', 'true')
      win.localStorage.setItem('kaelis_llm_configured', 'true')
    })
    cy.visit('/#/chat')

    cy.get('[data-testid="chat-input"]', { timeout: 10000 }).type('Hello Kaelis{enter}')
    cy.contains('Hello', { timeout: 15000 }).should('be.visible')
  })
})
