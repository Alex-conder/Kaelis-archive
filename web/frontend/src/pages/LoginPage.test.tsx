import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { HashRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LoginPage from './LoginPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        {children}
      </HashRouter>
    </QueryClientProvider>
  )
}

describe('LoginPage', () => {
  it('renders login form with email and password inputs', () => {
    render(<LoginPage />, { wrapper: Wrapper })

    expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument()
    expect(screen.getByText('登录')).toBeInTheDocument()
  })

  it('renders Kaelis branding', () => {
    render(<LoginPage />, { wrapper: Wrapper })

    expect(screen.getByText('Kaelis')).toBeInTheDocument()
    expect(screen.getByText('AI-Native Development Platform')).toBeInTheDocument()
  })

  it('renders offline mode button', () => {
    render(<LoginPage />, { wrapper: Wrapper })

    expect(screen.getByText('Use Offline Mode')).toBeInTheDocument()
  })
})
