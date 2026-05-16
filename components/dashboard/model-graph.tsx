"use client";

import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  BackgroundVariant,
  type NodeTypes,
  type Node,
  type Edge,
} from "@xyflow/react";
import { cn } from "@/lib/utils";
import type { ModelSnapshot } from "@/lib/model-types";

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------
const NODE_W = 216;
const NODE_H = 128;
const H_GAP = 72;
const V_GAP = 20;
const PAD = 36;
const HEADER_H = 44;
const GROUP_GAP = 80;

// ---------------------------------------------------------------------------
// Source extraction helpers
// ---------------------------------------------------------------------------

/**
 * Find the def line index for a function named `name` inside `source`.
 * Returns {lineIdx, indent} or null if not found.
 * Source may be a single function or an entire file.
 */
function findDef(
  name: string,
  lines: string[]
): { lineIdx: number; indent: number } | null {
  const re = new RegExp(`^(\\s*)def\\s+${name}\\s*[:(]`);
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(re);
    if (m) return { lineIdx: i, indent: m[1].length };
  }
  return null;
}

/**
 * Extract the docstring of function `name` from `source`.
 * Works when source is a single function OR a full file.
 */
function extractDocstring(
  name: string,
  source: string | null | undefined
): string | null {
  if (!source) return null;
  const lines = source.split("\n");
  const found = findDef(name, lines);
  if (!found) return null;
  const { lineIdx, indent } = found;

  for (let i = lineIdx + 1; i < lines.length; i++) {
    const raw = lines[i];
    const t = raw.trim();
    if (!t) continue;
    const lineIndent = raw.length - raw.trimStart().length;
    if (lineIndent <= indent) return null; // exited body without finding docstring
    if (t.startsWith('"""') || t.startsWith("'''")) {
      const q = t.startsWith('"""') ? '"""' : "'''";
      const rest = t.slice(3);
      const close = rest.indexOf(q);
      if (close !== -1) return rest.slice(0, close).trim() || null;
      // Multi-line docstring — collect until closing
      const parts: string[] = rest.trim() ? [rest.trim()] : [];
      for (let j = i + 1; j < lines.length; j++) {
        const jt = lines[j].trim();
        const closeIdx = jt.indexOf(q);
        if (closeIdx !== -1) {
          const part = jt.slice(0, closeIdx).trim();
          if (part) parts.push(part);
          return parts.join(" ").trim() || null;
        }
        if (jt) parts.push(jt);
      }
      return parts.join(" ").trim() || null;
    }
    return null; // first non-blank non-docstring line — no docstring
  }
  return null;
}

/**
 * Extract the body lines (after def + docstring) of function `name`.
 * Returns up to 4 trimmed lines. Works with full-file sources.
 */
function extractBody(
  name: string,
  source: string | null | undefined
): string | null {
  if (!source) return null;
  const lines = source.split("\n");
  const found = findDef(name, lines);
  if (!found) return null;
  const { lineIdx, indent } = found;

  let docDone = false;
  let inDoc = false;
  const body: string[] = [];

  for (let i = lineIdx + 1; i < lines.length; i++) {
    const raw = lines[i];
    const t = raw.trim();
    if (!t) continue;
    const lineIndent = raw.length - raw.trimStart().length;
    if (lineIndent <= indent) break; // exited function body

    if (!docDone) {
      if (t.startsWith('"""') || t.startsWith("'''")) {
        const q = t.startsWith('"""') ? '"""' : "'''";
        const rest = t.slice(3);
        if (rest.includes(q)) { docDone = true; continue; }
        inDoc = true;
        continue;
      }
      if (inDoc) {
        if (t.includes('"""') || t.includes("'''")) {
          inDoc = false;
          docDone = true;
        }
        continue;
      }
      docDone = true;
    }

    if (t.startsWith("def ") || t.startsWith("@")) break;
    body.push(t);
    if (body.length >= 4) break;
  }

  return body.length ? body.join("\n") : null;
}

// ---------------------------------------------------------------------------
// Node data types
// ---------------------------------------------------------------------------

type VarNodeData = {
  name: string;
  kind: "glob" | "row" | "scalar" | "depends";
  doc?: string | null;
  body?: string | null;
  defaultValue?: string | number | boolean;
  upstream?: string;
};

type GroupNodeData = { label: string; doc?: string | null };

// ---------------------------------------------------------------------------
// Kind styling
// ---------------------------------------------------------------------------

