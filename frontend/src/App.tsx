import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AppShell } from './components/AppShell'
import { LandingPage } from './pages/LandingPage'
import { ProjectEditorPage } from './pages/ProjectEditorPage'
import { ProjectListPage } from './pages/ProjectListPage'

function App() {
  const { i18n } = useTranslation()

  useEffect(() => {
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/projekte" element={<ProjectListPage />} />
          <Route path="/projekte/neu" element={<ProjectListPage showCreateDialog />} />
          <Route path="/projekte/:id" element={<ProjectEditorPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}

export default App
