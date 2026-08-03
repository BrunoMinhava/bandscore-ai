import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { OpenSheetMusicDisplay } from "opensheetmusicdisplay";
import {
  Check,
  ChevronDown,
  Download,
  Eye,
  FileMusic,
  Import,
  ListMusic,
  Loader2,
  Pencil,
  Play,
  ScanSearch,
  Wand2,
  X,
} from "lucide-react";
import {
  api,
  fileUrl,
  type ExportedFile,
  type PartInfo,
  type PreprocessOptions,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const STEPS = [
  { key: "import", label: "Importar", icon: Import },
  { key: "recognize", label: "Reconhecer", icon: ScanSearch },
  { key: "separate", label: "Separar", icon: ListMusic },
  { key: "export", label: "Exportar", icon: Download },
] as const;

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s ? `${m}m ${s}s` : `${m}m`;
}

type StepKey = (typeof STEPS)[number]["key"];

const DEFAULT_OPTIONS: PreprocessOptions = {
  perspective: true,
  shadows: true,
  denoise: true,
  contrast: true,
  deskew: true,
  split_double_pages: true,
};

const OPTION_LABELS: Record<keyof PreprocessOptions, string> = {
  perspective: "Corrigir perspetiva",
  shadows: "Remover sombras",
  denoise: "Remover ruído",
  contrast: "Corrigir brilho e contraste",
  deskew: "Corrigir rotação / páginas tortas",
  split_double_pages: "Detetar páginas duplas",
};

const EXPORT_FORMATS = ["pdf", "musicxml", "mscz", "mxl", "midi", "png", "svg"];

const INSTRUMENTS = [
  "Flautim", "Flauta", "Oboé", "Fagote", "Requinta", "Clarinete",
  "Clarinete Baixo", "Sax Soprano", "Sax Alto", "Sax Tenor", "Sax Barítono",
  "Trompete", "Cornetim", "Fliscorne", "Trompa", "Trombone",
  "Bombardino", "Tuba", "Contrabaixo", "Tímpanos", "Percussão", "Bateria",
];

function InstrumentAssign({
  projectId,
  part,
}: {
  projectId: number;
  part: PartInfo;
}) {
  const qc = useQueryClient();
  const [voice, setVoice] = useState("");
  const assign = useMutation({
    mutationFn: (name: string) => api.updatePart(projectId, part.id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["score", projectId] }),
  });

  const apply = (instrument: string, v: string) => {
    if (!instrument) return;
    assign.mutate(v ? `${instrument} ${v}` : instrument);
  };

  return (
    <div
      className="flex items-center gap-1.5"
      onClick={(e) => e.stopPropagation()}
    >
      <select
        value={INSTRUMENTS.includes(part.canonical) ? part.canonical : ""}
        onChange={(e) => apply(e.target.value, voice)}
        className="h-7 rounded-md border border-slate-300 bg-transparent px-1.5 text-xs outline-none focus:border-violet-500 dark:border-slate-700 dark:bg-slate-900"
      >
        <option value="">Atribuir instrumento…</option>
        {INSTRUMENTS.map((i) => (
          <option key={i} value={i}>
            {i}
          </option>
        ))}
      </select>
      <select
        value={voice}
        onChange={(e) => {
          setVoice(e.target.value);
          if (INSTRUMENTS.includes(part.canonical)) {
            apply(part.canonical, e.target.value);
          }
        }}
        className="h-7 rounded-md border border-slate-300 bg-transparent px-1 text-xs outline-none focus:border-violet-500 dark:border-slate-700 dark:bg-slate-900"
        title="Nº de voz (Trompete 1, 2, 3…)"
      >
        <option value="">nº</option>
        {["1", "2", "3", "4"].map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
      {assign.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />}
    </div>
  );
}

