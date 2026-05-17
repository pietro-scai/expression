"use client"

import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import type {
  AxisSpec,
  GlobValue,
  ModelSnapshot,
  RowDefinition,
  TableResult,
} from "@/lib/model-types"
import { CodeBlockEditor } from "@/components/ai-elements/code-block-editor"
import { Accordion as AccordionPrimitive } from "radix-ui"
import {
  CheckCircle2Icon,
  CircleDashedIcon,
  InfoIcon,
  XCircleIcon,
} from "lucide-react"
import { useMemo, useState } from "react"
import { useModel } from "./model-context"
import { ModelGraph } from "./model-graph"

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function formatValue(v: number | string | boolean | null | undefined): string {
  if (v === null || v === undefined) return "—"
  if (typeof v === "boolean") return v ? "true" : "false"
  if (typeof v === "number") {
    if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
    if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(2)}K`
    if (!Number.isInteger(v)) return v.toFixed(4).replace(/\.?0+$/, "")
    return String(v)
  }
  return String(v)
}

function extractModelNames(source: string): string[] {
  const names: string[] = []
  for (const m of source.matchAll(/^class\s+(\w+)\s*\([^)]*Model[^)]*\)/gm)) {
    names.push(m[1])
  }
  return names
}

// ---------------------------------------------------------------------------
// shared sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status?: "ok" | "error" }) {
  if (!status) return null
  if (status === "ok") {
    return (
      <Badge
        className="gap-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
        variant="secondary"
      >
        <CheckCircle2Icon className="size-3" />
        solved
      </Badge>
    )
  }
  return (
    <Badge
      className="gap-1 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
      variant="secondary"
    >
      <XCircleIcon className="size-3" />
      error
    </Badge>
  )
}

function InputsBar({ inputs }: { inputs: Record<string, GlobValue> }) {
  const entries = Object.entries(inputs)
  if (entries.length === 0) return null
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
  )
}

function InfoTooltip({ doc }: { doc?: string | null }) {
  if (!doc) return null
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <InfoIcon className="size-3 shrink-0 cursor-help text-muted-foreground/50 hover:text-muted-foreground" />
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-xs">
        {doc}
      </TooltipContent>
    </Tooltip>
  )
}

function resultKey(parts: (number | string)[]): string {
  return parts.map(String).join(",")
}

function axisKey(axis: AxisSpec): string {
  return `${axis.kind}:${axis.values.map(String).join("|")}`
}

function isMultiAxis(columns: AxisSpec[]): boolean {
  return columns.length > 1
}

function axisSignature(columns: AxisSpec[]): string {
  return columns.map(axisKey).join("/")
}

function collectExtraAxes(
  rows: DisplayRow[],
  tables: Map<string, TableResult>
) {
  const seen = new Map<string, AxisSpec>()
  for (const row of rows) {
    const columns = tables.get(row.name)?.columns ?? row.columns
    for (const axis of columns.slice(1)) {
      const key = axisKey(axis)
      if (!seen.has(key)) seen.set(key, axis)
    }
  }
  return [...seen.values()]
}

function selectedAxisValue(
  axis: AxisSpec,
  dimensionSelection: Record<string, string>
) {
  const selectedIndex = Number(dimensionSelection[axisKey(axis)] ?? 0)
  return axis.values[selectedIndex] ?? axis.values[0]
}

type DisplayRow = RowDefinition

function ModelDataRow({
  row,
  table,
  primaryValues,
  dimensionSelection,
}: {
  row: DisplayRow
  table?: TableResult
  primaryValues: (number | string)[]
  dimensionSelection: Record<string, string>
}) {
  const columns = table?.columns ?? row.columns
  const extraAxes = columns.slice(1)
  const hasExtraAxes = isMultiAxis(columns)
  const selectedAxisValues = extraAxes.map((axis) =>
    selectedAxisValue(axis, dimensionSelection)
  )

  return (
    <tr className="transition-colors hover:bg-muted/30">
      <td className="sticky left-0 z-10 min-w-[180px] bg-background px-4 py-2.5 align-top">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-1.5">
            <span className="font-mono">{row.name}</span>
            {hasExtraAxes && (
              <Badge
                variant="secondary"
                className="h-5 px-1.5 font-mono text-[10px]"
              >
                {columns.length}D
              </Badge>
            )}
            <InfoTooltip doc={row.doc} />
          </div>
          {extraAxes.length > 0 && (
            <span className="font-mono text-[11px] text-muted-foreground">
              {selectedAxisValues.map(String).join(" / ")}
            </span>
          )}
        </div>
      </td>
      {primaryValues.map((p) => {
        const key = hasExtraAxes
          ? resultKey([p, ...selectedAxisValues])
          : String(p)
        return (
          <td
            key={String(p)}
            className="px-4 py-2.5 text-right font-mono tabular-nums"
          >
            {table ? formatValue(table.results[key]) : "—"}
          </td>
        )
      })}
    </tr>
  )
}

function ModelTable({ snapshot }: { snapshot: ModelSnapshot }) {
  const { definition, execution } = snapshot
  const defRows = definition?.rows ?? []
  const execTables: TableResult[] = execution?.tables ?? []

  const rows: DisplayRow[] =
    defRows.length > 0
      ? defRows
      : execTables.map((t) => ({
          name: t.name,
          kind: "row" as const,
          doc: t.doc,
          depends_on: t.depends_on,
          columns: t.columns,
          source: undefined,
        }))

  const tableByName = new Map(execTables.map((t) => [t.name, t]))
  const primaryValues =
    execTables[0]?.columns[0]?.values ?? rows[0]?.columns[0]?.values ?? []
  const dimensionAxes = collectExtraAxes(rows, tableByName)
  const [dimensionSelection, setDimensionSelection] = useState<
    Record<string, string>
  >({})

  if (rows.length === 0) {
    return (
      <div className="px-4 py-6 text-center text-xs text-muted-foreground">
        No rows yet.
      </div>
    )
  }

  return (
    <div className="overflow-auto">
      {dimensionAxes.length > 0 && (
        <div className="sticky left-0 z-20 flex min-w-max items-center gap-2 border-b bg-background px-4 py-2">
          <span className="text-xs font-medium text-muted-foreground">
            Slice
          </span>
          {dimensionAxes.map((axis, axisIndex) => {
            const key = axisKey(axis)
            const selected = dimensionSelection[key] ?? "0"
            return (
              <Select
                key={key}
                value={
                  axis.values[Number(selected)] === undefined ? "0" : selected
                }
                onValueChange={(value) =>
                  setDimensionSelection((current) => ({
                    ...current,
                    [key]: value,
                  }))
                }
              >
                <SelectTrigger
                  aria-label={`Select slice for dimension ${axisIndex + 1}`}
                  className="h-7 w-auto min-w-24 gap-1 rounded px-2 py-0 text-xs"
                >
                  <SelectValue placeholder={`Dim ${axisIndex + 1}`} />
                </SelectTrigger>
                <SelectContent>
                  {axis.values.map((value, valueIndex) => (
                    <SelectItem
                      key={`${valueIndex}-${String(value)}`}
                      value={String(valueIndex)}
                    >
                      {String(value)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )
          })}
        </div>
      )}
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="border-b bg-muted/40">
            <th className="sticky left-0 z-10 min-w-[140px] bg-muted/40 px-4 py-2 text-left font-medium text-muted-foreground">
              Row
            </th>
            {primaryValues.map((p) => (
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
            const table = tableByName.get(row.name)
            const columns = table?.columns ?? row.columns
            return (
              <ModelDataRow
                key={`${row.name}:${axisSignature(columns)}`}
                row={row}
                table={table}
                primaryValues={primaryValues}
                dimensionSelection={dimensionSelection}
              />
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ErrorBlock({ message }: { message?: string }) {
  return (
    <div className="px-4 py-3">
      <pre className="overflow-x-auto rounded-md bg-red-50 p-3 font-mono text-xs break-all whitespace-pre-wrap text-red-800 dark:bg-red-900/20 dark:text-red-300">
        {message ?? "Unknown error"}
      </pre>
    </div>
  )
}

// Flush accordion content — no horizontal padding so tables can be edge-to-edge.
function AccordionContentFlush({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <AccordionPrimitive.Content
      data-slot="accordion-content"
      className={cn(
        "overflow-hidden data-open:animate-accordion-down data-closed:animate-accordion-up",
        className
      )}
    >
      {children}
    </AccordionPrimitive.Content>
  )
}

// ---------------------------------------------------------------------------
// tab content components
// ---------------------------------------------------------------------------

function ModelTab({ snapshots }: { snapshots: ModelSnapshot[] }) {
  const source = snapshots[0]?.source ?? ""
  const names = useMemo(() => extractModelNames(source), [source])
  const defaultValues = useMemo(
    () => snapshots.map((_, i) => String(i)),
    [snapshots]
  )

  return (
    <Accordion
      type="multiple"
      defaultValue={defaultValues}
      className="rounded-none border-x-0 border-t-0 border-b-0"
    >
      {snapshots.map((snapshot, i) => {
        const name = names[i] ?? snapshot.definition?.name ?? `Model ${i + 1}`
        const doc = snapshot.definition?.doc
        const inputs = snapshot.execution?.inputs
        const isError = snapshot.execution?.status === "error"

        return (
          <AccordionItem
            key={i}
            value={String(i)}
            className="border-b last:border-b-0 data-open:bg-transparent"
          >
            <AccordionTrigger className="px-4 py-2.5 hover:no-underline">
              <div className="flex min-w-0 flex-1 items-center gap-2 pr-2">
                <span className="font-mono text-sm font-semibold">{name}</span>
                {doc && (
                  <span className="truncate text-xs text-muted-foreground">
                    {doc}
                  </span>
                )}
                <div className="ml-auto shrink-0">
                  <StatusBadge status={snapshot.execution?.status} />
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContentFlush>
              {inputs && Object.keys(inputs).length > 0 && (
                <InputsBar inputs={inputs} />
              )}
              {isError ? (
                <ErrorBlock message={snapshot.execution?.message} />
              ) : (
                <ModelTable snapshot={snapshot} />
              )}
            </AccordionContentFlush>
          </AccordionItem>
        )
      })}
    </Accordion>
  )
}

function PythonTab({ snapshots }: { snapshots: ModelSnapshot[] }) {
  const source = snapshots[0]?.source ?? ""
  if (!source) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
        No source available.
      </div>
    )
  }
  return (
    <CodeBlockEditor
      className="flex-co m-0! flex min-h-0 flex-1 border-none! bg-transparent! p-0!"
      code={source}
      language="python"
      minHeight={280}
    />
  )
}

function JsonTab({ code }: { code: string }) {
  return (
    <CodeBlockEditor
      className="m-0! flex min-h-0 flex-1 flex-col border-none! bg-transparent! p-0!"
      code={code}
      language="json"
      minHeight={280}
      readOnly
    />
  )
}

// ---------------------------------------------------------------------------
// empty state
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <CircleDashedIcon className="size-8 text-muted-foreground/40" />
      <p className="text-sm text-muted-foreground">
        No model yet. Start chatting to build one.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// root component
// ---------------------------------------------------------------------------

type PanelTab = "model" | "graph" | "python" | "result-json" | "model-json"

export function ModelPanel({ className }: { className?: string }) {
  const { snapshots } = useModel()
  const [tab, setTab] = useState<PanelTab>("model")

  const resultJson = useMemo(
    () =>
      JSON.stringify(
        {
          models: snapshots.map((s) => ({
            inputs: s.execution?.inputs ?? {},
            tables: s.execution?.tables ?? [],
            scalars: s.execution?.scalars ?? [],
          })),
        },
        null,
        2
      ),
    [snapshots]
  )

  // Use the raw model.json string streamed from the sandbox when available,
  // so the tab shows exactly what sweet describe wrote — no round-trip drift.
  const modelJson = useMemo(() => {
    const raw = snapshots[0]?.rawModelJson
    return raw ?? "{}"
  }, [snapshots])

  if (snapshots.length === 0) {
    return (
      <div
        className={cn(
          "flex h-full flex-col overflow-hidden border-l bg-background",
          className
        )}
      >
        <EmptyState />
      </div>
    )
  }

  const overallStatus = snapshots.some((s) => s.execution?.status === "error")
    ? ("error" as const)
    : snapshots.some((s) => s.execution?.status === "ok")
      ? ("ok" as const)
      : undefined

  return (
    <TooltipProvider>
      <div
        className={cn(
          "flex h-full flex-col overflow-hidden border-l bg-background",
          className
        )}
      >
        {/* Tab bar */}
        <div className="flex shrink-0 items-center gap-2 border-b px-3 py-1.5">
          <Tabs value={tab} onValueChange={(v) => setTab(v as PanelTab)}>
            <TabsList className="h-7">
              <TabsTrigger value="model" className="h-6 px-2.5 text-xs">
                Model
              </TabsTrigger>
              <TabsTrigger value="graph" className="h-6 px-2.5 text-xs">
                Graph
              </TabsTrigger>
              <TabsTrigger value="python" className="h-6 px-2.5 text-xs">
                Python
              </TabsTrigger>
              <TabsTrigger
                value="result-json"
                className="h-6 px-2.5 font-mono text-xs"
              >
                result.json
              </TabsTrigger>
              <TabsTrigger
                value="model-json"
                className="h-6 px-2.5 font-mono text-xs"
              >
                model.json
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="ml-auto">
            <StatusBadge status={overallStatus} />
          </div>
        </div>

        {/* Content */}
        <div className="min-h-0 flex-1 overflow-hidden">
          {tab === "model" && (
            <div className="h-full overflow-auto">
              <ModelTab snapshots={snapshots} />
            </div>
          )}
          {tab === "graph" && <ModelGraph snapshots={snapshots} />}
          {tab === "python" && (
            <div className="flex h-full min-h-0 flex-col p-2">
              <PythonTab snapshots={snapshots} />
            </div>
          )}
          {tab === "result-json" && (
            <div className="flex h-full min-h-0 flex-col p-2">
              <JsonTab code={resultJson} />
            </div>
          )}
          {tab === "model-json" && (
            <div className="flex h-full min-h-0 flex-col p-2">
              <JsonTab code={modelJson} />
            </div>
          )}
        </div>
      </div>
    </TooltipProvider>
  )
}
