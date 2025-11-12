import React from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { BarChart } from "@mui/x-charts/BarChart";
import { QueryResult } from "../features/query/types";

type SQLRow = {
  bin_start: number;
  bin_end: number;
  count: number;
}

type HistogramProps = {
  rows: SQLRow[]; // array of data rows from SQL query
  binSize?: number;  // size of each bin
  roundBinEdgeTo?: number; // number of decimal places to round bin edges to
  domain?: { min?: number; max?: number }; // optional domain for x-axis
  title?: string;  // title of the histogram
  height?: number; // height of the chart in px
  formatBinLabel?: (start: number, end: number) => string; // function to format bin labels
}

// Robust rounding for float keys
const roundTo = (x: number, digits = 2) => {
  const k = Math.pow(10, digits);
  return Math.round(x * k) / k;
};

// Fill in missing bins, keep order stable, and ensure safe axes for edge cases
function normalizeBins(
  rows: SQLRow[],
  binSize: number,
  roundBinEdgeTo: number,
  domain?: { min?: number; max?: number }
) {
  if (!rows || rows.length === 0) {
    return { xLabels: [] as string[], series: [] as number[], yMax: 1 };
  }

  const minStart = Math.min(
    ...rows.map((r) => r.bin_start),
    domain?.min ?? Number.POSITIVE_INFINITY
  );
  const maxEnd = Math.max(
    ...rows.map((r) => r.bin_end),
    domain?.max ?? Number.NEGATIVE_INFINITY
  );

  // If domain missing, derive from data; if degenerate (all zeros), force one bin
  const start = Number.isFinite(minStart) ? minStart : 0;
  const end = Number.isFinite(maxEnd) ? maxEnd : start + binSize;

  const effectiveStart = Math.floor(start / binSize) * binSize;
  const effectiveEnd = Math.ceil(end / binSize) * binSize;

  // Map existing rows by bin_start for O(1) lookup
  const byStart = new Map<number, SQLRow>();
  rows.forEach((r) => byStart.set(r.bin_start, r));

  const xLabels: string[] = [];
  const series: number[] = [];

  for (let s = effectiveStart; s < effectiveEnd; s += binSize) {
    const e = s + binSize;
    const roundedEnd = roundTo(e, roundBinEdgeTo);
    const roundedStart = roundTo(s, roundBinEdgeTo);
    const row = byStart.get(roundedStart);
    xLabels.push(`${roundedStart}-${roundedEnd}`);
    series.push(row ? row.count : 0);
  }

  // yMax must be >= 1 so an all-zero series still renders sane axes
  const yMax = Math.max(1, ...series);
  return { xLabels, series, yMax };
}

export const Histogram: React.FC<HistogramProps> = ({
  rows,
  binSize = 5,
  roundBinEdgeTo = 2,
  domain,
  title,
  height = 280,
  formatBinLabel,
}) => {
  // Remap labels if custom formatter is provided
  const { xLabels, series, yMax } = React.useMemo(() => {
    const normalized = normalizeBins(rows, binSize, roundBinEdgeTo, domain);
    if (formatBinLabel) {
      // Recompute labels with custom formatter based on the numeric spans
      // implicit in the label text "start-end"
      const customLabels = normalized.xLabels.map((lab) => {
        const [s, e] = lab.split("-").map(Number);
        return formatBinLabel(s, e);
      })
      return { ...normalized, xLabels: customLabels };
    }
    return normalized;
  }, [rows, binSize, domain, formatBinLabel]);

  if (xLabels.length === 0) {
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

  return (
    <Box>
      {title && (
        <Typography component="h1" variant="subtitle1" gutterBottom>
          {title}
        </Typography>
      )}
      <BarChart
        xAxis={[
          {
            scaleType: "band",
            data: xLabels,
            label: "Bins",
            tickLabelPlacement: "tick",
            tickLabelStyle: { angle: 0, textAnchor: "middle", fontSize: 10 },
          },
        ]}
        yAxis={[{
          min: 0,
          max: yMax,
          valueFormatter: (v: number) => Math.abs(v) >= 1e6 ? v.toExponential(1) : v.toLocaleString(), // sci. notation for large
          tickLabelPlacement: "tick",
          tickLabelStyle: { angle: 0, textAnchor: "end", fontSize: 10 },
        }]}
        series={[ { data: series, label: "Count" } ]}
        margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
        height={height}
      />
    </Box> 
  )
}

/**  Helper: convert SQL rows (e.g., from an API) into the expected shape */
export function histogramFromSQLResults(result: QueryResult): SQLRow[] {
  return result.rows
    .map((r) => ({
      bin_start: Number(r["bin_start"]),
      bin_end: Number(r["bin_end"]),
      count: Number(r["count"] ?? 0),
    }));
}
