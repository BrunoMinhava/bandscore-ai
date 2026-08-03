import * as React from "react";
import { cn } from "@/lib/utils";

const styles: Record<string, string> = {
  default:
    "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300",
  ok: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  warn: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  error: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  muted:
    "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};

export function Badge({
  className,
  tone = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof styles }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        styles[tone],
        className
      )}
      {...props}
    />
  );
}
