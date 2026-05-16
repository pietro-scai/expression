export type ChartType = "line" | "bar" | "area";

export type ChartSeries = {
  key: string;
  label: string;
};

export type ChartSpec = {
  chartType: ChartType;
  title?: string;
  xKey: string;
  series: ChartSeries[];
  data: Record<string, string | number>[];
};
