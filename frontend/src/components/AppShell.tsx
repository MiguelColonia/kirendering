import type { ReactNode } from "react";
import { Building2, FolderKanban, SquarePen } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const { t } = useTranslation();

  const navItems = [
    { to: "/", label: t("nav.landing"), icon: Building2 },
    { to: "/projekte", label: t("nav.projects"), icon: FolderKanban },
    { to: "/projekte/neu", label: t("nav.new_project"), icon: SquarePen },
  ];

  return (
    <div className="min-h-screen text-[color:var(--color-ink)]">
      <header className="fixed inset-x-0 top-0 z-40 border-b border-[color:var(--color-line)] bg-[color:var(--color-paper)]/72 shadow-[0_18px_40px_rgba(24,36,45,0.07)] backdrop-blur-2xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 md:px-6 lg:px-8">
          <NavLink to="/" className="group inline-flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-full border border-white/55 bg-[linear-gradient(145deg,var(--color-accent),var(--color-teal))] text-sm font-semibold tracking-[0.24em] text-white shadow-[0_14px_30px_rgba(24,78,99,0.24)] transition-transform duration-200 group-hover:-translate-y-0.5">
              C
            </span>
            <span>
              <span className="block text-lg font-semibold tracking-[-0.04em]">
                {t("app.title")}
              </span>
              <span className="block text-xs uppercase tracking-[0.18em] text-[color:var(--color-mist)]">
                {t("app.tagline")}
              </span>
            </span>
          </NavLink>

          <nav className="flex flex-wrap gap-2 rounded-full border border-[color:var(--color-line)] bg-white/60 p-1.5 shadow-[0_12px_28px_rgba(24,36,45,0.05)] backdrop-blur-xl">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  [
                    "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition",
                    isActive
                      ? "border-white/70 bg-white text-[color:var(--color-accent)] shadow-[0_10px_20px_rgba(24,78,99,0.12)]"
                      : "border-transparent text-[color:var(--color-mist)] hover:border-[color:var(--color-line)] hover:bg-white/70 hover:text-[color:var(--color-ink)]",
                  ].join(" ")
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 pb-12 pt-28 md:px-6 lg:px-8">
        <main className="space-y-6">{children}</main>
      </div>
    </div>
  );
}
