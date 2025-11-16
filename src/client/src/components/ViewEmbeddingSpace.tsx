import React from "react";
import Box from "@mui/material/Box";
import Alert from "@mui/material/Alert";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import CircularProgress from "@mui/material/CircularProgress";
import { ScatterChart } from "@mui/x-charts/ScatterChart";
import { useNotifications } from "../components/NotificationProvider";
import { Session } from "../features/session/types";
import { EmbeddingPoint } from "../features/views/types";
import { getEmbeddingSpace } from "../features/views/api";

interface ViewEmbeddingSpaceProps {
  session: Session;
  // Updated to functional form to avoid stale closures
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
  const idToName = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const item of session.items) {
      map.set(item.id, item.name);
    }
    return map;
  }, [session.items]);

  // Changes only when the contents of items changes, not just because of polling
  const itemsKey = React.useMemo(() => {
    if (!session.items || session.items.length === 0) return "";

    return session.items
      .map((item) => `${item.id}:${item.status}:${item.updatedAt}`)
      .join("|")
  }, [session.items]);

  // Fetch embedding space points when session changes
  React.useEffect(() => {
    // No items: nothing to embed
    if (!session.items || session.items.length === 0) {
      setPoints(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;

    setLoading(true);
    setError(null);

    getEmbeddingSpace(session)
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
  }, [itemsKey, pushNotification]); // only rerun when itemsKey changes (i.e., notable changes to session items)

  // No items at all
  if (!session.items || session.items.length === 0) {
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
      {error && !loading && (
        <Box sx={{ mb: 2 }}>
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
              series={[
                {
                  label: "Items",
                  data: points.map((p) => ({
                    x: p.x,
                    y: p.y,
                    id: p.id,
                    name: idToName.get(p.id) ?? p.id,
                  })),
                  valueFormatter: (_value, context) => {
                    const idx = context.dataIndex;
                    const point = points[idx];
                    return idToName.get(point.id) ?? point.id;
                  }
                }
              ]}
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
