import { useState, useEffect } from 'react'
import { track } from '@/utils/telemetry'

interface OnboardingWizardProps {
  onComplete?: () => void
}

async function markOnboardingComplete() {
  try {
    await fetch('http://localhost:5000/api/auth/onboarding/complete', { method: 'POST' })
  } catch {
    // ignore
  }
  localStorage.setItem('kaelis_onboarding_completed', 'true')
}

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState<'welcome' | 'llm' | 'workflow' | 'done'>('welcome')
  const [apiKey, setApiKey] = useState('')
  const [provider, setProvider] = useState('openai')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)

  useEffect(() => {
    // 检查是否已配置 API Key（简化版：仅检查 localStorage 标记）
    const hasKey = localStorage.getItem('kaelis_llm_configured') === 'true'
    if (hasKey && step === 'welcome') {
      setStep('workflow')
    }
  }, [step])

  const handleWelcomeNext = () => {
    track('onboarding_step_complete', { step: 'welcome', next: 'llm' })
    setStep('llm')
  }

  const handleTestConnection = async () => {
    if (!apiKey.trim()) return
    track('onboarding_llm_test_start', { provider })
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetch('http://localhost:5000/api/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey })
      })
      if (res.ok) {
        setTestResult('success')
        track('onboarding_llm_test_success', { provider })
        localStorage.setItem('kaelis_llm_provider', provider)
        localStorage.setItem('kaelis_llm_api_key', apiKey)
        localStorage.setItem('kaelis_llm_configured', 'true')
        setTimeout(() => {
          track('onboarding_step_complete', { step: 'llm', next: 'workflow' })
          setStep('workflow')
        }, 800)
      } else {
        setTestResult('error')
        track('onboarding_llm_test_error', { provider, status: res.status })
      }
    } catch {
      setTestResult('error')
      track('onboarding_llm_test_error', { provider, error: 'network' })
    } finally {
      setTesting(false)
    }
  }

  const handleImportTemplate = async () => {
    track('onboarding_step_complete', { step: 'workflow', next: 'done', action: 'import_template' })
    // 模拟导入示例工作流
    localStorage.setItem('kaelis_workflows', JSON.stringify([{
      id: 'template_1',
      name: '文献综述模板',
      template: 'literature_review'
    }]))
    await markOnboardingComplete()
    setStep('done')
    setTimeout(() => {
      onComplete?.()
    }, 500)
  }

  const handleSkip = async () => {
    track('onboarding_skip', { currentStep: step })
    await markOnboardingComplete()
    onComplete?.()
  }

  if (step === 'done') {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
        <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full text-center">
          <div className="text-5xl mb-4">🎉</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">准备就绪！</h2>
          <p className="text-gray-600">正在进入 Kaelis 工作台...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-lg w-full mx-4">
        {/* 进度指示器 */}
        <div className="flex items-center justify-between mb-8">
          {[
            { id: 'welcome', label: '欢迎' },
            { id: 'llm', label: '配置 LLM' },
            { id: 'workflow', label: '工作流' }
          ].map((s, idx) => {
            const isActive = step === s.id
            const isPast = ['welcome', 'llm', 'workflow'].indexOf(step) > idx
            return (
              <div key={s.id} className="flex items-center">
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold
                  ${isActive ? 'bg-blue-600 text-white' : isPast ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'}
                `}>
                  {isPast ? '✓' : idx + 1}
                </div>
                <span className={`ml-2 text-sm ${isActive ? 'text-blue-600 font-medium' : 'text-gray-500'}`}>
                  {s.label}
                </span>
                {idx < 2 && <div className="w-12 h-px bg-gray-200 mx-3" />}
              </div>
            )
          })}
        </div>

        {/* 欢迎步骤 */}
        {step === 'welcome' && (
          <>
            <div className="text-center mb-6">
              <div className="text-5xl mb-4">🌊</div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">欢迎来到 Kaelis</h2>
              <p className="text-gray-600">您的 AI 科研工作台，3 步即可开始知识提取</p>
            </div>
            <div className="space-y-3 mb-6">
              <div className="flex items-center p-3 bg-blue-50 rounded-lg">
                <span className="text-blue-600 font-bold mr-3">1</span>
                <span className="text-gray-700">配置 LLM API Key</span>
              </div>
              <div className="flex items-center p-3 bg-blue-50 rounded-lg">
                <span className="text-blue-600 font-bold mr-3">2</span>
                <span className="text-gray-700">导入示例工作流</span>
              </div>
              <div className="flex items-center p-3 bg-blue-50 rounded-lg">
                <span className="text-blue-600 font-bold mr-3">3</span>
                <span className="text-gray-700">开始 KG 提取</span>
              </div>
            </div>
            <div className="flex justify-between">
              <button onClick={handleSkip} className="text-gray-500 hover:text-gray-700 px-4 py-2">
                跳过引导
              </button>
              <button
                onClick={handleWelcomeNext}
                className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 font-medium"
              >
                开始配置
              </button>
            </div>
          </>
        )}

        {/* LLM 配置步骤 */}
        {step === 'llm' && (
          <>
            <h2 className="text-xl font-bold text-gray-900 mb-4">配置 LLM</h2>
            <p className="text-gray-600 mb-6">选择提供商并输入 API Key，我们将测试连接</p>
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">提供商</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="openai">OpenAI</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="anthropic">Anthropic</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            {testResult === 'success' && (
              <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm">✅ 连接测试成功</div>
            )}
            {testResult === 'error' && (
              <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">❌ 连接失败，请检查 API Key</div>
            )}
            <div className="flex justify-between">
              <button onClick={() => setStep('welcome')} className="text-gray-500 hover:text-gray-700 px-4 py-2">
                上一步
              </button>
              <button
                onClick={handleTestConnection}
                disabled={testing || !apiKey.trim()}
                className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {testing ? '测试中...' : '测试并继续'}
              </button>
            </div>
          </>
        )}

        {/* 工作流步骤 */}
        {step === 'workflow' && (
          <>
            <h2 className="text-xl font-bold text-gray-900 mb-4">导入首个工作流</h2>
            <p className="text-gray-600 mb-6">从模板开始，快速体验 KG 提取</p>
            <div className="border border-gray-200 rounded-xl p-4 mb-6 hover:border-blue-400 cursor-pointer transition-colors"
                 onClick={handleImportTemplate}>
              <div className="flex items-start space-x-4">
                <div className="text-3xl">📚</div>
                <div>
                  <h3 className="font-semibold text-gray-900">文献综述模板</h3>
                  <p className="text-sm text-gray-600 mt-1">自动提取论文中的实体、关系与核心观点，生成知识图谱</p>
                  <div className="mt-2 flex space-x-2">
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">NLP</span>
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">KG 提取</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex justify-between">
              <button onClick={() => setStep('llm')} className="text-gray-500 hover:text-gray-700 px-4 py-2">
                上一步
              </button>
              <button
                onClick={handleSkip}
                className="text-gray-500 hover:text-gray-700 px-4 py-2"
              >
                暂不导入
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