export default function ProjectView() {
  const { id } = useParams();
  const projectId = Number(id);
  const qc = useQueryClient();
  const [step, setStep] = useState<StepKey>("import");
  const [error, setError] = useState("");

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
  });
  const score = useQuery({
    queryKey: ["score", projectId],
    queryFn: () => api.score(projectId),
    retry: false,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["project", projectId] });
    qc.invalidateQueries({ queryKey: ["score", projectId] });
  };

  if (!project.data) {
    return (
      <div className="flex h-full items-center justify-center text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> A carregar projeto…
      </div>
    );
  }
  const p = project.data;

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{p.name}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {p.composer || "Compositor desconhecido"} · {p.pages.length} página(s)
            · <Badge tone="muted">{p.status}</Badge>
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={`/project/${projectId}/editor`}>
            <Button variant="outline" size="sm" disabled={!score.data}>
              <Pencil className="h-4 w-4" /> Editor
            </Button>
          </Link>
          <Link to={`/project/${projectId}/play`}>
            <Button variant="outline" size="sm" disabled={!score.data}>
              <Play className="h-4 w-4" /> Reprodução
            </Button>
          </Link>
        </div>
      </div>

      <div className="mt-6 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 dark:border-slate-800 dark:bg-slate-900/70">
        {STEPS.map((s) => (
          <button
            key={s.key}
            onClick={() => setStep(s.key)}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 py-2.5 text-sm font-medium transition-colors",
              step === s.key
                ? "bg-violet-600 text-white shadow-lg shadow-violet-600/25"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/60"
            )}
          >
            <s.icon className="h-4 w-4" /> {s.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-300/60 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
          {error}
          <button className="ml-3 underline" onClick={() => setError("")}>
            fechar
          </button>
        </div>
      )}

      <motion.div
        key={step}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="mt-6"
      >
        {step === "import" && (
          <ImportStep projectId={projectId} onDone={refresh} onError={setError} />
        )}
        {step === "recognize" && (
          <RecognizeStep
            projectId={projectId}
            onDone={refresh}
            onError={setError}
            onSinglePart={() => setStep("export")}
          />
        )}
        {step === "separate" && (
          <SeparateStep projectId={projectId} onGoExport={() => setStep("export")} />
        )}
        {step === "export" && (
          <ExportStep projectId={projectId} onError={setError} />
        )}
      </motion.div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ImportStep({
  projectId,
  onDone,
  onError,
}: {
  projectId: number;
  onDone: () => void;
  onError: (m: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
  });

  const importMutation = useMutation({
    mutationFn: async () => {
      if (window.bandscore) {
        const paths = await window.bandscore.openFiles([
          {
            name: "Partituras",
            extensions: ["pdf", "png", "jpg", "jpeg", "bmp", "tiff", "musicxml", "xml", "mxl", "mscz"],
          },
        ]);
        if (!paths.length) return null;
        return api.importPaths(projectId, paths);
      }
      inputRef.current?.click();
      return null;
    },
    onSuccess: (r) => r && onDone(),
    onError: (e: Error) => onError(e.message),
  });

  const uploadMutation = useMutation({
    mutationFn: (files: FileList) => api.importUpload(projectId, files),
    onSuccess: onDone,
    onError: (e: Error) => onError(e.message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Importar ficheiros</CardTitle>
        <CardDescription>
          PDF, PNG, JPG, JPEG, BMP, TIFF, MusicXML, MXL e MSCZ. PDFs são
          convertidos página a página; partituras digitais entram diretamente no
          motor musical.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-3">
          <Button onClick={() => importMutation.mutate()} disabled={importMutation.isPending}>
            {importMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Import className="h-4 w-4" />
            )}
            Escolher ficheiros
          </Button>
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            accept=".pdf,.png,.jpg,.jpeg,.bmp,.tiff,.musicxml,.xml,.mxl,.mscz"
            onChange={(e) => e.target.files?.length && uploadMutation.mutate(e.target.files)}
          />
          {uploadMutation.isPending && (
            <span className="text-sm text-slate-500">A importar…</span>
          )}
        </div>

        {!!project.data?.pages.length && (
          <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
            {project.data.pages.map((page) => (
              <div
                key={page.id}
                className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800"
              >
                <img
                  src={fileUrl(page.original_url)}
                  alt={`Página ${page.index}`}
                  className="aspect-[3/4] w-full object-cover"
                />
                <div className="px-2 py-1.5 text-center text-xs text-slate-500">
                  Página {page.index}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */

function RecognizeStep({
  projectId,
  onDone,
  onError,
  onSinglePart,
}: {
  projectId: number;
  onDone: () => void;
  onError: (m: string) => void;
  onSinglePart: () => void;
}) {
  const qc = useQueryClient();
  const [options, setOptions] = useState<PreprocessOptions>(DEFAULT_OPTIONS);
  const [showOptions, setShowOptions] = useState(false);
  const [running, setRunning] = useState(false);

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
  });
  const score = useQuery({
    queryKey: ["score", projectId],
    queryFn: () => api.score(projectId),
    retry: false,
  });

  // enquanto corre, pergunta o progresso de segundo a segundo
  const progress = useQuery({
    queryKey: ["progress", projectId],
    queryFn: () => api.progress(projectId),
    refetchInterval: running ? 1000 : false,
    enabled: running,
  });

  const start = useMutation({
    mutationFn: () => api.startRecognition(projectId, options),
    onSuccess: () => setRunning(true),
    onError: (e: Error) => onError(e.message),
  });
  const acceptAll = useMutation({
    mutationFn: () => api.acceptAllDoubts(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["score", projectId] }),
    onError: (e: Error) => onError(e.message),
  });

  const p = progress.data;
  useEffect(() => {
    if (!running || !p?.finished) return;
    setRunning(false);
    if (p.error) {
      onError(p.error);
      return;
    }
    onDone();
    if (p.result?.warning) onError(p.result.warning);
    if (p.result && p.result.parts.length === 1) onSinglePart();
  }, [running, p, onDone, onError, onSinglePart]);

  const doubtCount = score.data
    ? Object.values(score.data.doubtful_measures).reduce(
        (sum, rows) => sum + rows.reduce((s, r) => s + r.notes, 0),
        0
      )
    : 0;
  const pages = project.data?.pages.length ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Reconhecimento</CardTitle>
        <CardDescription>
          Prepara as imagens e reconhece a música num só passo: correção das
          páginas, pautas, instrumentos, notas, dinâmicas, armaduras, compassos,
          repetições, D.C., D.S., Coda e Fine.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="lg"
            onClick={() => start.mutate()}
            disabled={running || start.isPending || !pages}
          >
            {running ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ScanSearch className="h-4 w-4" />
            )}
            {running ? "A processar…" : `Reconhecer ${pages} página(s)`}
          </Button>
          {doubtCount > 0 && !running && (
            <Button
              variant="secondary"
              onClick={() => acceptAll.mutate()}
              disabled={acceptAll.isPending}
            >
              {acceptAll.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              Aceitar todas as {doubtCount} leituras duvidosas
            </Button>
          )}
          {!running && (
            <button
              onClick={() => setShowOptions((v) => !v)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-violet-600 dark:text-slate-400"
            >
              <Wand2 className="h-3.5 w-3.5" />
              Opções de preparação da imagem
              <ChevronDown
                className={cn("h-3.5 w-3.5 transition-transform", showOptions && "rotate-180")}
              />
            </button>
          )}
        </div>

        {running && p && !p.idle && (
          <div className="mt-5">
            <div className="mb-2 flex items-baseline justify-between text-sm">
              <span className="font-medium">
                {p.phase_label}
                {p.total ? (
                  <span className="ml-2 text-slate-500">
                    página {Math.min((p.done ?? 0) + 1, p.total)} de {p.total}
                  </span>
                ) : null}
              </span>
              <span className="font-mono text-lg font-semibold text-violet-600 dark:text-violet-400">
                {p.percent ?? 0}%
              </span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-500"
                animate={{ width: `${p.percent ?? 0}%` }}
                transition={{ duration: 0.4 }}
              />
            </div>
            <div className="mt-2 flex justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>decorrido {formatDuration(p.elapsed_seconds ?? 0)}</span>
              <span>
                {p.eta_seconds != null
                  ? `faltam ~${formatDuration(p.eta_seconds)}`
                  : "a calcular o tempo…"}
              </span>
            </div>
          </div>
        )}

        {showOptions && !running && (
          <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-3">
            {(Object.keys(OPTION_LABELS) as (keyof PreprocessOptions)[]).map((key) => (
              <label
                key={key}
                className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2 text-xs dark:border-slate-800"
              >
                <input
                  type="checkbox"
                  checked={options[key]}
                  onChange={(e) =>
                    setOptions((prev) => ({ ...prev, [key]: e.target.checked }))
                  }
                  className="h-4 w-4 accent-violet-600"
                />
                {OPTION_LABELS[key]}
              </label>
            ))}
          </div>
        )}

        {score.data && !running && (
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge tone="ok">
              <Check className="h-3 w-3" /> {score.data.parts.length} instrumento(s)
            </Badge>
            <Badge tone={doubtCount ? "warn" : "ok"}>
              {doubtCount} nota(s) duvidosa(s)
            </Badge>
            {acceptAll.data && (
              <Badge tone="ok">{acceptAll.data.accepted} leituras aceites</Badge>
            )}
          </div>
        )}

        {doubtCount > 0 && !running && (
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            Os compassos com confiança baixa aparecem detalhados por instrumento
            no passo <strong>Separar</strong>. Pode aceitar tudo de uma vez aqui
            e rever apenas o que interessar.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */

function SeparateStep({
  projectId,
  onGoExport,
}: {
  projectId: number;
  onGoExport: () => void;
}) {
  const [preview, setPreview] = useState<PartInfo | null>(null);
  const score = useQuery({
    queryKey: ["score", projectId],
    queryFn: () => api.score(projectId),
    retry: false,
  });

  if (!score.data) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-sm text-slate-500">
          Execute primeiro o reconhecimento para ver os instrumentos encontrados.
        </CardContent>
      </Card>
    );
  }

  if (score.data.parts.length === 1) {
    const only = score.data.parts[0];
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
          <Badge tone="ok">Papel individual detetado</Badge>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Este projeto contém apenas <strong>{only.name}</strong> — não há
            nada para separar.
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setPreview(only)}>
              <Eye className="h-4 w-4" /> Ver papel
            </Button>
            <Button onClick={onGoExport}>
              <Download className="h-4 w-4" /> Ir direto para Exportar
            </Button>
          </div>
          {preview && (
            <PartPreview
              projectId={projectId}
              part={preview}
              onClose={() => setPreview(null)}
            />
          )}
        </CardContent>
      </Card>
    );
  }

  // agrupar as partes por instrumento (Clarinete I/II/III juntos, etc.)
  const families = new Map<string, PartInfo[]>();
  for (const part of score.data.parts) {
    const key = part.canonical || part.name || "Outros";
    families.set(key, [...(families.get(key) ?? []), part]);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Instrumentos — separados por família</CardTitle>
        <CardDescription>
          Cada instrumento mostra os compassos com nível de confiança baixo,
          para saber exatamente o que rever antes de exportar.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {[...families.entries()].map(([family, parts]) => (
          <div key={family}>
            <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <FileMusic className="h-4 w-4 text-violet-500" />
              {family}
              <Badge tone="muted">{parts.length} parte(s)</Badge>
            </h4>
            <div className="flex flex-col gap-2">
              {parts.map((part) => {
                const doubtRows = score.data!.doubtful_measures[part.id] ?? [];
                const doubtNotes = doubtRows.reduce((s, r) => s + r.notes, 0);
                return (
                  <div
                    key={part.id}
                    onClick={() => setPreview(part)}
                    className="cursor-pointer rounded-lg border border-slate-200 px-3 py-2.5 transition-colors hover:border-violet-400/60 dark:border-slate-800 dark:hover:border-violet-500/50"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Eye className="h-4 w-4 shrink-0 text-slate-400" />
                        <div>
                          <span className="text-sm font-medium">{part.name}</span>
                          <span className="ml-2 text-xs text-slate-500">
                            «{part.raw_name}» · {part.measures} compassos
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <InstrumentAssign projectId={projectId} part={part} />
                        {doubtNotes === 0 ? (
                          <Badge tone="ok">
                            <Check className="h-3 w-3" /> sem dúvidas
                          </Badge>
                        ) : (
                          <Badge tone="warn">
                            {doubtNotes} nota(s) em {doubtRows.length} compasso(s)
                          </Badge>
                        )}
                        <Badge
                          tone={
                            part.confidence >= 0.9
                              ? "ok"
                              : part.confidence >= 0.6
                                ? "warn"
                                : "error"
                          }
                          title="Confiança na identificação do instrumento"
                        >
                          {(part.confidence * 100).toFixed(0)}%
                        </Badge>
                      </div>
                    </div>
                    {doubtRows.length > 0 && (
                      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                        <span className="text-amber-600 dark:text-amber-400">
                          ⚠ Compassos com confiança baixa:
                        </span>
                        {doubtRows.map((r) => (
                          <span
                            key={r.measure}
                            className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-amber-800 dark:bg-amber-500/15 dark:text-amber-300"
                            title={`${r.notes} nota(s), mínimo ${(r.min_confidence * 100).toFixed(0)}%`}
                          >
                            {r.measure}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
        {preview && (
          <PartPreview
            projectId={projectId}
            part={preview}
            onClose={() => setPreview(null)}
          />
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */

function PartPreview({
  projectId,
  part,
  onClose,
}: {
  projectId: number;
  part: PartInfo;
  onClose: () => void;
}) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(api.musicxmlUrl(projectId, part.id));
        if (!res.ok) throw new Error("Não foi possível gerar o papel");
        const xml = await res.text();
        if (cancelled || !sheetRef.current) return;
        sheetRef.current.innerHTML = "";
        const osmd = new OpenSheetMusicDisplay(sheetRef.current, {
          autoResize: true,
          drawTitle: true,
          backend: "svg",
        });
        await osmd.load(xml);
        if (cancelled) return;
        osmd.render();
        setStatus("ready");
      } catch (e) {
        setMessage(e instanceof Error ? e.message : String(e));
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, part.id]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        onClick={(e) => e.stopPropagation()}
        className="flex h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-slate-100"
      >
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
          <div className="flex items-center gap-2">
            <FileMusic className="h-4 w-4 text-violet-600" />
            <span className="text-sm font-semibold text-slate-900">
              {part.name} — papel individual
            </span>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-auto p-6">
          {status === "loading" && (
            <div className="flex h-full items-center justify-center text-slate-500">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" /> A preparar o
              papel de {part.name}…
            </div>
          )}
          {status === "error" && (
            <div className="flex h-full items-center justify-center text-sm text-slate-500">
              {message}
            </div>
          )}
          <div ref={sheetRef} />
        </div>
      </motion.div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ExportStep({
  projectId,
  onError,
}: {
  projectId: number;
  onError: (m: string) => void;
}) {
  const [formats, setFormats] = useState<string[]>(["pdf", "musicxml"]);
  const [selected, setSelected] = useState<string[]>([]);
  const [separate, setSeparate] = useState(true);
  const [files, setFiles] = useState<ExportedFile[]>([]);

  const score = useQuery({
    queryKey: ["score", projectId],
    queryFn: () => api.score(projectId),
    retry: false,
  });
  const validation = useQuery({
    queryKey: ["validation", projectId],
    queryFn: () => api.validate(projectId),
    retry: false,
    enabled: !!score.data,
  });

  const run = useMutation({
    mutationFn: () =>
      api.exportScore(projectId, {
        formats,
        part_ids: selected.length ? selected : undefined,
        separate,
      }),
    onSuccess: (r) => setFiles(r.files),
    onError: (e: Error) => onError(e.message),
  });

  if (!score.data) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-sm text-slate-500">
          Execute primeiro o reconhecimento para poder exportar.
        </CardContent>
      </Card>
    );
  }

  const toggle = (list: string[], v: string) =>
    list.includes(v) ? list.filter((x) => x !== v) : [...list, v];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Separação e exportação</CardTitle>
          <CardDescription>
            Escolha os instrumentos e os formatos. Com «ficheiros individuais»
            cada instrumento gera o seu próprio PDF/MusicXML/MIDI.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Instrumentos (vazio = todos)
            </h4>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelected(score.data!.parts.map((p) => p.id))}
              >
                Selecionar todos
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelected([])}>
                Limpar
              </Button>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-1 gap-1.5 md:grid-cols-2">
            {score.data.parts.map((part) => (
              <label
                key={part.id}
                className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-800"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(part.id)}
                  onChange={() => setSelected((s) => toggle(s, part.id))}
                  className="h-4 w-4 accent-violet-600"
                />
                {part.name}
              </label>
            ))}
          </div>

          <h4 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Formatos
          </h4>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {EXPORT_FORMATS.map((f) => (
              <button
                key={f}
                onClick={() => setFormats((s) => toggle(s, f))}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium uppercase transition-colors",
                  formats.includes(f)
                    ? "border-violet-600 bg-violet-600 text-white"
                    : "border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-400"
                )}
              >
                {f}
              </button>
            ))}
          </div>

          <label className="mt-4 flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={separate}
              onChange={(e) => setSeparate(e.target.checked)}
              className="h-4 w-4 accent-violet-600"
            />
            Gerar ficheiros individuais por instrumento
          </label>

          <Button
            className="mt-5"
            onClick={() => run.mutate()}
            disabled={run.isPending || !formats.length}
          >
            {run.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Exportar
          </Button>

          {!!files.length && (
            <div className="mt-4 flex flex-col gap-1.5">
              {files.map((f) => (
                <a
                  key={f.url}
                  href={fileUrl(f.url)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-violet-600 underline dark:text-violet-400"
                >
                  {f.name}
                </a>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Verificação automática</CardTitle>
          <CardDescription>
            Durações de compassos, âmbitos, repetições, ligaduras e erros de OCR.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {validation.data ? (
            <>
              <div className="flex flex-wrap gap-2">
                <Badge tone={validation.data.ok ? "ok" : "error"}>
                  {validation.data.ok ? "Pronto a exportar" : "Erros por resolver"}
                </Badge>
                {Object.entries(validation.data.summary).map(([k, v]) => (
                  <Badge key={k} tone="muted">
                    {k.replace(/_/g, " ")}: {v}
                  </Badge>
                ))}
              </div>
              <div className="mt-4 flex max-h-80 flex-col gap-1.5 overflow-y-auto">
                {validation.data.issues.map((issue, i) => (
                  <div
                    key={i}
                    className={cn(
                      "rounded-lg px-3 py-2 text-xs",
                      issue.severity === "erro"
                        ? "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300"
                        : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
                    )}
                  >
                    <strong>{issue.part}</strong> — {issue.message}
                  </div>
                ))}
                {!validation.data.issues.length && (
                  <p className="text-sm text-slate-500">
                    Nenhum problema encontrado. 🎉
                  </p>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">A verificar…</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
