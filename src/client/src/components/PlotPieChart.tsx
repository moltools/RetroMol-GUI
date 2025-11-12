import React from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { PieChart as MuiPieChart } from "@mui/x-charts/PieChart";
import type { QueryResult } from "../features/query/types";

export type PieRow = {
  label: string;
  value: number;
};

type PieProps = {
  rows: PieRow[];
  title?: string;
  height?: number;
  /** Show a donut (sets innerRadius as a % of outerRadius) */
  donut?: boolean | number; // true => 60%, or pass a number (e.g., 50)
  /** Minimum slice angle (in degrees) to show an on-slice label */
  minLabelAngle?: number; // default 8 degrees
  /** If too many slices, keep top N by value and group the rest */
  maxSlices?: number; // e.g., 12
  otherLabel?: string; // label for grouped remainder
  /** Sort slices by value descending before truncation */
  sortDesc?: boolean;
  /** Format value in tooltip and legend */
  valueFormatter?: (v: number) => string;
  /** Show % in the on-slice label (arc label) */
  showPercentLabels?: boolean;
  /** Digits for % labels */
  percentDigits?: number;
  /** Legend position */
  legendPosition?: "top" | "right" | "bottom" | "left";
  /** Format label in on-slice label (arc label) */
  labelFormatter?: (label: string, ctx: { value: number; total: number; percent: number }) => string;
}

function prepareData(
  rows: PieRow[],
  maxSlices?: number,
  otherLabel = "Other",
  sortDesc = true
) {
  const clean = rows
    .filter((r) => Number.isFinite(r.value) && r.value > 0)
    .map((r) => ({ label: r.label, value: Number(r.value) }));

  if (clean.length === 0) {
    return { data: [], total: 0 };
  }

  const sorted = sortDesc
    ? [...clean].sort((a, b) => b.value - a.value)
    : clean;

  if (!maxSlices || sorted.length <= maxSlices) {
    return {
      data: sorted.map((r, i) => ({ id: i, value: r.value, label: r.label })),
      total: sorted.reduce((s, r) => s + r.value, 0),
    };
  }

  const head = sorted.slice(0, maxSlices - 1);
  const tail = sorted.slice(maxSlices - 1);
  const otherValue = tail.reduce((s, r) => s + r.value, 0);

  const data = [
    ...head.map((r, i) => ({ id: i, value: r.value, label: r.label })),
    { id: maxSlices - 1, value: otherValue, label: otherLabel },
  ];

  const total = data.reduce((s, d) => s + d.value, 0);
  return { data, total };
}

export const PieChart: React.FC<PieProps> = ({
  rows,
  title,
  height = 280,
  donut = true,
  minLabelAngle = 8,
  maxSlices,
  otherLabel = "Other",
  sortDesc = true,
  valueFormatter = (v) => v.toLocaleString(),
  showPercentLabels = true,
  percentDigits = 0,
  legendPosition = "right",
  labelFormatter = (label, _) => label,
}) => {
  const { data, total } = React.useMemo(
    () => prepareData(rows, maxSlices, otherLabel, sortDesc),
    [rows, maxSlices, otherLabel, sortDesc]
  )

  if (data.length === 0 || total <= 0) {
    return (
      <Box>
        {title && (
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
        )}
        <Typography variant="body2" color="text.secondary">
          No data to display.
        </Typography>
      </Box>
    )
  }

  // Donut inner radius: default 60% if true
  const innerRatio =
    donut === true ? 0.6 : typeof donut === "number" ? Math.max(0, Math.min(95, donut)) / 100 : 0;

  // Apply label formatter
  const dataWithLabels = React.useMemo(() =>
    data.map((d) => {
      const percent = (d.value / total) * 100;
      return { ...d, label: labelFormatter ? labelFormatter(d.label ?? "", { value: d.value, total, percent }) : d.label };
    }),
    [data, total, labelFormatter]
  )

  return (
    <Box sx={{ overflow: "visible" }}>
      {title && (
        <Typography component="h1" variant="subtitle1" gutterBottom>
          {title}
        </Typography>
      )}
      <MuiPieChart
        height={height}
        series={[
          {
            data: dataWithLabels,
            arcLabel: (item) => 
              showPercentLabels
                ? `${((item.value / total) * 100).toFixed(percentDigits)}%`
                : (item.label ?? ""),
            arcLabelMinAngle: minLabelAngle,
            arcLabelRadius: 60,
            valueFormatter: (item) => valueFormatter(item.value),
            innerRadius: innerRatio,
            highlighted: { additionalRadius: 4 },
          }
        ]}
        slotProps={{
          legend: { position: { vertical: "middle", horizontal: "end" } as const },
        }}
        margin = {{
          top: 12,
          right: legendPosition === "right" ? 24 : 12,
          bottom: legendPosition === "bottom" ? 24 : 12,
          left: legendPosition === "left" ? 24 : 12,
        }}
      />
    </Box>
  )
}

/** 
 * Build Pie rows from a SQL result with generic olumn names
 * Pass the column names that hold the label and value
 */
export function pieFromSQLResults(
  result: QueryResult,
  labelCol: string,
  valueCol: string
): PieRow[] {
    return result.rows
      .map((r) => ({
        label: String(r[labelCol]),
        value: Number(r[valueCol]),
      }))
      .filter((x) => Number.isFinite(x.value) && x.value >= 0);
}
