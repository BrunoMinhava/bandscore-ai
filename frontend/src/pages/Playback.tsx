import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Midi } from "@tonejs/midi";
import {
  ArrowLeft,
  Loader2,
  Pause,
  Play,
  Repeat,
  Square,
  Timer,
  Volume2,
  VolumeX,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface TrackState {
  name: string;
  muted: boolean;
  volume: number; // 0–1
}

function midiToFreq(m: number) {
  return 440 * Math.pow(2, (m - 69) / 12);
}

export default function PlaybackPage() {
  const { id } = useParams();
  const projectId = Number(id);

  const [midi, setMidi] = useState<Midi | null>(null);
  const [tracks, setTracks] = useState<TrackState[]>([]);
  const [rate, setRate] = useState(1.0);
  const [loop, setLoop] = useState(false);
  const [metronome, setMetronome] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");

  const ctxRef = useRef<AudioContext | null>(null);
  const loopTimerRef = useRef<number | null>(null);
  const tracksRef = useRef<TrackState[]>([]);
  tracksRef.current = tracks;
  const rateRef = useRef(rate);
  rateRef.current = rate;
  const loopRef = useRef(loop);
  loopRef.current = loop;
  const metronomeRef = useRef(metronome);
  metronomeRef.current = metronome;

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(api.midiUrl(projectId));
        if (!res.ok) throw new Error("Partitura ainda não reconhecida");
        const buffer = await res.arrayBuffer();
        const parsed = new Midi(buffer);
        setMidi(parsed);
        setTracks(
          parsed.tracks
            .filter((t) => t.notes.length)
            .map((t, i) => ({
              name: t.name || t.instrument.name || `Instrumento ${i + 1}`,
              muted: false,
              volume: 0.8,
            }))
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  function stop() {
    if (loopTimerRef.current) window.clearTimeout(loopTimerRef.current);
    loopTimerRef.current = null;
    ctxRef.current?.close().catch(() => undefined);
    ctxRef.current = null;
    setPlaying(false);
  }

  function play() {
    if (!midi) return;
    stop();
    const ctx = new AudioContext();
    ctxRef.current = ctx;
    const speed = rateRef.current;
    const start = ctx.currentTime + 0.25;
    const master = ctx.createGain();
    master.gain.value = 0.6;
    master.connect(ctx.destination);

    const audible = midi.tracks.filter((t) => t.notes.length);
    audible.forEach((track, i) => {
      const state = tracksRef.current[i];
      if (!state || state.muted) return;
      const gain = ctx.createGain();
      gain.gain.value = state.volume;
      gain.connect(master);
      const isPercussion = track.channel === 9;
      for (const note of track.notes) {
        const t0 = start + note.time / speed;
        const dur = Math.max(0.06, note.duration / speed);
        if (isPercussion) {
          scheduleClick(ctx, gain, t0, 0.4, 180);
          continue;
        }
        const osc = ctx.createOscillator();
        osc.type = "triangle";
        osc.frequency.value = midiToFreq(note.midi);
        const env = ctx.createGain();
        env.gain.setValueAtTime(0, t0);
        env.gain.linearRampToValueAtTime(note.velocity * 0.9, t0 + 0.015);
        env.gain.setTargetAtTime(0, t0 + dur - 0.04, 0.03);
        osc.connect(env).connect(gain);
        osc.start(t0);
        osc.stop(t0 + dur + 0.1);
      }
    });

    const duration = midi.duration / speed;

    if (metronomeRef.current) {
      const bpm = midi.header.tempos[0]?.bpm ?? 120;
      const beat = 60 / bpm / speed;
      const metroGain = ctx.createGain();
      metroGain.gain.value = 0.5;
      metroGain.connect(master);
      for (let t = 0; t < duration; t += beat) {
        scheduleClick(ctx, metroGain, start + t, 0.25, 1100);
      }
    }

    setPlaying(true);
    loopTimerRef.current = window.setTimeout(() => {
      if (loopRef.current) play();
      else stop();
    }, (duration + 0.6) * 1000);
  }

  function scheduleClick(
    ctx: AudioContext,
    out: AudioNode,
    time: number,
    level: number,
    freq: number
  ) {
    const osc = ctx.createOscillator();
    osc.type = "square";
    osc.frequency.value = freq;
    const env = ctx.createGain();
    env.gain.setValueAtTime(level, time);
    env.gain.exponentialRampToValueAtTime(0.001, time + 0.05);
    osc.connect(env).connect(out);
    osc.start(time);
    osc.stop(time + 0.06);
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <div className="flex items-center gap-3">
        <Link to={`/project/${projectId}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4" /> Projeto
          </Button>
        </Link>
        <h1 className="text-xl font-bold tracking-tight">Reprodução</h1>
      </div>

      {error && (
        <p className="mt-6 text-sm text-slate-500">{error}</p>
      )}

      {!midi && !error && (
        <div className="mt-10 flex items-center justify-center text-slate-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" /> A preparar o áudio…
        </div>
      )}

      {midi && (
        <>
          <Card className="mt-6">
            <CardContent className="flex flex-wrap items-center gap-4 p-5">
              <div className="flex items-center gap-2">
                <Button size="icon" onClick={() => (playing ? stop() : play())}>
                  {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </Button>
                <Button variant="outline" size="icon" onClick={stop}>
                  <Square className="h-4 w-4" />
                </Button>
              </div>

              <div className="flex items-center gap-2 text-sm">
                <Timer className="h-4 w-4 text-slate-400" />
                <span className="text-slate-500">Andamento</span>
                <input
                  type="range"
                  min={0.4}
                  max={1.8}
                  step={0.05}
                  value={rate}
                  onChange={(e) => setRate(Number(e.target.value))}
                  className="w-36 accent-violet-600"
                />
                <span className="w-12 font-mono text-xs">{(rate * 100).toFixed(0)}%</span>
              </div>

              <button
                onClick={() => setLoop((v) => !v)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
                  loop
                    ? "border-violet-600 bg-violet-600 text-white"
                    : "border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-400"
                )}
              >
                <Repeat className="h-3.5 w-3.5" /> Loop
              </button>
              <button
                onClick={() => setMetronome((v) => !v)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
                  metronome
                    ? "border-violet-600 bg-violet-600 text-white"
                    : "border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-400"
                )}
              >
                <Timer className="h-3.5 w-3.5" /> Metrónomo
              </button>
            </CardContent>
          </Card>

          <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Misturador — instrumento isolado ou em grupo
          </h2>
          <div className="mt-3 flex flex-col gap-2">
            {tracks.map((t, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-lg border border-slate-200 px-4 py-2.5 dark:border-slate-800"
              >
                <button
                  onClick={() =>
                    setTracks((prev) =>
                      prev.map((x, j) => (j === i ? { ...x, muted: !x.muted } : x))
                    )
                  }
                  className={cn(
                    "shrink-0",
                    t.muted ? "text-slate-400" : "text-violet-500"
                  )}
                  title={t.muted ? "Ativar" : "Silenciar"}
                >
                  {t.muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                </button>
                <span
                  className={cn(
                    "w-48 truncate text-sm",
                    t.muted && "text-slate-400 line-through"
                  )}
                >
                  {t.name}
                </span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={t.volume}
                  onChange={(e) =>
                    setTracks((prev) =>
                      prev.map((x, j) =>
                        j === i ? { ...x, volume: Number(e.target.value) } : x
                      )
                    )
                  }
                  className="flex-1 accent-violet-600"
                />
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-400">
            As alterações ao misturador e andamento aplicam-se ao próximo
            arranque da reprodução. Sons por soundfont de alta qualidade estão
            no roadmap.
          </p>
        </>
      )}
    </div>
  );
}
