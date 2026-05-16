/**
 * TypeScript mirror of the sweet JSON output schema.
 * Both `sweet describe` and `sweet run` emit { models: SweetModelEntry[] }.
 * Keep in sync with framework/src/sweet/outputs.py.
 */

export type SweetAxisSpec = {
  kind: "periods" | "dim";
  values: (string | number)[];
};

export type SweetRowEntry = {
  name: string;
  kind: "row";
  doc?: string | null;
  depends_on: string[];
  columns: SweetAxisSpec[];
  /** Only present in `sweet run` output. */
  results?: Record<string, number | string>;
  source?: string | null;
};

export type SweetScalarEntry = {
  name: string;
  kind: "scalar";
  doc?: string | null;
  depends_on: string[];
  /** Only present in `sweet run` output. */
  value?: number | string | null;
  type?: string;
  source?: string | null;
};

export type SweetGlobValue = {
  value: number | string | boolean;
  default: number | string | boolean;
  type: string;
  doc?: string | null;
};

export type SweetDagNode = { name: string; kind: "glob" | "row" | "scalar" };
export type SweetDagEdge = { from: string; to: string };

export type SweetModelMeta = {
  name: string;
  doc?: string | null;
  axes: Record<string, SweetAxisSpec>;
  dag: { nodes: SweetDagNode[]; edges: SweetDagEdge[] };
  mermaid: string;
};

/** One entry in the `models` array for both `describe` and `run` output. */
export type SweetModelEntry = {
  model: SweetModelMeta;
  /** Glob definitions (describe) or solved glob values (run). */
  inputs: Record<string, SweetGlobValue>;
  tables: SweetRowEntry[];
  scalars: SweetScalarEntry[];
};

/** Top-level shape of workspace/outputs/model.json and workspace/outputs/result.json. */
export type SweetOutput = {
  models: SweetModelEntry[];
};