const KIND = {
  glob: {
    border: "border-amber-300/80 dark:border-amber-500/50",
    bg: "bg-amber-50/80 dark:bg-amber-950/25",
    badge: "text-amber-700 dark:text-amber-300 bg-amber-100/70 dark:bg-amber-900/50",
    code: "bg-amber-100/50 dark:bg-amber-900/25 text-amber-800 dark:text-amber-200",
  },
  row: {
    border: "border-border",
    bg: "bg-background",
    badge: "text-muted-foreground bg-muted/60",
    code: "bg-muted/50 text-foreground/70",
  },
  scalar: {
    border: "border-sky-300/80 dark:border-sky-500/50",
    bg: "bg-sky-50/80 dark:bg-sky-950/25",
    badge: "text-sky-700 dark:text-sky-300 bg-sky-100/70 dark:bg-sky-900/50",
    code: "bg-sky-100/50 dark:bg-sky-900/25 text-sky-800 dark:text-sky-200",
  },
  depends: {
    border: "border-violet-300/80 dark:border-violet-500/50",
    bg: "bg-violet-50/80 dark:bg-violet-950/25",
    badge: "text-violet-700 dark:text-violet-300 bg-violet-100/70 dark:bg-violet-900/50",
    code: "bg-violet-100/50 dark:bg-violet-900/25 text-violet-800 dark:text-violet-200",
  },
} as const;

// ---------------------------------------------------------------------------
// Custom nodes
// ---------------------------------------------------------------------------

