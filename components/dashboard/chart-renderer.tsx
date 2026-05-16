"use client";

import type { ChartSpec } from "@/lib/chart-types";
import type { ChartConfig } from "@/components/evilcharts/ui/chart";
import { EvilLineChart } from "@/components/evilcharts/charts/line-chart";
import { EvilBarChart } from "@/components/evilcharts/charts/bar-chart";
import { EvilAreaChart } from "@/components/evilcharts/charts/area-chart";

// Default color palette — light/dark pairs
const PALETTE: { light: string[]; dark: string[] }[] = [
  { light: ["#6366f1"], dark: ["#818cf8"] },
  { light: ["#f43f5e"], dark: ["#fb7185"] },
  { light: ["#10b981"], dark: ["#34d399"] },
  { light: ["#f59e0b"], dark: ["#fbbf24"] },
  { light: ["#3b82f6"], dark: ["#60a5fa"] },
  { light: ["#a855f7"], dark: ["#c084fc"] },
];

function buildChartConfig(series: ChartSpec["series"]): ChartConfig {
  return Object.fromEntries(
    series.map(({ key, label }, i) => [
      key,
      {
        label,
        colors: PALETTE[i % PALETTE.length],
      },
    ])
  );
}

export function ChartRenderer({ spec }: { spec: ChartSpec }) {
  const { chartType, title, xKey, series, data } = spec;
  const chartConfig = buildChartConfig(series);

  const shared = {
    chartConfig,
    data: data as Record<string, unknown>[],
    xDataKey: xKey,
    className: "h-[220px] w-full",
  };

  return (
    <div className="my-2 rounded-lg border bg-card p-3">
      {title && (
        <p className="mb-2 text-sm font-medium text-muted-foreground">{title}</p>
      )}
      {chartType === "line" && <EvilLineChart {...shared} />}
      {chartType === "bar" && <EvilBarChart {...shared} />}
      {chartType === "area" && <EvilAreaChart {...shared} />}
    </div>
  );
}
