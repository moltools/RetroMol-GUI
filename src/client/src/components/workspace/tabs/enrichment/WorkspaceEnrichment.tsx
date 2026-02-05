import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import MuiLink from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import InputLabel from "@mui/material/InputLabel";
import FormControl from "@mui/material/FormControl";
import MenuItem from "@mui/material/MenuItem";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import Checkbox from "@mui/material/Checkbox";
import FormGroup from "@mui/material/FormGroup";
import FormControlLabel from "@mui/material/FormControlLabel";
import TextField from "@mui/material/TextField";
import InputAdornment from "@mui/material/InputAdornment";
import Chip from "@mui/material/Chip";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import Tooltip from "@mui/material/Tooltip";
import DownloadIcon from "@mui/icons-material/Download";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { Session } from "../../../../features/session/types";
import { Select } from "@mui/material";
import { useNotifications } from "../../NotificationProvider";
import type { EnrichmentResponse, EnrichmentResult } from "./types";

type WorkspaceEnrichmentProps = {
  session: Session;
  setSession: React.Dispatch<React.SetStateAction<Session | null>>;
};

const DEFAULT_THRESHOLD_PCT = 80;
const SIGNIFICANCE_ALPHA = 0.05;

function formatPValue(value: number): string {
  if (!Number.isFinite(value)) return "n/a";
  if (value === 0) return "0";
  if (value < 0.0001) return value.toExponential(2);
  return value.toFixed(4);
}

function formatCount(count: number, total: number): string {
  if (total <= 0) return `${count} / ${total}`;
  const pct = (count / total) * 100;
  return `${count} / ${total} (${pct.toFixed(1)}%)`;
}

function labelText(result: EnrichmentResult): string {
  const { scheme, key, value } = result.label;
  return `${scheme}: ${key} = ${value}`;
}

function buildEnrichmentTsv(result: EnrichmentResponse): string {
  const summary = result.summary;
  const lines = [
    `# neighbors_requested\t${summary.neighbors_requested}`,
    `# total_neighbors\t${summary.total_neighbors}`,
    `# population_total\t${summary.population_total}`,
    `# in_group\t${summary.in_group}`,
    `# out_group\t${summary.out_group}`,
    `# threshold_pct\t${summary.threshold_pct}`,
    `# self_alignment_score\t${summary.self_alignment_score}`,
    `# alignment_threshold\t${summary.alignment_threshold}`,
    "",
    [
      "scheme",
      "key",
      "value",
      "p_value",
      "p_adjusted",
      "in_group_count",
      "background_count",
      "in_group_fraction",
      "background_fraction",
    ].join("\t"),
    ...result.results.map((row) =>
      [
        row.label.scheme,
        row.label.key,
        row.label.value,
        row.p_value,
        row.p_adjusted,
        row.in_group_count,
        row.background_count,
        row.in_group_fraction,
        row.background_fraction,
      ].join("\t")
    ),
  ];

  return lines.join("\n");
}

