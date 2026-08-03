import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Home, Library, Moon, Music4, Sun } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/useAppStore";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function CapabilityDot({ label, ok }: { label: string; ok: boolean }) {
  return (
    <Badge tone={ok ? "ok" : "warn"} title={ok ? `${label} disponível` : `${label} não encontrado`}>
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          ok ? "bg-emerald-500" : "bg-amber-500"
        )}
      />
      {label}
    </Badge>
  );
}

export default function Layout() {
  const { theme, toggleTheme } = useAppStore();
  const caps = useQuery({
    queryKey: ["capabilities"],
    queryFn: api.capabilities,
    retry: 1,
    refetchInterval: 60_000,
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const nav = [
    { to: "/", label: "Início", icon: Home },
    { to: "/library", label: "Biblioteca", icon: Library },
  ];

  return (
    <div className="flex h-full bg-slate-50 text-slate-900 dark:bg-[#0b0d12] dark:text-slate-100">
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white/70 dark:border-slate-800 dark:bg-slate-950/60">
        <div className="drag-region flex items-center gap-2.5 px-5 pb-4 pt-10">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-fuchsia-600 shadow-lg shadow-violet-600/30">
            <Music4 className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight">BandScore AI</div>
            <div className="text-[10px] text-slate-500 dark:text-slate-400">
              Partituras inteligentes
            </div>
          </div>
        </div>

        <nav className="flex flex-col gap-1 px-3">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-violet-600/10 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/60"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-2 border-t border-slate-200 p-4 dark:border-slate-800">
          {caps.data && (
            <div className="flex flex-wrap gap-1.5">
              <CapabilityDot label="Audiveris" ok={!!caps.data.audiveris} />
              <CapabilityDot label="MuseScore" ok={!!caps.data.musescore} />
              <Badge tone="muted">{caps.data.device.toUpperCase()}</Badge>
            </div>
          )}
          {caps.isError && (
            <Badge tone="error">Backend desligado — correr scripts/dev.sh</Badge>
          )}
          <Button variant="ghost" size="sm" onClick={toggleTheme} className="justify-start">
            {theme === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
            {theme === "dark" ? "Modo claro" : "Modo escuro"}
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
