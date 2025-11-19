import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import MuiLink from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Stack from "@mui/material/Stack";
import CircularProgress from "@mui/material/CircularProgress";
import Alert from "@mui/material/Alert";
import { DataGrid, GridColDef, GridPaginationModel } from "@mui/x-data-grid";
import NotificationsRoundedIcon from "@mui/icons-material/NotificationsRounded";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { useNotifications } from "../components/NotificationProvider";
import { Session, SessionItem } from "../features/session/types";
import { runQuery } from "../features/query/api";
import type { QueryResult } from "../features/query/types";
import { ItemKindChip } from "./ItemKindChip";

interface WorkspaceQueryProps {
  session: Session;
  setSession: (updated: (prev: Session) => Session) => void;
}

const formatSource = (value: string | null | undefined) => {
  if (!value) return "Unknown";
  if (value.toLowerCase() === "mibig") return "MIBiG";
  if (value.toLowerCase() === "npatlas") return "NPAtlas";
  return value;
}

const buildExtIdUrl = (source: string | undefined, extId: string) => {
  if (source?.toLowerCase() === "mibig") return `https://mibig.secondarymetabolites.org/repository/${extId}/index.html#r1c1`;
  if (source?.toLowerCase() === "npatlas") return `https://www.npatlas.org/explore/compounds/${extId}`;
  return null;
}

const columnNameMap: Record<string, string> = {
  identifier: "Readout ID",
  type: "Type",
  source: "Source",
  ext_id: "External ID",
  name: "Name",
  score: "Similarity (%)",
};

