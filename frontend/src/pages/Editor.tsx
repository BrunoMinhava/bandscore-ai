import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { OpenSheetMusicDisplay } from "opensheetmusicdisplay";
import { ArrowLeft, Loader2, Undo2, ZoomIn, ZoomOut } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function EditorPage() {
  const { id } = useParams();
  const projectId = Number(id);
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<OpenSheetMusicDisplay | null>(null);
  const [zoom, setZoom] = useState(1.0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");

  async function loadScore() {
    if (!containerRef.current) return;
    setStatus("loading");
    try {
      const res = await fetch(api.musicxmlUrl(projectId));
      if (!res.ok) throw new Error("Partitura ainda não reconhecida");
      const xml = await res.text();
      if (!osmdRef.current) {
        osmdRef.current = new OpenSheetMusicDisplay(containerRef.current, {
          autoResize: true,
          drawTitle: true,
          backend: "svg",
        });
      }
      await osmdRef.current.load(xml);
      osmdRef.current.Zoom = zoom;
      osmdRef.current.render();
      setStatus("ready");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  }

  useEffect(() => {
    loadScore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (osmdRef.current && status === "ready") {
      osmdRef.current.Zoom = zoom;
      osmdRef.current.render();
    }
  }, [zoom, status]);

  async function handleUndo() {
    try {
      await api.undo(projectId);
      await loadScore();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-6 py-3 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <Link to={`/project/${projectId}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4" /> Projeto
            </Button>
          </Link>
          <h1 className="text-sm font-semibold">Editor de partitura</h1>
          <Badge tone="muted">edição visual completa no roadmap</Badge>
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="outline" size="icon" onClick={handleUndo} title="Desfazer (backend)">
            <Undo2 className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setZoom((z) => Math.max(0.3, z - 0.15))}
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="w-12 text-center text-xs text-slate-500">
            {(zoom * 100).toFixed(0)}%
          </span>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setZoom((z) => Math.min(4, z + 0.15))}
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-white p-6 dark:bg-slate-100">
        {status === "loading" && (
          <div className="flex h-full items-center justify-center text-slate-500">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> A renderizar…
          </div>
        )}
        {status === "error" && (
          <div className="flex h-full items-center justify-center text-sm text-slate-500">
            {message}
          </div>
        )}
        <div ref={containerRef} />
      </div>
    </div>
  );
}
