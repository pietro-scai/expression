/**
 * TypeScript mirror of the expression JSON output schema.
 * Both `expression describe` and `expression run` emit { models: ExpressionModelEntry[] }.
 * Keep in sync with framework/src/expression/outputs.py.
 */

export type ExpressionAxisSpec = {
  kind: "periods" | "dim";
  values: (string | number)[];
};

export type ExpressionRowEntry = {
  name: string;
  kind: "row";
  doc?: string | null;
  depends_on: string[];
  columns: ExpressionAxisSpec[];
  /** Only present in `expression run` output. */
  results?: Record<string, number | string>;
  source?: string | null;
};

export type ExpressionScalarEntry = {
  name: string;
  kind: "scalar";
  doc?: string | null;
  depends_on: string[];
  /** Only present in `expression run` output. */
  value?: number | string | null;
  type?: string;
  source?: string | null;
};

export type ExpressionGlobValue = {
  value: number | string | boolean;
  default: number | string | boolean;
  type: string;
  doc?: string | null;
};

export type ExpressionDagNode = { name: string; kind: "glob" | "row" | "scalar" };
export type ExpressionDagEdge = { from: string; to: string };

export type ExpressionModelMeta = {
  name: string;
  doc?: string | null;
  axes: Record<string, ExpressionAxisSpec>;
  dag: { nodes: ExpressionDagNode[]; edges: ExpressionDagEdge[] };
  mermaid: string;
};

/** One entry in the `models` array for both `describe` and `run` output. */
export type ExpressionModelEntry = {
  model: ExpressionModelMeta;
  /** Glob definitions (describe) or solved glob values (run). */
  inputs: Record<string, ExpressionGlobValue>;
  tables: ExpressionRowEntry[];
  scalars: ExpressionScalarEntry[];
};

/** Top-level shape of workspace/outputs/model.json and workspace/outputs/result.json. */
export type ExpressionOutput = {
  models: ExpressionModelEntry[];
};
