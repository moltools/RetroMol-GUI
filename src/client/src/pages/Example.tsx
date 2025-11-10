import * as React from "react";
import {
  Box,
  Button,
  CssBaseline,
  TextField,
  MenuItem,
  Select,
  InputLabel,
  FormControl,
  Stack,
  Paper,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

type OrderDir = "asc" | "desc";
type OrderCol = "exact_mass" | "id";

type QueryPayload = {
  name: "compound_by_mass";
  params: { min_mass: number; max_mass: number };
  paging?: { limit?: number; offset?: number };
  order?: { column: OrderCol; dir?: OrderDir };
};

type QueryResult = {
  name: string;
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  limit: number;
  offset: number;
  elapsed_ms: number;
};

export default function Example(props: { disableCustomTheme?: boolean }) {
  // Form state
  const [minMass, setMinMass] = React.useState<number>(100);
  const [maxMass, setMaxMass] = React.useState<number>(300);
  const [orderCol, setOrderCol] = React.useState<OrderCol>("exact_mass");
  const [orderDir, setOrderDir] = React.useState<OrderDir>("desc");
  const [limit, setLimit] = React.useState<number>(50); // server-side page size
  const [offset, setOffset] = React.useState<number>(0); // server-side offset

  // Result state
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<QueryResult | null>(null);
  const [lastPayload, setLastPayload] = React.useState<string | null>(null);

  const canPrev = offset > 0;
  const canNext = !!result && result.rowCount === limit; // server returned a full page -> probably more

  const buildPayload = React.useCallback((): QueryPayload => {
    return {
      name: "compound_by_mass",
      params: { min_mass: Number(minMass), max_mass: Number(maxMass) },
      paging: { limit, offset },
      order: { column: orderCol, dir: orderDir },
    };
  }, [minMass, maxMass, limit, offset, orderCol, orderDir]);

  const fetchData = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    const payload = buildPayload();
    setLastPayload(JSON.stringify(payload, null, 2));
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      const data = text ? (JSON.parse(text) as QueryResult | { error?: string; detail?: string }) : null;

      if (!res.ok) {
        const msg =
          (data && typeof data === "object" && "error" in data && (data as any).error) ||
          `HTTP ${res.status}`;
        throw new Error(msg);
      }
      // Light sanity checks
      const ok =
        data &&
        typeof (data as any).name === "string" &&
        Array.isArray((data as any).columns) &&
        Array.isArray((data as any).rows);
      if (!ok) throw new Error("Invalid response from server");

      setResult(data as QueryResult);
    } catch (e: any) {
      setResult(null);
      setError(e?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }, [buildPayload]);

  // Handlers
  const onSearch = async () => {
    // reset pagination and fetch
    setOffset(0);
    // Wait a tick so offset state is applied before fetch
    setTimeout(fetchData, 0);
  };

  const onPrev = async () => {
    if (!canPrev) return;
    setOffset((prev) => Math.max(0, prev - limit));
    setTimeout(fetchData, 0);
  };

  const onNext = async () => {
    if (!canNext) return;
    setOffset((prev) => prev + limit);
    setTimeout(fetchData, 0);
  };

  // Basic client-side guard
  const massError =
    isNaN(minMass) || isNaN(maxMass) || minMass < 0 || maxMass < 0 || minMass > maxMass
      ? "Mass range invalid"
      : null;

  return (
    <React.Fragment>
      <CssBaseline enableColorScheme />
      <Box sx={{ p: 3, display: "flex", flexDirection: "column", gap: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          RetroMol — Query: <code>compound_by_mass</code>
        </Typography>

        {/* Controls */}
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} useFlexGap flexWrap="wrap">
            <TextField
              label="Min mass"
              type="number"
              value={minMass}
              onChange={(e) => setMinMass(Number(e.target.value))}
              size="small"
              sx={{ minWidth: 160 }}
            />
            <TextField
              label="Max mass"
              type="number"
              value={maxMass}
              onChange={(e) => setMaxMass(Number(e.target.value))}
              size="small"
              sx={{ minWidth: 160 }}
            />
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel id="order-col-label">Order column</InputLabel>
              <Select
                labelId="order-col-label"
                label="Order column"
                value={orderCol}
                onChange={(e) => setOrderCol(e.target.value as OrderCol)}
              >
                <MenuItem value="exact_mass">exact_mass</MenuItem>
                <MenuItem value="id">id</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel id="order-dir-label">Order dir</InputLabel>
              <Select
                labelId="order-dir-label"
                label="Order dir"
                value={orderDir}
                onChange={(e) => setOrderDir(e.target.value as OrderDir)}
              >
                <MenuItem value="desc">desc</MenuItem>
                <MenuItem value="asc">asc</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel id="limit-label">Limit</InputLabel>
              <Select
                labelId="limit-label"
                label="Limit"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              >
                {[25, 50, 100, 200, 500].map((n) => (
                  <MenuItem key={n} value={n}>
                    {n}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Offset"
              type="number"
              value={offset}
              onChange={(e) => setOffset(Math.max(0, Number(e.target.value)))}
              size="small"
              sx={{ minWidth: 140 }}
            />

            <Stack direction="row" spacing={1} alignItems="center">
              <Button
                variant="contained"
                onClick={onSearch}
                disabled={!!massError || loading}
              >
                Search
              </Button>
              <Button variant="outlined" onClick={onPrev} disabled={!canPrev || loading}>
                Prev
              </Button>
              <Button variant="outlined" onClick={onNext} disabled={!canNext || loading}>
                Next
              </Button>
              {loading && <CircularProgress size={22} sx={{ ml: 1 }} />}
            </Stack>
          </Stack>

          {massError && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {massError}
            </Alert>
          )}
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </Paper>

        {/* Results */}
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Results
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {result
                ? `rows: ${result.rowCount} | limit: ${result.limit} | offset: ${result.offset} | ${result.elapsed_ms} ms`
                : "No data"}
            </Typography>
          </Stack>

          {!result ? (
            <Typography variant="body2" color="text.secondary">
              Run a search to see results.
            </Typography>
          ) : result.rows.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No rows.
            </Typography>
          ) : (
            <TableContainer sx={{ maxHeight: 520 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    {result.columns.map((c) => (
                      <TableCell key={c} sx={{ whiteSpace: "nowrap", fontWeight: 600 }}>
                        {c}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.rows.map((row, idx) => (
                    <TableRow key={idx} hover>
                      {result.columns.map((c) => {
                        let v = row[c];
                        // Trim very long strings for readability
                        if (typeof v === "string" && v.length > 200) v = v.slice(0, 200) + "…";
                        return (
                          <TableCell key={c} sx={{ maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis" }}>
                            {v as any}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>

        {/* Last payload (debug) */}
        {lastPayload && (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
              Last request payload
            </Typography>
            <Box component="pre" sx={{ m: 0, whiteSpace: "pre-wrap", fontSize: 12 }}>
              {lastPayload}
            </Box>
          </Paper>
        )}
      </Box>
    </React.Fragment>
  );
}
