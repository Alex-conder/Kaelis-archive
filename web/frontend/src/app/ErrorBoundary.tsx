import { Component, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw, Home } from 'lucide-react'
import { Link } from 'react-router-dom'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen bg-[#0B1120] flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-[#0f172a] border border-slate-800 rounded-2xl p-8 shadow-2xl">
            <div className="w-14 h-14 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-5">
              <AlertTriangle className="w-7 h-7 text-red-400" />
            </div>
            <h1 className="text-xl font-bold text-white text-center mb-2">
              应用发生错误
            </h1>
            <p className="text-sm text-slate-400 text-center mb-6 leading-relaxed">
              抱歉，Kaelis 遇到了意外问题。错误信息已记录，您可以尝试刷新页面恢复。
            </p>
            {this.state.error && (
              <div className="bg-[#0B1120] rounded-lg border border-slate-800 p-3 mb-6 overflow-auto">
                <code className="text-xs text-red-300 font-mono block whitespace-pre-wrap">
                  {this.state.error.message}
                </code>
              </div>
            )}
            <div className="flex items-center gap-3 justify-center">
              <button
                onClick={this.handleReset}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                重试
              </button>
              <Link
                to="/"
                className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors"
              >
                <Home className="w-4 h-4" />
                返回首页
              </Link>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
