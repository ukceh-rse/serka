import { useMemo } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { createAppTheme } from './theme'
import { useAppStore } from './stores/appStore'
import Layout from './components/Layout'
import LandingPage from './pages/LandingPage'
import ResultsPage from './pages/ResultsPage'
import ChatPage from './pages/ChatPage'

export default function App() {
  const { themeMode } = useAppStore()
  const theme = useMemo(() => createAppTheme(themeMode), [themeMode])

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/search" element={<ResultsPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ThemeProvider>
  )
}
