import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import MuiLink from "@mui/material/Link";
import Tooltip from "@mui/material/Tooltip";
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
import UploadFileIcon from "@mui/icons-material/UploadFile";
import SettingsIcon from "@mui/icons-material/Settings";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { useNotifications } from "../components/NotificationProvider";
import { Session, SessionItem } from "../features/session/types";
import { runQuery } from "../features/query/api";
import type { QueryResult } from "../features/query/types";
import { runEnrichment } from "../features/views/api";
import type { EnrichmentResult } from "../features/views/types";
import { ItemKindChip } from "./ItemKindChip";
import { importCompoundById } from "../features/jobs/api";
import type { QuerySettings } from "../features/views/types";
import { DialogQuerySettings } from "./DialogQuerySettings";

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
  score: "Similarity",
};

export const WorkspaceQuery: React.FC<WorkspaceQueryProps> = ({ session, setSession }) => {
  const theme = useTheme();
  const { pushNotification } = useNotifications();

  const [settingsDialogOpen, setSettingsDialogOpen] = React.useState(false);
  const [querySettings, setQuerySettings] = React.useState<QuerySettings>({
    scoreThreshold: 0.7,
  });

  const [queryLoading, setQueryLoading] = React.useState(false);
  const [queryError, setQueryError] = React.useState<string | null>(null);
  const [queryResult, setQueryResult] = React.useState<QueryResult | null>(null);
  
  const [enrichmentLoading, setEnrichmentLoading] = React.useState(false);
  const [enrichmentError, setEnrichmentError] = React.useState<string | null>(null);
  const [enrichmentResult, setEnrichmentResult] = React.useState<EnrichmentResult | null>(null);

  const [rowCount, setRowCount] = React.useState(0);
  const [paginationModel, setPaginationModel] = React.useState<GridPaginationModel>({
    pageSize: 10,
    page: 0,
  })

  const [importCooldown, setImportCooldown] = React.useState(false);
  const IMPORT_COOLDOWN_MS = 3000;

  // Helper to build deps for import service
  const deps = React.useMemo(
    () => ({
      setSession,
      pushNotification,
      sessionId: session.sessionId,
    }),
    [setSession, session.sessionId]
  )

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

  // Second fetch for enrichment analysis for results
  const fetchEnrichmentForResults = React.useCallback(
    async (result: QueryResult) => {
      if (!result.rows || result.rows.length === 0) return;

      try {
        setEnrichmentLoading(true);
        setEnrichmentError(null);

        // Get selected fingerprint data
        const selectedItem = session.items?.find((item) => item.id === selectedItemId);
        const selectedFingerprint = selectedItem?.fingerprints?.find((fp) => fp.id === selectedFingerprintId);
        if (!selectedFingerprint || !selectedFingerprint) {
          setEnrichmentError("Selected readout data not found.");
          return;
        }

        const fingerprint512 = selectedFingerprint.fingerprint512;
        
        const data = await runEnrichment({ fingerprint512, querySettings });
        setEnrichmentResult(data);
      } catch (err: any) {
        setEnrichmentError(err.message || "Failed to run enrichment analysis");
        pushNotification(`Enrichment analysis failed: ${err.message}`, "error");
      } finally {
        setEnrichmentLoading(false);
      }
    },
    [session.sessionId, querySettings]
  )

  // Core fetch function that wires page + pageSize -> limit + offset
  const fetchQueryResults = React.useCallback(
    async (model: GridPaginationModel): Promise<QueryResult | null> => {
      if (!selectedItemId || !selectedFingerprintId) {
        pushNotification("Select an item and readout to query.", "warning");
        return null;
      }

      // Get the selected fingerprint data
      const selectedItem = session.items?.find((item) => item.id === selectedItemId);
      const selectedFingerprint = selectedItem?.fingerprints?.find((fp) => fp.id === selectedFingerprintId);
      if (!selectedFingerprint || !selectedFingerprint) {
        pushNotification("Selected readout data not found.", "error");
        return null;
      }

      setQueryLoading(true);
      setQueryError(null);
      
      try {
        const limit = model.pageSize;
        const offset = model.page * model.pageSize;

        const data = await runQuery({
          name: "cross_modal_retrieval",
          params: {
            fingerprint512: selectedFingerprint.fingerprint512,
            querySettings,
          },
          paging: { limit, offset },
          order: { column: "score", dir: "desc" },
        });

        setQueryResult(data);
        
        const total =
          (data as any).totalCount ??
          offset + data.rows.length + (data.rows.length === limit ? 1 : 0);

        setRowCount(total);

        return data;
      } catch (err: any) {
        setQueryError(err.message || "Failed to run query.");
        pushNotification(`Query failed: ${err.message}`, "error");
        return null;
      } finally {
        setQueryLoading(false);
      }
    },
    [selectedItemId, selectedFingerprintId, querySettings]
  )

  // USer clicks "Run query" -> reset to first page and fetch
  const handleRunQuery = async () => {
    const firstPageModel: GridPaginationModel = {
      page: 0,
      pageSize: paginationModel.pageSize,
    };
    setPaginationModel(firstPageModel);
    
    const data = await fetchQueryResults(firstPageModel);

    // Only run enrichment when button is clicked
    if (data && data.rows && data.rows.length > 0) {
      void fetchEnrichmentForResults(data);
    } else {
      setEnrichmentResult(null);
    }
  };

  // DataGrid pagination event -> fetch that page from backend
  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
    void fetchQueryResults(newModel);
  }

  // Row action handler
  const handleRowAction = React.useCallback(
    (row: any) => {
      if (importCooldown) {
        pushNotification("Please wait a moment before importing another item.", "info");
        return;
      }
      
      // Start global cooldown
      setImportCooldown(true);
      setTimeout(() => setImportCooldown(false), IMPORT_COOLDOWN_MS);

      // Extract necessary info from the row
      const type = row.type as string | undefined;
      const identifier = row.identifier as number | undefined;

      // Only allow type "compound" for now
      if (type !== "compound") {
        pushNotification(`Import for item type "${type}" is not supported yet.`, "warning");
        return;
      }

      // Check if both are present
      if (!type || !identifier) {
        pushNotification("Cannot import item: missing type or identifier.", "error");
        return;
      }

      // Use importCompoundById to import the compound
      importCompoundById(deps, identifier).then((item) => {
        if (item) {
          pushNotification(`Imported item "${item.name}" into your workspace`, "success");
        } else {
          pushNotification("Failed to import item", "error");
        }
      }).catch((err) => {
        const msg = err instanceof Error ? err.message : String(err);
        pushNotification(`Import failed: ${msg}`, "error");
      });
    },
    [importCooldown, deps]
  )

  // Define columns based on result columns
  const columns: GridColDef[] = React.useMemo(() => {
    if (!queryResult) return [];

    // return result.columns.map((col) => {
    const baseColumns: GridColDef[] = queryResult.columns.map((col) => {
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

      // Format score as percentage with 2 decimals
      if (col === "score") {
        base.valueFormatter = (v: number) => {
          return (v * 100).toFixed(2) + "%";
        }
      }

      return base;
    })

    // Add extra column with Import action button
    const actionColumn: GridColDef = {
      field: "actions",
      headerName: "",
      sortable: false,
      filterable: false,
      resizable: false,
      disableColumnMenu: true,
      align: "center",
      headerAlign: "center",
      width: 50,
      renderCell: (params) => {
        const isDisabled = importCooldown || params.row.type !== "compound";    

        // Only show import button for compounds for now
        return (
          params.row.type === "compound" ? (
            <Box sx={{ pt: 0.5 }}>
              <Tooltip
                title={
                  importCooldown
                    ? "Please wait before importing another item"
                    : "Import this item into your workspace"
                }
                arrow
              >
                <UploadFileIcon
                  fontSize="small"
                  sx={{ cursor: isDisabled ? "not-allowed" : "pointer" }}
                  onClick={() => { if (!isDisabled) handleRowAction(params.row) }}
                />
              </Tooltip>
            </Box>
          ) : null
        )
      },
    }

    return [...baseColumns, actionColumn];
  }, [queryResult, handleRowAction, importCooldown]);

  // Map result rows to DataGrid rows with unique IDs
  const rows = React.useMemo(() => {
    if (!queryResult) return [];
    return queryResult.rows.map((row, idx) => ({
      id: idx,
      ...row,
    }));
  }, [queryResult]);

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
              <Button variant="contained" onClick={handleRunQuery} disabled={!fingerprintOptions.length || queryLoading}>
                Run query
              </Button>
              <Tooltip title="Adjust query settings" arrow>
                <SettingsIcon
                  fontSize="small"
                  onClick={() => setSettingsDialogOpen(true)}
                  sx={{
                    cursor: "pointer",
                    color: "text.primary",
                    transform: settingsDialogOpen ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform 0.4s ease",
                  }}
                />
              </Tooltip>
              {queryLoading && <CircularProgress size={20} />}
            </Stack>

            {!fingerprintOptions.length && (
              <Alert severity="info">
                No items with readouts found. Import items in Upload, wait for readouts, then try again.
              </Alert>
            )}

            {queryError && <Alert severity="error">{queryError}</Alert>}
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
              {rows.length === 0 && !queryLoading ? (
                <Typography variant="body2">
                  {queryResult ? "No results returned." : "Run a query to see results."}
                </Typography>
              ) : (
                <DataGrid
                  loading={queryLoading}
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
                    noRowsLabel: queryResult ? "No rows returned." : "Run a query to see results.",
                  }}
                  sx={{
                    borderRadius: 0,
                    "& .MuiIconButton-root": {
                      backgroundColor: "transparent !important",
                      border: "none !important",
                      boxShadow: "none",
                    },
                    "& .MuiIconButton-root:hover": {
                      backgroundColor: "transparent !important",
                    },
                    "& .MuiButtonBase-root": {
                      boxShadow: "none",
                    },
                  }}
                  slotProps={{
                    basePagination: {
                      material: { labelDisplayedRows: ({ from, to, count }) => `${from}-${to}` }
                    },
                    filterPanel: {
                      sx: {
                        "& .MuiInputLabel-root": {
                          backgroundColor: "background.paper",
                          paddingLeft: 0.5,
                          paddingRight: 0.5,
                        },
                      },
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
              {enrichmentLoading ? (
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <CircularProgress size={20} />
                  <Typography variant="body2">Running enrichment analysis...</Typography>
                </Box>
              ) : enrichmentError ? (
                <Alert severity="error">{enrichmentError}</Alert>
              ) : enrichmentResult ? (
                enrichmentResult.items.length > 0 ? (
                  <DataGrid
                    loading={enrichmentLoading}
                    pageSizeOptions={[10, 25, 50]}
                    density="compact"
                    rows={enrichmentResult.items.map((item, idx) => ({
                      id: item.id,
                      significant: item.p_value < 0.05,
                      schema: item.schema,
                      key: item.key,
                      value: item.value,
                      p_value: item.p_value,
                      adjusted_p_value: item.adjusted_p_value,
                    }))}
                    columns={[
                      { field: "significant", headerName: "Significant", flex: 1, sortable: true, resizable: true,
                        valueFormatter: (v: boolean) => v ? "Yes" : "No",
                      },
                      { field: "schema", headerName: "Schema", flex: 1, sortable: true, resizable: true,
                        valueFormatter: (v: string) => v.toUpperCase(),
                      },
                      { field: "key", headerName: "Key", flex: 1, sortable: true, resizable: true,
                        valueFormatter: (v: string) => v.toUpperCase(),
                      },
                      { field: "value", headerName: "Value", flex: 1, sortable: true, resizable: true,
                        valueFormatter: (v: string) => v.toUpperCase(),
                      },
                      { field: "p_value", headerName: "P-value", flex: 1, sortable: true, resizable: true,
                        valueFormatter: (v: number) => v.toExponential(3),
                      },
                      { field: "adjusted_p_value", headerName: "Adjusted P-value", flex: 1, sortable: true, resizable: true,
                        valueFormatter: (v: number) => v.toExponential(3),
                      },
                    ]}
                    sx={{
                      borderRadius: 0,
                      "& .MuiIconButton-root": {
                        backgroundColor: "transparent !important",
                        border: "none !important",
                        boxShadow: "none",
                      },
                      "& .MuiIconButton-root:hover": {
                        backgroundColor: "transparent !important",
                      },
                      "& .MuiButtonBase-root": {
                        boxShadow: "none",
                      },
                    }}
                    slotProps={{
                      filterPanel: {
                        sx: {
                          "& .MuiInputLabel-root": {
                            backgroundColor: "background.paper",
                            paddingLeft: 0.5,
                            paddingRight: 0.5,
                          },
                        },
                      },
                    }}
                    localeText={{
                      noRowsLabel: "No enrichment results found.",
                    }}
                  />
                ) : (
                  <Typography variant="body2">
                    No significant enrichment found among the query results.
                  </Typography>
                )
              ) : (
                <Typography variant="body2">
                  Enrichment results will appear here after running a query.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <DialogQuerySettings
          open={settingsDialogOpen}
          onClose={() => setSettingsDialogOpen(false)}
          settings={querySettings}
          handleSettingsChange={setQuerySettings}
        />
      </Grid>
    </Box>
  )
}
