import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

const FIELDS = [
  { key: "q", label: "Pesquisa livre" },
  { key: "composer", label: "Compositor" },
  { key: "instrument", label: "Instrumento" },
  { key: "difficulty", label: "Dificuldade" },
  { key: "ensemble", label: "Banda / Orquestra" },
  { key: "year", label: "Ano" },
  { key: "publisher", label: "Editor" },
] as const;

export default function LibraryPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const results = useQuery({
    queryKey: ["library", filters],
    queryFn: () => api.library(filters),
  });

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
        <Search className="h-6 w-6 text-violet-500" /> Biblioteca
      </h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Pesquise o arquivo por compositor, obra, instrumento, dificuldade,
        formação, ano ou editor.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {FIELDS.map((f) => (
          <input
            key={f.key}
            placeholder={f.label}
            value={filters[f.key] ?? ""}
            onChange={(e) =>
              setFilters((prev) => ({ ...prev, [f.key]: e.target.value }))
            }
            className="h-10 rounded-lg border border-slate-300 bg-transparent px-3 text-sm outline-none focus:border-violet-500 dark:border-slate-700"
          />
        ))}
      </div>

      <div className="mt-8 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
              <th className="px-4 py-3">Obra</th>
              <th className="px-4 py-3">Compositor</th>
              <th className="px-4 py-3">Formação</th>
              <th className="px-4 py-3">Ano</th>
              <th className="px-4 py-3">Dificuldade</th>
              <th className="px-4 py-3">Instrumentos</th>
            </tr>
          </thead>
          <tbody>
            {results.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  Sem resultados. As obras entram automaticamente na biblioteca
                  quando são reconhecidas ou importadas em MusicXML/MSCZ.
                </td>
              </tr>
            )}
            {results.data?.map((e) => (
              <tr
                key={e.id}
                className="border-b border-slate-100 last:border-0 dark:border-slate-800/60"
              >
                <td className="px-4 py-3 font-medium">{e.title}</td>
                <td className="px-4 py-3">{e.composer || "—"}</td>
                <td className="px-4 py-3">
                  <Badge tone="muted">{e.ensemble}</Badge>
                </td>
                <td className="px-4 py-3">{e.year ?? "—"}</td>
                <td className="px-4 py-3">{e.difficulty || "—"}</td>
                <td className="px-4 py-3 text-xs text-slate-500">
                  {e.instruments.slice(0, 5).join(", ")}
                  {e.instruments.length > 5 && "…"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
