import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { AppProviders } from './app/providers'
import { ErrorBoundary } from './app/ErrorBoundary'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <AppProviders>
        <App />
      </AppProviders>
    </ErrorBoundary>
  </StrictMode>
)