export const WorkspaceQuery: React.FC<WorkspaceQueryProps> = ({ session, setSession }) => {
  const theme = useTheme();
  const { pushNotification } = useNotifications();
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<QueryResult | null>(null);

  const [rowCount, setRowCount] = React.useState(0);
  const [paginationModel, setPaginationModel] = React.useState<GridPaginationModel>({
    pageSize: 10,
    page: 0,
  })

  // Items that have at least one fingerprint/readout
  const itemsWithFingerprints = React.useMemo(() => {
    return (session.items || []).filter((item) => item.fingerprints && item.fingerprints.length > 0);
  }, [session.items]);

  // Flatten fingerprints for selection list
  const fingerprintOptions = React.useMemo(() => {
    const options: { itemId: string; fpId: string; label: string }[] = [];
    for (const item of itemsWithFingerprints) {
      item.fingerprints!.forEach((fp, idx) => {
        options.push({
          itemId: item.id,
          fpId: fp.id,
          label: `${item.name} (readout ${idx + 1})`,
        });
      });
    }
    return options;
  }, [itemsWithFingerprints]);

  const [selectedItemId, setSelectedItemId] = React.useState<string>(() => fingerprintOptions[0]?.itemId || "");
  const [selectedFingerprintId, setSelectedFingerprintId] = React.useState<string>(() => fingerprintOptions[0]?.fpId || "");

  // Keep selection in sync when options change
  React.useEffect(() => {
    if (!fingerprintOptions.length) {
      setSelectedItemId("");
      setSelectedFingerprintId("");
      return;
    }
    if (!fingerprintOptions.find((opt) => opt.fpId === selectedFingerprintId)) {
      setSelectedItemId(fingerprintOptions[0].itemId);
      setSelectedFingerprintId(fingerprintOptions[0].fpId);
    }
  }, [fingerprintOptions, selectedFingerprintId]);

  const handleItemChange = (value: string) => {
    setSelectedItemId(value);
    const firstFp = fingerprintOptions.find((opt) => opt.itemId === value);
    setSelectedFingerprintId(firstFp?.fpId || "");
  };

  const handleFingerprintChange = (value: string) => {
    const match = fingerprintOptions.find((opt) => opt.fpId === value);
    if (match) {
      setSelectedItemId(match.itemId);
      setSelectedFingerprintId(match.fpId);
    }
  };

  // Core fetch function that wires page + pageSize -> limit + offset
  const fetchResults = React.useCallback(
    async (model: GridPaginationModel) => {
      if (!selectedItemId || !selectedFingerprintId) {
        pushNotification("Select an item and readout to query.", "warning");
        return;
      }

      // Get the selected fingerprint data
      const selectedItem = session.items?.find((item) => item.id === selectedItemId);
      const selectedFingerprint = selectedItem?.fingerprints?.find((fp) => fp.id === selectedFingerprintId);
      if (!selectedFingerprint || !selectedFingerprint) {
        pushNotification("Selected readout data not found.", "error");
        return;
      }

      setLoading(true);
      setError(null);
      
      try {
        const limit = model.pageSize;
        const offset = model.page * model.pageSize;

        const data = await runQuery({
          name: "cross_modal_retrieval",
          params: {
            fingerprint512: selectedFingerprint.fingerprint512,
          },
          paging: { limit, offset },
          order: { column: "score", dir: "desc" },
        });

        setResult(data);
        
        const total =
          (data as any).totalCount ??
          offset + data.rows.length + (data.rows.length === limit ? 1 : 0);

        setRowCount(total);
      } catch (err: any) {
        setError(err.message || "Failed to run query.");
        pushNotification(`Query failed: ${err.message}`, "error");
      } finally {
        setLoading(false);
      }
    },
    [selectedItemId, selectedFingerprintId]
  )

  // USer clicks "Run query" -> reset to first page and fetch
  const handleRunQuery = async () => {
    const firstPageModel: GridPaginationModel = {
      page: 0,
      pageSize: paginationModel.pageSize,
    };
    setPaginationModel(firstPageModel);
    fetchResults(firstPageModel);
  };

  // DataGrid pagination event -> fetch that page from backend
  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
    fetchResults(newModel);
  }

  const columns: GridColDef[] = React.useMemo(() => {
    if (!result) return [];

    return result.columns.map((col) => {
      const base: GridColDef = {
        field: col,
        headerName: columnNameMap[col] || col,
        flex: 1,
        sortable: true,
        resizable: true,
      }

      // For "type" column, render ItemKindChip
      if (col === "type") {
        base.renderCell = (params) => {
          const itemKind = params.value as string | undefined;
          if (!itemKind) return null;
          return <ItemKindChip itemKind={itemKind} />;
        }
      }

      // Format source values
      if (col === "source") {
        base.valueGetter = (value) => {
          return formatSource(value as string | undefined);
        }
      }

      // Render ext_id as clickable outlink
      if (col === "ext_id") {
        base.renderCell = (params) => {
          const extId = params.value as string | undefined;
          if (!extId) return null;

          const source = params.row.source as string | undefined;
          const url = buildExtIdUrl(source, extId);

          return (
            <MuiLink
              href={url || "#"}
              target={url ? "_blank" : undefined}
              rel="noopener noreferrer"
              underline="hover"
            >
              {extId}
            </MuiLink>
          )
        }
      }

      return base;
    })
  }, [result]);

  const rows = React.useMemo(() => {
    if (!result) return [];
    return result.rows.map((row, idx) => ({
      id: idx,
      ...row,
    }));
  }, [result]);

  return (
    <Box 
      sx={{ 
        width: "100%", 
        mx: "auto", 
        display: "flex", 
        flexDirection: "column", 
        gap: "16px" 
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
            Getting started
          </Typography>
          <Typography variant="body1">
            Pick one of your imported items from the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/upload"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Upload tab
            </MuiLink>
            &nbsp;and query it against the BioNexus database for compounds and BGCs (biosynthetic gene clusters). The results
            data frame shows nearest neighbors based on fingerprint similarity. The enrichment results show overrepresented
            annotations among the hits compared to the background database.
            You can
            insert query hits into your workspace for further analysis in the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/explore"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Explore tab
            </MuiLink>. Keep an eye on <NotificationsRoundedIcon fontSize={"small"} sx={{ verticalAlign: "middle" }} />
            for updates on your queries.
          </Typography>

          <Stack direction="column" spacing={2} sx={{ mt: 3 }}>
            <FormControl fullWidth size="small">
              <InputLabel
                id="item-select-label"
                sx={{
                  backgroundColor: "background.paper",
                  px: 0.5,
                }}
              >
                Item
              </InputLabel>
              <Select
                labelId="item-select-label"
                label="Item"
                value={selectedItemId}
                onChange={(e) => handleItemChange(e.target.value)}
                disabled={!fingerprintOptions.length}
              >
                {Array.from(
                  new Map<string, SessionItem>(itemsWithFingerprints.map((item) => [item.id, item])).values()
                ).map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth size="small">
              <InputLabel
                id="fingerprint-select-label"
                sx={{
                  backgroundColor: "background.paper",
                  px: 0.5,
                }}
              >
                Readout
              </InputLabel>
              <Select
                labelId="fingerprint-select-label"
                label="Readout"
                value={selectedFingerprintId}
                onChange={(e) => handleFingerprintChange(e.target.value)}
                disabled={!fingerprintOptions.length}
              >
                {fingerprintOptions
                  .filter((opt) => opt.itemId === selectedItemId)
                  .map((opt) => (
                    <MenuItem key={opt.fpId} value={opt.fpId}>
                      {opt.label}
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>

            <Stack direction="row" spacing={1} alignItems="center">
              <Button variant="contained" onClick={handleRunQuery} disabled={!fingerprintOptions.length || loading}>
                Run query
              </Button>
              {loading && <CircularProgress size={20} />}
            </Stack>

            {!fingerprintOptions.length && (
              <Alert severity="info">
                No items with readouts found. Import items in Upload, wait for readouts, then try again.
              </Alert>
            )}

            {error && <Alert severity="error">{error}</Alert>}
          </Stack>

        </CardContent>
      </Card>
      <Grid container spacing={2} columns={12} alignItems="stretch" sx={{ mb: (theme) => theme.spacing(2) }}>
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: "flex" }}>
          <Card variant="outlined" sx={{ display: "flex", "flexDirection": "column", flex: 1 }}>
            <CardContent sx={{ display: "flex", flexDirection: "column" }}>
              <Typography component="h1" variant="subtitle1">
                Query results
              </Typography>
              {rows.length === 0 && !loading ? (
                <Typography variant="body2">
                  {result ? "No results returned." : "Run a query to see results."}
                </Typography>
              ) : (
                <DataGrid
                  loading={loading}
                  rows={rows}
                  columns={columns}
                  paginationMode="server"
                  paginationModel={paginationModel}
                  onPaginationModelChange={handlePaginationModelChange}
                  rowCount={rowCount}
                  pageSizeOptions={[10, 25, 50]}
                  disableRowSelectionOnClick
                  getRowId={(row) => row.id}
                  density="compact"
                  localeText={{
                    noRowsLabel: result ? "No rows returned." : "Run a query to see results.",
                  }}
                  sx={{
                    // Make all icon buttons inside the grid "flat"
                    "& .MuiIconButton-root": {
                      backgroundColor: "transparent !important",
                      border: "none !important",
                      boxShadow: "none",
                    },
                    "& .MuiIconButton-root:hover": {
                      backgroundColor: "transparent !important",
                    },
                    // optional: also nuke any outlined/button-style things in the footer/toolbar
                    "& .MuiButtonBase-root": {
                      boxShadow: "none",
                    },
                  }}
                />
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: "flex" }}>
          <Card variant="outlined" sx={{ display: "flex", "flexDirection": "column", flex: 1 }}>
            <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1 }}>
              <Typography component="h1" variant="subtitle1">
                Enrichment results
              </Typography>
              <Typography variant="body2">
                Enrichtment results view is currently unavailable.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
