"use client";

import type { ChartSpec } from "@/lib/chart-types";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
} from "recharts";

const COLORS: Array<{ light: string; dark: string }> = [
  { light: "#6366f1", dark: "#818cf8" },
  { light: "#f43f5e", dark: "#fb7185" },
  { light: "#10b981", dark: "#34d399" },
  { light: "#f59e0b", dark: "#fbbf24" },
  { light: "#3b82f6", dark: "#60a5fa" },
  { light: "#a855f7", dark: "#c084fc" },
];

function buildChartConfig(series: ChartSpec["series"]): ChartConfig {
  return Object.fromEntries(
    series.map(({ key, label }, i) => [
      key,
      { label, theme: COLORS[i % COLORS.length] },
    ])
  );
}

export function ChartRenderer({ spec }: { spec: ChartSpec }) {
  const { chartType, title, xKey, series, data } = spec;
  const chartConfig = buildChartConfig(series);
  const seriesKeys = series.map((s) => s.key);
  const showLegend = series.length > 1;

  const shared = {
    data: data as Record<string, unknown>[],
    margin: { top: 5, right: 10, left: 0, bottom: 0 },
  };

  return (
    <div className="my-2 rounded-lg border bg-card p-3">
      {title && (
        <p className="mb-2 text-sm font-medium text-muted-foreground">{title}</p>
      )}
      <ChartContainer config={chartConfig} className="h-[220px] w-full">
        {chartType === "line" ? (
          <LineChart {...shared}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey={xKey} tickLine={false} axisLine={false} tickMargin={8} minTickGap={8} />
            <ChartTooltip content={<ChartTooltipContent />} />
            {showLegend && <ChartLegend content={<ChartLegendContent />} />}
            {seriesKeys.map((key) => (
              <Line key={key} dataKey={key} stroke={`var(--color-${key})`} strokeWidth={1.5} dot={false} type="linear" />
            ))}
          </LineChart>
        ) : chartType === "bar" ? (
          <BarChart {...shared}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey={xKey} tickLine={false} axisLine={false} tickMargin={8} minTickGap={8} />
            <ChartTooltip content={<ChartTooltipContent />} />
            {showLegend && <ChartLegend content={<ChartLegendContent />} />}
            {seriesKeys.map((key) => (
              <Bar key={key} dataKey={key} fill={`var(--color-${key})`} radius={2} />
            ))}
          </BarChart>
        ) : (
          <AreaChart {...shared}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey={xKey} tickLine={false} axisLine={false} tickMargin={8} minTickGap={8} />
            <ChartTooltip content={<ChartTooltipContent />} />
            {showLegend && <ChartLegend content={<ChartLegendContent />} />}
            {seriesKeys.map((key) => (
              <Area key={key} dataKey={key} stroke={`var(--color-${key})`} fill={`var(--color-${key})`} fillOpacity={0.15} strokeWidth={1.5} dot={false} type="linear" />
            ))}
          </AreaChart>
        )}
      </ChartContainer>
    </div>
  );
}