function VarNode({ data }: { data: VarNodeData }) {
  const s = KIND[data.kind];
  return (
    <div
      className={cn("rounded-xl border px-3 py-2.5 shadow-sm text-xs", s.border, s.bg)}
      style={{ width: NODE_W }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-2.5 !border-2 !border-background !bg-muted-foreground/50"
      />

      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="font-mono font-semibold text-[11px] text-foreground leading-none truncate">
          {data.name}
        </span>
        <span className={cn("ml-auto rounded px-1 py-0.5 text-[9px] uppercase tracking-wide font-semibold leading-none shrink-0", s.badge)}>
          {data.kind}
        </span>
      </div>

      {data.kind === "depends" && data.upstream && (
        <p className="text-[10px] font-mono text-violet-600 dark:text-violet-400 mb-1.5 leading-snug">
          ↑ {data.upstream}
        </p>
      )}

      {data.doc && (
        <p className="text-[10px] text-muted-foreground leading-snug mb-2 line-clamp-2">
          {data.doc}
        </p>
      )}

      {data.kind === "glob" && data.defaultValue !== undefined && (
        <div className={cn("rounded px-1.5 py-1 font-mono text-[10px]", s.code)}>
          {String(data.defaultValue)}
        </div>
      )}

      {data.body && (
        <div className={cn("rounded px-2 py-1.5 font-mono text-[9px] leading-relaxed whitespace-pre overflow-hidden", s.code)}>
          {data.body}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        className="!size-2.5 !border-2 !border-background !bg-muted-foreground/50"
      />
    </div>
  );
}

function GroupNode({ data }: { data: GroupNodeData }) {
  return (
    <div className="h-full w-full rounded-2xl border-2 border-border/40 bg-muted/5">
      <div className="flex items-baseline gap-2 px-4 py-2.5 border-b border-border/30">
        <span className="font-mono text-[13px] font-bold text-foreground">{data.label}</span>
        {data.doc && (
          <span className="text-[11px] text-muted-foreground truncate">{data.doc}</span>
        )}
      </div>
      <Handle
        type="source"
        id="cross"
        position={Position.Bottom}
        className="!size-2.5 !border-2 !border-background !bg-primary/70"
      />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  var: VarNode as unknown as NodeTypes[string],
  "model-group": GroupNode as unknown as NodeTypes[string],
};

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

function buildGraph(snapshots: ModelSnapshot[]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const modelGroupId = new Map<string, string>();
  let groupY = 0;

  for (const [mi, snapshot] of snapshots.entries()) {
    const def = snapshot.definition;
    if (!def || def.dag.nodes.length === 0) continue;

    const groupId = `g${mi}`;
    modelGroupId.set(def.name, groupId);

    const { dag, rows, scalars, globals } = def;
    const rowMap = new Map(rows.map((r) => [r.name, r]));
    const scalarMap = new Map(scalars.map((s) => [s.name, s]));

    // Compute topological depth
    const inDeps = new Map<string, string[]>();
    for (const n of dag.nodes) inDeps.set(n.name, []);
    for (const e of dag.edges) inDeps.get(e.to)?.push(e.from);

    const depth = new Map<string, number>();
    function getDepth(name: string): number {
      if (depth.has(name)) return depth.get(name)!;
      const deps = inDeps.get(name) ?? [];
      const d = deps.length === 0 ? 0 : Math.max(...deps.map(getDepth)) + 1;
      depth.set(name, d);
      return d;
    }
    for (const n of dag.nodes) getDepth(n.name);

    // Sort into columns — globs/depends first within each column
    const maxD = Math.max(0, ...depth.values());
    const cols: string[][] = Array.from({ length: maxD + 1 }, () => []);
    const kindOrder: Record<string, number> = { glob: 0, depends: 1, row: 2, scalar: 3 };
    const sorted = [...dag.nodes].sort(
      (a, b) => (kindOrder[a.kind] ?? 2) - (kindOrder[b.kind] ?? 2)
    );
    for (const n of sorted) cols[depth.get(n.name)!].push(n.name);

    // Group dimensions
    const maxColLen = Math.max(...cols.map((c) => c.length), 1);
    const groupW = cols.length * (NODE_W + H_GAP) - H_GAP + PAD * 2;
    const groupH = maxColLen * (NODE_H + V_GAP) - V_GAP + PAD * 2 + HEADER_H;

    nodes.push({
      id: groupId,
      type: "model-group",
      position: { x: 0, y: groupY },
      data: { label: def.name, doc: def.doc } satisfies GroupNodeData,
      style: { width: groupW, height: groupH },
      selectable: false,
      zIndex: 0,
    });

    // Child nodes
    for (const [di, col] of cols.entries()) {
      for (const [ri, name] of col.entries()) {
        const dagNode = dag.nodes.find((n) => n.name === name)!;
        const row = rowMap.get(name);
        const scalar = scalarMap.get(name);
        const glob = globals[name];

        // Source (could be full file for Layer-2 rows)
        const rawSource = row?.source ?? scalar?.source ?? null;

        // Doc: prefer explicit field, fall back to extracting from source
        const doc =
          row?.doc ??
          scalar?.doc ??
          glob?.doc ??
          (rawSource ? extractDocstring(name, rawSource) : null);

        // Formula body (skip for globs and depends)
        const body =
          dagNode.kind === "glob" || dagNode.kind === "depends"
            ? null
            : extractBody(name, rawSource);

        nodes.push({
          id: `${groupId}-${name}`,
          parentId: groupId,
          type: "var",
          position: {
            x: PAD + di * (NODE_W + H_GAP),
            y: PAD + HEADER_H + ri * (NODE_H + V_GAP),
          },
          data: {
            name,
            kind: dagNode.kind,
            doc,
            body,
            defaultValue: glob?.default,
            upstream: dagNode.upstream,
          } satisfies VarNodeData,
          extent: "parent",
          zIndex: 10,
        });
      }
    }

    // Intra-model edges — use var(--border) directly, no hsl() wrapper
    for (const e of dag.edges) {
      edges.push({
        id: `${groupId}|${e.from}>${e.to}`,
        source: `${groupId}-${e.from}`,
        target: `${groupId}-${e.to}`,
        type: "smoothstep",
        style: { stroke: "var(--border)", strokeWidth: 1.5 },
        zIndex: 20,
      });
    }

    groupY += groupH + GROUP_GAP;
  }

  // Cross-model edges
  for (const [mi, snapshot] of snapshots.entries()) {
    const def = snapshot.definition;
    if (!def) continue;
    const groupId = `g${mi}`;
    for (const dagNode of def.dag.nodes) {
      if (dagNode.kind !== "depends" || !dagNode.upstream) continue;
      const srcGroupId = modelGroupId.get(dagNode.upstream);
      if (!srcGroupId) continue;
      edges.push({
        id: `x|${srcGroupId}>${groupId}-${dagNode.name}`,
        source: srcGroupId,
        sourceHandle: "cross",
        target: `${groupId}-${dagNode.name}`,
        type: "smoothstep",
        animated: true,
        style: {
          stroke: "var(--primary)",
          strokeWidth: 1.5,
          strokeDasharray: "5 4",
        },
        zIndex: 30,
      });
    }
  }

  return { nodes, edges };
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export function ModelGraph({ snapshots }: { snapshots: ModelSnapshot[] }) {
  const { nodes, edges } = useMemo(() => buildGraph(snapshots), [snapshots]);

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
        No model definition available.
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.08}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1}
          color="var(--border)"
          className="opacity-40"
        />
        <Controls
          showInteractive={false}
          className="[&>button]:border-border [&>button]:bg-background [&>button]:text-foreground [&>button:hover]:bg-muted"
        />
      </ReactFlow>
    </div>
  );
}
