export type AxisSpec = {
  kind: "periods" | "dim";
  values: (string | number)[];
};

export type GlobDefinition = {
  default: number | string | boolean;
  type: string;
  doc?: string | null;
};

export type RowDefinition = {
  name: string;
  kind: "row";
  doc?: string | null;
  depends_on: string[];
  columns: AxisSpec[];
  source?: string | null;
};

export type ScalarDefinition = {
  name: string;
  kind: "scalar";
  doc?: string | null;
  depends_on: string[];
  source?: string | null;
};

export type DagNode = {
  name: string;
  kind: "glob" | "row" | "scalar" | "depends";
  upstream?: string;
};
export type DagEdge = { from: string; to: string };

export type ModelDefinition = {
  name: string;
  doc?: string | null;
  axes: Record<string, AxisSpec>;
  globals: Record<string, GlobDefinition>;
  rows: RowDefinition[];
  scalars: ScalarDefinition[];
  dag: { nodes: DagNode[]; edges: DagEdge[] };
  mermaid: string;
};

export type GlobValue = {
  value: number | string | boolean;
  default: number | string | boolean;
  type: string;
  doc?: string | null;
};

export type TableResult = {
  name: string;
  kind: "row";
  doc?: string | null;
  depends_on: string[];
  columns: AxisSpec[];
  results: Record<string, number | string>;
};

export type ScalarResult = {
  name: string;
  kind: "scalar";
  value: number | string | null;
  type: string;
  doc?: string | null;
};

export type ModelExecution = {
  status: "ok" | "error";
  message?: string;
  inputs?: Record<string, GlobValue>;
  tables?: TableResult[];
  scalars?: ScalarResult[];
};

export type ModelSnapshot = {
  source: string;
  definition?: ModelDefinition;
  execution?: ModelExecution;
  /** Raw model.json string from the sandbox — exactly what sweet describe wrote. */
  rawModelJson?: string;
};
