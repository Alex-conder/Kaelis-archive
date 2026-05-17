import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import NotificationBell from './NotificationBell'

function Wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('NotificationBell', () => {
  it('renders bell icon button', () => {
    render(<NotificationBell />, { wrapper: Wrapper })
    expect(screen.getByTitle('通知中心')).toBeInTheDocument()
  })

  it('shows dropdown when clicked', () => {
    render(<NotificationBell />, { wrapper: Wrapper })
    const bell = screen.getByTitle('通知中心')
    fireEvent.click(bell)
    expect(screen.getByText('通知中心')).toBeInTheDocument()
  })
})
