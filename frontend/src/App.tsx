import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AppShell } from "./components/AppShell";

const LandingPage = lazy(() =>
  import("./pages/LandingPage").then((module) => ({
    default: module.LandingPage,
  })),
);
const ProjectListPage = lazy(() =>
  import("./pages/ProjectListPage").then((module) => ({
    default: module.ProjectListPage,
  })),
);
const ProjectEditorPage = lazy(() =>
  import("./pages/ProjectEditorPage").then((module) => ({
    default: module.ProjectEditorPage,
  })),
);
const ProjectRendersPage = lazy(() =>
  import("./pages/ProjectRendersPage").then((module) => ({
    default: module.ProjectRendersPage,
  })),
);

function RouteFallback() {
  return (
    <section className="panel-surface rounded-[2rem] p-6 md:p-8">
      <p className="text-sm text-[color:var(--color-mist)]">Laden...</p>
    </section>
  );
}

function App() {
  const { i18n } = useTranslation();

  useEffect(() => {
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  return (
    <BrowserRouter>
      <AppShell>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/projekte" element={<ProjectListPage />} />
            <Route
              path="/projekte/neu"
              element={<ProjectListPage showCreateDialog />}
            />
            <Route path="/projekte/:id" element={<ProjectEditorPage />} />
            <Route
              path="/projekte/:id/renders"
              element={<ProjectRendersPage />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AppShell>
    </BrowserRouter>
  );
}

export default App;
