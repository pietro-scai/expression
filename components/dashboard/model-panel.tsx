"use client";

import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { GlobValue, ModelSnapshot, TableResult } from "@/lib/model-types";
import {
  CheckCircle2Icon,
  CircleDashedIcon,
  InfoIcon,
  XCircleIcon,
} from "lucide-react";
import { useModel } from "./model-context";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function formatValue(v: number | string | boolean | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") {
    if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
    if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(2)}K`;
    if (!Number.isInteger(v)) return v.toFixed(4).replace(/\.?0+$/, "");
    return String(v);
  }
  return String(v);
}

// ---------------------------------------------------------------------------
// status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status?: "ok" | "error" }) {
  if (!status) return null;
  if (status === "ok") {
    return (
      <Badge
        className="gap-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
        variant="secondary"
      >
        <CheckCircle2Icon className="size-3" />
        solved
      </Badge>
    );
  }
  return (
    <Badge
      className="gap-1 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
      variant="secondary"
    >
      <XCircleIcon className="size-3" />
      error
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// inputs bar
// ---------------------------------------------------------------------------

function InputsBar({ inputs }: { inputs: Record<string, GlobValue> }) {
  const entries = Object.entries(inputs);
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b bg-muted/20 px-4 py-2">
      {entries.map(([name, val]) => (
        <span key={name} className="flex items-center gap-1.5 text-xs">
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="flex cursor-default items-center gap-1">
                <span className="font-mono text-muted-foreground">{name}</span>
                {val.doc && (
                  <InfoIcon className="size-2.5 shrink-0 text-muted-foreground/50" />
                )}
              </span>
            </TooltipTrigger>
            {val.doc && (
              <TooltipContent side="bottom">{val.doc}</TooltipContent>
            )}
          </Tooltip>
          <span className="font-mono font-medium tabular-nums">
            {formatValue(val.value)}
          </span>
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// model table (one row per @row, columns = time periods)
// ---------------------------------------------------------------------------

function InfoTooltip({ doc }: { doc?: string | null }) {
  if (!doc) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <InfoIcon className="size-3 shrink-0 cursor-help text-muted-foreground/50 hover:text-muted-foreground" />
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-xs">
        {doc}
      </TooltipContent>
    </Tooltip>
  );
}

function ModelTable({ snapshot }: { snapshot: ModelSnapshot }) {
  const { definition, execution } = snapshot;

  // Resolve rows: prefer definition (has source) over execution tables
  const defRows = definition?.rows ?? [];
  const execTables: TableResult[] = execution?.tables ?? [];

  const rows =
    defRows.length > 0
      ? defRows
      : execTables.map((t) => ({
          name: t.name,
          kind: "row" as const,
          doc: t.doc,
          depends_on: t.depends_on,
          columns: t.columns,
          source: undefined,
        }));

  // Period labels from first available source
  const periods =
    execTables[0]?.columns[0]?.values ??
    defRows[0]?.columns[0]?.values ??
    [];

  const tableByName = new Map(execTables.map((t) => [t.name, t]));

  if (rows.length === 0) {
    return (
      <div className="px-4 py-8 text-center text-xs text-muted-foreground">
        No rows yet.
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="border-b bg-muted/40">
            <th className="sticky left-0 z-10 min-w-[140px] bg-muted/40 px-4 py-2 text-left font-medium text-muted-foreground">
              Row
            </th>
            {periods.map((p) => (
              <th
                key={String(p)}
                className="px-4 py-2 text-right font-mono font-normal text-muted-foreground"
              >
                {p}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((row) => {
            const table = tableByName.get(row.name);
            return (
              <tr
                key={row.name}
                className="transition-colors hover:bg-muted/30"
              >
                <td className="sticky left-0 z-10 bg-background px-4 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono">{row.name}</span>
                    <InfoTooltip doc={row.doc} />
                  </div>
                </td>
                {periods.map((p) => (
                  <td
                    key={String(p)}
                    className="px-4 py-2.5 text-right font-mono tabular-nums"
                  >
                    {table ? formatValue(table.results[String(p)]) : "—"}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// error block
// ---------------------------------------------------------------------------

function ErrorBlock({ message }: { message?: string }) {
  return (
    <div className="px-4 py-3">
      <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-red-50 p-3 font-mono text-red-800 text-xs dark:bg-red-900/20 dark:text-red-300">
        {message ?? "Unknown error"}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// single-model view (inputs + table/error)
// ---------------------------------------------------------------------------

function ModelView({ snapshot }: { snapshot: ModelSnapshot }) {
  const inputs = snapshot.execution?.inputs;
  const isError = snapshot.execution?.status === "error";
  return (
    <>
      {inputs && Object.keys(inputs).length > 0 && (
        <InputsBar inputs={inputs} />
      )}
      <div className="flex-1 overflow-auto">
        {isError ? (
          <ErrorBlock message={snapshot.execution?.message} />
        ) : (
          <ModelTable snapshot={snapshot} />
        )}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// empty state
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <CircleDashedIcon className="size-8 text-muted-foreground/40" />
      <p className="text-muted-foreground text-sm">
        No model yet. Start chatting to build one.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// root component
// ---------------------------------------------------------------------------

export function ModelPanel({ className }: { className?: string }) {
  const { snapshots, activeModel, setActiveModel } = useModel();
  const names = Object.keys(snapshots);

  if (names.length === 0) {
    return (
      <div
        className={cn(
          "flex h-full flex-col overflow-hidden border-l bg-background",
          className
        )}
      >
        <div className="flex shrink-0 items-center gap-2 border-b px-4 py-3">
          <span className="font-medium text-sm">Model</span>
          <span className="text-muted-foreground text-xs">empty</span>
        </div>
        <EmptyState />
      </div>
    );
  }

  const currentName =
    activeModel && names.includes(activeModel) ? activeModel : names[0];
  const snapshot = snapshots[currentName];

  return (
    <TooltipProvider>
      <div
        className={cn(
          "flex h-full flex-col overflow-hidden border-l bg-background",
          className
        )}
      >
        {/* Tab bar */}
        <div className="flex shrink-0 items-center gap-3 border-b px-4 py-2">
          <Tabs
            value={currentName}
            onValueChange={setActiveModel}
            className="flex-1"
          >
            <TabsList>
              {names.map((name) => (
                <TabsTrigger key={name} value={name}>
                  {name}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <StatusBadge status={snapshot?.execution?.status} />
        </div>

        {/* Content */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {snapshot && <ModelView snapshot={snapshot} />}
        </div>
      </div>
    </TooltipProvider>
  );
}
