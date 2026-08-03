import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Camera,
  FilePlus2,
  FileText,
  FolderOpen,
  ScanLine,
  Trash2,
} from "lucide-react";
import { api, type Project } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const FILE_FILTERS = [
  {
    name: "Partituras",
    extensions: ["pdf", "png", "jpg", "jpeg", "bmp", "tiff", "musicxml", "xml", "mxl", "mscz"],
  },
];

interface Action {
  label: string;
  description: string;
  icon: typeof FilePlus2;
  onClick: () => void;
}

export default function HomePage() {
  const navigate = useNavigate();
  const recent = useQuery({ queryKey: ["recent"], queryFn: api.recentProjects });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [composer, setComposer] = useState("");
  const [notice, setNotice] = useState("");

  const createAndImport = useMutation({
    mutationFn: async (args: { name: string; composer?: string; paths?: string[] }) => {
      const project = await api.createProject({
        name: args.name,
        composer: args.composer,
      });
      if (args.paths?.length) {
        await api.importPaths(project.id, args.paths);
      }
      return project;
    },
    onSuccess: (p) => navigate(`/project/${p.id}`),
    onError: (e: Error) => setNotice(e.message),
  });

  async function openWithDialog(sourceLabel: string) {
    if (!window.bandscore) {
      setNotice(
        "A escolha de ficheiros nativa requer a janela Electron (npm run electron:dev). No navegador, crie um Novo Projeto e importe por upload."
      );
      return;
    }
    const paths = await window.bandscore.openFiles(FILE_FILTERS);
    if (!paths.length) return;
    const base = paths[0].split("/").pop() ?? sourceLabel;
    createAndImport.mutate({ name: base.replace(/\.[^.]+$/, ""), paths });
  }

  const actions: Action[] = [
    {
      label: "Novo Projeto",
      description: "Começar uma obra do zero",
      icon: FilePlus2,
      onClick: () => setDialogOpen(true),
    },
    {
      label: "Abrir Projeto",
      description: "Continuar um projeto existente",
      icon: FolderOpen,
      onClick: () =>
        document.getElementById("recentes")?.scrollIntoView({ behavior: "smooth" }),
    },
    {
      label: "Abrir PDF",
      description: "Importar partitura em PDF",
      icon: FileText,
      onClick: () => openWithDialog("PDF"),
    },
    {
      label: "Abrir Fotografia",
      description: "Reconhecer a partir de fotos",
      icon: Camera,
      onClick: () => openWithDialog("Fotografia"),
    },
    {
      label: "Abrir Scanner",
      description: "Digitalização direta (em breve)",
      icon: ScanLine,
      onClick: () =>
        setNotice(
          "A integração direta com scanners (TWAIN/ICA) está no roadmap. Por agora, digitalize para PDF ou PNG e use «Abrir PDF»."
        ),
    },
  ];

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-3xl font-bold tracking-tight">
          Bem-vindo ao{" "}
          <span className="bg-gradient-to-r from-violet-600 to-fuchsia-500 bg-clip-text text-transparent">
            BandScore AI
          </span>
        </h1>
        <p className="mt-2 max-w-2xl text-slate-500 dark:text-slate-400">
          Reconhecimento, edição, separação e gestão de partituras para bandas
          filarmónicas, orquestras e escolas de música — tudo offline.
        </p>
      </motion.div>

      {notice && (
        <div className="mt-6 rounded-lg border border-amber-300/50 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
          {notice}
          <button className="ml-3 underline" onClick={() => setNotice("")}>
            fechar
          </button>
        </div>
      )}

      <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
        {actions.map((a, i) => (
          <motion.button
            key={a.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i, duration: 0.35 }}
            whileHover={{ y: -3 }}
            onClick={a.onClick}
            className="group flex flex-col items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-colors hover:border-violet-400/60 dark:border-slate-800 dark:bg-slate-900/70 dark:hover:border-violet-500/50"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-600/10 text-violet-600 transition-colors group-hover:bg-violet-600 group-hover:text-white dark:bg-violet-500/15 dark:text-violet-300">
              <a.icon className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-semibold">{a.label}</div>
              <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {a.description}
              </div>
            </div>
          </motion.button>
        ))}
      </div>

      <section id="recentes" className="mt-12">
        <h2 className="text-lg font-semibold">Projetos recentes</h2>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {recent.data?.length === 0 && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Ainda não há projetos. Comece por abrir um PDF ou uma fotografia.
            </p>
          )}
          {recent.data?.map((p: Project) => (
            <Card
              key={p.id}
              className="cursor-pointer transition-colors hover:border-violet-400/60 dark:hover:border-violet-500/50"
              onClick={() => navigate(`/project/${p.id}`)}
            >
              <CardContent className="flex items-center justify-between p-4">
                <div>
                  <div className="font-medium">{p.name}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {p.composer || "Compositor desconhecido"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone="muted">{p.status}</Badge>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (confirm(`Apagar o projeto «${p.name}»?`)) {
                        await api.deleteProject(p.id);
                        recent.refetch();
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-slate-400" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900"
          >
            <h3 className="text-lg font-semibold">Novo Projeto</h3>
            <div className="mt-4 flex flex-col gap-3">
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Nome da obra"
                className="h-10 rounded-lg border border-slate-300 bg-transparent px-3 text-sm outline-none focus:border-violet-500 dark:border-slate-700"
              />
              <input
                value={composer}
                onChange={(e) => setComposer(e.target.value)}
                placeholder="Compositor (opcional)"
                className="h-10 rounded-lg border border-slate-300 bg-transparent px-3 text-sm outline-none focus:border-violet-500 dark:border-slate-700"
              />
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDialogOpen(false)}>
                Cancelar
              </Button>
              <Button
                disabled={!name.trim() || createAndImport.isPending}
                onClick={() => createAndImport.mutate({ name: name.trim(), composer })}
              >
                Criar
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
