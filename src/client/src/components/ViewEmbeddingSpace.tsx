import React from "react";
import Box from "@mui/material/Box";
import Alert from "@mui/material/Alert";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import CircularProgress from "@mui/material/CircularProgress";
import { ScatterChart } from "@mui/x-charts/ScatterChart";
import { useNotifications } from "../components/NotificationProvider";
import { Session, SessionItem } from "../features/session/types";
import { EmbeddingPoint } from "../features/views/types";
import { getEmbeddingSpace } from "../features/views/api";

const labelMap: Record<string, string> = {
  "compound": "Compound",
  "gene_cluster": "Biosynthetic gene cluster",
}

interface ViewEmbeddingSpaceProps {
  session: Session;
  setSession: (updated: (prev: Session) => Session) => void;
}

export const ViewEmbeddingSpace: React.FC<ViewEmbeddingSpaceProps> = ({
  session,
  setSession,
}) => {
  const { pushNotification } = useNotifications();

  const [points, setPoints] = React.useState<EmbeddingPoint[] | null>(null);
  const [loading, setLoading] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string | null>(null);

  // Map item ID -> name for tooltips/labels
  const parentById = React.useMemo(() => {
    const map = new Map<string, SessionItem>();
    for (const item of session.items) {
      map.set(item.id, item);
    }
    return map;
  }, [session.items]);

  // Map child ID -> score for tooltips
  const scoreByChildId = React.useMemo(() => {
    const map = new Map<string, number>();
    for (const item of session.items) {
      for (const fp of item.fingerprints || []) {
        map.set(fp.id, fp.score);
      }
    }
    return map;
  }, [session.items]);

  // Construct scatter series from points
  const scatterSeries = React.useMemo(() => {
    if (!points) return [];

    // kind -> array of points for that kin
    const byKind = new Map<string, { label: string; data: { x: number; y: number; id: string; name: string }[] }>();

    for (const p of points) {
      const parent = parentById.get(p.parent_id) ?? null;
      const parentName = parent ? parent.name : "unknown";
      const childIds = parent?.fingerprints.map((fp) => fp.id) || [];
      const childIdx = childIds.indexOf(p.child_id);
      const key = p.kind || "unknown";

      // Initialize kind entry if not present
      if (!byKind.has(key)) {
        byKind.set(key, { label: key, data: [] });
      }

      // Add point to appropriate kind series
      byKind.get(key)!.data.push({
        x: p.x,
        y: p.y,
        id: p.child_id,
        name: `Readout ${childIdx >= 0 ? `${childIdx + 1}` : ""} ${parentName} `,
      });
    }

    return Array.from(byKind.values());
  }, [points, parentById]);

  // Changes only when the contents of items changes, not just because of polling
  const itemsKey = React.useMemo(() => {
    if (!session.items || session.items.length === 0) return "";

    return session.items
      .map((item) => `${item.id}:${item.status}:${item.updatedAt}`)
      .join("|")
  }, [session.items]);

  // Filtered items with fingerprints
  const itemsWithFingerprints = React.useMemo(() => {
    return session.items?.filter((item) => item.fingerprints && item.fingerprints.length > 0) || [];
  }, [session.items]);

  // Fetch embedding space points when session changes
  React.useEffect(() => {
    // If less than 2 items, no embedding space
    if (!itemsWithFingerprints || itemsWithFingerprints.length < 2) {
      setPoints(null);
      setLoading(false);
      setError(`At least two readouts are required to view the embedding space.`);
      return;
    }

    let cancelled = false;

    setLoading(true);

    getEmbeddingSpace(session.sessionId, itemsWithFingerprints)
      .then((pts) => {
        if (cancelled) return;
        setPoints(pts);
      })
      .catch((err) => {
        if (cancelled) return;
        pushNotification(`Failed to load embedding space: ${err.message}`, "error");
        setError(err.message);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    
    return () => {
      cancelled = true;
    }
  }, [itemsWithFingerprints, pushNotification]); // only rerun when itemsKey changes (i.e., notable changes to session items)

  // No items at all
  if (!itemsWithFingerprints || itemsWithFingerprints.length === 0) {
    return (
      <Box>
        <Typography variant="body2">
          No items in this session yet. Add compounds or gene clusters to see the embedding space.
        </Typography>
      </Box>
    )
  }

  return (
    <Box>
      {/* Loading spinner on mount/fetch */}
      {loading && (
        <Box
          sx={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            py: 4,
          }}
        >
          <CircularProgress />
        </Box>
      )}

      {/* Error message if fetch failed */}
      {error && (
        <Box>
          <Alert severity="error">
            {error}
          </Alert>
        </Box>
      )}

      {/* Embedding space visualization */}
      {!loading && !error && points && points.length > 0 && (
        <Paper
          elevation={2}
          sx={{
            p: 2,
            height: 420,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Box sx={{ flex: 1, minHeight: 0 }}>
            <ScatterChart
              height={360}
              series={scatterSeries.map((group) => ({
                label: labelMap[group.label] || group.label,
                data: group.data,
                valueFormatter: (_value, context) => {
                  const idx = context.dataIndex;
                  const point = group.data[idx];
                  const score = scoreByChildId.get(point.id);
                  return score != null
                    ? `${point.name} (score ${(score * 100).toFixed(1)}%)`
                    : point.name;
                }
              }))}
              xAxis={[{ disableLine: true, disableTicks: true }]}
              yAxis={[{ disableLine: true, disableTicks: true }]}
              grid={{ horizontal: false, vertical: false }}
              sx={{
                // Hide any remaining tick labels just in case
                "& .MuiChartsAxis-tickLabel": {
                  display: "none",
                },
              }}
            />
          </Box>
        </Paper>
      )}

      {/* If backend returns no points */}
      {!loading && !error && (!points || points.length === 0) && (
        <Typography variant="body2">
          No embedding points returned from backend.
        </Typography>
      )}
    </Box>
  )
}