export const WorkspaceEnrichment: React.FC<WorkspaceEnrichmentProps> = ({ session }) => {
  const theme = useTheme();
  const { pushNotification } = useNotifications();

  const hasItems = session.items.length > 0;

  const [selectedItemId, setSelectedItemId] = React.useState<string>("");
  const [thresholdPct, setThresholdPct] = React.useState<number>(DEFAULT_THRESHOLD_PCT);
  const [queryLoading, setQueryLoading] = React.useState(false);
  const [queryError, setQueryError] = React.useState<string | null>(null);
  const [queryResult, setQueryResult] = React.useState<EnrichmentResponse | null>(null);

  const [queryAgainstCompounds, setQueryAgainstCompounds] = React.useState(true);
  const [queryAgainstClusters, setQueryAgainstClusters] = React.useState(true);

  const alert = React.useMemo(() => {
    if (queryError) {
      return { severity: "error" as const, text: queryError };
    }
    if (queryResult) {
      return { severity: "success" as const, text: "Enrichment complete! See results below." };
    }
    return {
      severity: "info" as const,
      text: "Select an item and run enrichment to see results here.",
    };
  }, [queryError, queryResult]);

  async function runEnrichment(itemId: string): Promise<EnrichmentResponse> {
    const threshold = Math.min(100, Math.max(0, thresholdPct));
    const params = new URLSearchParams({
      sessionId: session.sessionId,
      itemId,
      thresholdPct: String(threshold),
      queryAgainstCompounds: String(queryAgainstCompounds),
      queryAgainstClusters: String(queryAgainstClusters),
    });
    const res = await fetch(`/api/enrichment?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`Enrichment failed: ${res.status}`);
    }
    return await res.json();
  }

  const handleRunEnrichment = async () => {
    if (!selectedItemId) return;

    setQueryLoading(true);
    setQueryError(null);
    setQueryResult(null);

    try {
      const result = await runEnrichment(selectedItemId);
      setQueryResult(result);
      pushNotification("Enrichment completed successfully!", "success");
    } catch (error) {
      setQueryError("Failed to run enrichment. Please try again.");
      pushNotification("Failed to run enrichment.", "error");
    } finally {
      setQueryLoading(false);
    }
  };

  const handleDownloadTsv = React.useCallback(() => {
    if (!queryResult) return;
    const tsv = buildEnrichmentTsv(queryResult);
    const blob = new Blob([tsv], { type: "text/tab-separated-values;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "enrichment.tsv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [queryResult]);

  return (
    <Box
      sx={{
        width: "100%",
        mx: "auto",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      <Card
        variant="outlined"
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          flexGrow: 1,
        }}
      >
        <CardContent>
          <Typography component="h1" variant="subtitle1">
            Enrichment study
          </Typography>
          <Typography variant="body1">
            Use uploaded items from the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/upload"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Upload tab
            </MuiLink>
            &nbsp;to test whether annotation labels are overrepresented among the nearest neighbors.
          </Typography>

          <Stack direction="column" spacing={2} sx={{ mt: 3 }}>
            <FormControl fullWidth size="small" disabled={!hasItems || queryLoading}>
              <InputLabel
                id="enrichment-item-select-label"
                sx={{
                  backgroundColor: "background.paper",
                  px: 0.5,
                  transform: "translate(14px, 12px) scale(1)",
                  "&.MuiInputLabel-shrink": { transform: "translate(14px, -9px) scale(0.75)" },
                }}
              >
                {!hasItems
                  ? "No items available to select"
                  : selectedItemId
                    ? "Item to use for enrichment"
                    : "Select an item to use for enrichment"}
              </InputLabel>
              <Select
                labelId="enrichment-item-select-label"
                label="Item to use for enrichment"
                value={selectedItemId}
                onChange={(e) => setSelectedItemId(e.target.value)}
                disabled={!hasItems || queryLoading}
                MenuProps={{
                  PaperProps: {
                    sx: {
                      "& .MuiMenuItem-root": {
                        userSelect: "none",
                        borderRadius: 0,
                      },
                    },
                  },
                }}
                sx={{
                  "& .MuiSelect-select": { userSelect: "none" },
                  "& .MuiSelect-select:focus": { backgroundColor: "transparent" },
                  "& .MuiSelect-select:focus-visible": { outline: "none" },
                  "&.MuiInputBase-root": { height: 44 },
                }}
              >
                {session.items.map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              label="Alignment threshold"
              type="number"
              size="small"
              value={thresholdPct}
              onChange={(e) => {
                const next = Number(e.target.value);
                if (!Number.isNaN(next)) {
                  const clamped = Math.min(100, Math.max(0, next));
                  setThresholdPct(clamped);
                }
              }}
              disabled={queryLoading}
              inputProps={{ min: 0, max: 100, step: 1 }}
              helperText="Percentage of the query self-alignment score used as cutoff."
              InputProps={{
                endAdornment: <InputAdornment position="end">%</InputAdornment>,
              }}
            />

            <Box sx={{ display: "flex", justifyContent: "center" }}>
              <FormGroup row>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={queryAgainstClusters}
                      disabled={queryLoading || (queryAgainstClusters && !queryAgainstCompounds)}
                      onChange={(e) => setQueryAgainstClusters(e.target.checked)}
                    />
                  }
                  label="Query against clusters"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={queryAgainstCompounds}
                      disabled={queryLoading || (queryAgainstCompounds && !queryAgainstClusters)}
                      onChange={(e) => setQueryAgainstCompounds(e.target.checked)}
                    />
                  }
                  label="Query against compounds"
                />
              </FormGroup>
            </Box>

            <Stack direction="row" spacing={1} alignItems="center">
              <Button
                variant="contained"
                onClick={handleRunEnrichment}
                disabled={queryLoading || !selectedItemId}
              >
                {queryLoading ? "Running enrichment..." : "Run enrichment"}
              </Button>
              {queryLoading && <CircularProgress size={24} />}
            </Stack>

            <Alert severity={alert.severity}>{alert.text}</Alert>
          </Stack>
        </CardContent>
      </Card>

      {queryResult && (
        <Card
          variant="outlined"
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            flexGrow: 1,
          }}
        >
          <CardContent>
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 2,
                flexWrap: "wrap",
              }}
            >
              <Typography component="h2" variant="subtitle1">
                Enrichment results
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<DownloadIcon />}
                onClick={handleDownloadTsv}
                disabled={!queryResult?.results.length}
              >
                Download TSV
              </Button>
            </Box>

            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", mb: 1 }}>
              <Chip label={`Neighbors: ${queryResult.summary.total_neighbors}`} />
              <Chip label={`Population: ${queryResult.summary.population_total}`} />
              <Chip label={`In-group: ${queryResult.summary.in_group}`} />
              <Chip label={`Out-group: ${queryResult.summary.out_group}`} />
              <Chip label={`Threshold: ${queryResult.summary.threshold_pct}%`} />
            </Stack>

            <Typography variant="body2" sx={{ mb: 2 }}>
              Self-alignment score: {queryResult.summary.self_alignment_score.toFixed(2)}. Cutoff:{" "}
              {queryResult.summary.alignment_threshold.toFixed(2)}. Background counts use all
              database items for the selected types.
            </Typography>

            {queryResult.warnings.map((warning) => (
              <Alert key={warning} severity="warning" sx={{ mb: 1 }}>
                {warning}
              </Alert>
            ))}

            {queryResult.results.length === 0 ? (
              <Typography variant="body2">
                No enriched labels detected for this threshold.
              </Typography>
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell />
                      <TableCell>Label</TableCell>
                      <TableCell align="right">In-group</TableCell>
                      <TableCell align="right">Background</TableCell>
                      <TableCell align="right">P-value</TableCell>
                      <TableCell align="right">Adj. P</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {queryResult.results.map((result) => {
                      const label = labelText(result);
                      const isSignificant = result.p_adjusted <= SIGNIFICANCE_ALPHA;
                      return (
                        <TableRow key={label}>
                          <TableCell sx={{ width: 40 }}>
                            <Tooltip
                              title={
                                isSignificant
                                  ? "Significant (q ≤ 0.05)"
                                  : "Not significant (q > 0.05)"
                              }
                              arrow
                            >
                              <Box
                                component="span"
                                sx={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  color: isSignificant ? "success.main" : "error.main",
                                }}
                              >
                                {isSignificant ? (
                                  <CheckCircleOutlineIcon fontSize="small" />
                                ) : (
                                  <ErrorOutlineIcon fontSize="small" />
                                )}
                              </Box>
                            </Tooltip>
                          </TableCell>
                          <TableCell>
                            <Tooltip title={label} arrow>
                              <Typography variant="body2" noWrap sx={{ maxWidth: 360 }}>
                                {label}
                              </Typography>
                            </Tooltip>
                          </TableCell>
                          <TableCell align="right">
                            {formatCount(result.in_group_count, queryResult.summary.in_group)}
                          </TableCell>
                          <TableCell align="right">
                            {formatCount(result.background_count, queryResult.summary.population_total)}
                          </TableCell>
                          <TableCell align="right">{formatPValue(result.p_value)}</TableCell>
                          <TableCell align="right">{formatPValue(result.p_adjusted)}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};
