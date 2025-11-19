import React from "react";
import Box from "@mui/material/Box";
import Alert from "@mui/material/Alert";
import Typography from "@mui/material/Typography";
import CircularProgress from "@mui/material/CircularProgress";
import { ScatterChart } from "@mui/x-charts/ScatterChart";
import { useNotifications } from "../components/NotificationProvider";
import { Session, SessionItem } from "../features/session/types";
import { EmbeddingPoint } from "../features/views/types";
import { getEmbeddingSpace } from "../features/views/api";

const labelMap: Record<string, string> = {
  "compound": "Compound",
  "gene_cluster": "BGC",
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

  // Container ref + size for square embedding space
  const embeddingSpaceContainerRef = React.useRef<HTMLDivElement | null>(null);
  const [embeddingSpaceSize, setEmbeddingSpaceSize] = React.useState<number | null>(null);

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
      .map((item) => {
        const fpIds = (item.fingerprints || []).map((fp) => fp.id).join(",");
        return `${item.id}:${item.status}:${item.updatedAt}:${fpIds}`;
      })
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
      setError(`At least three readouts are required to view the embedding space.`);
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
  }, [itemsKey]); // only rerun when itemsKey changes (i.e., notable changes to session items)

  // Adjust embedding space size on container resize
  React.useLayoutEffect(() => {
    if (typeof ResizeObserver === "undefined") return;

    const element = embeddingSpaceContainerRef.current;
    if (!element) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width;
        setEmbeddingSpaceSize((prev) => (prev === width ? prev : width));
      }
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, [points])

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

  // Calculate axes limits and add some padding
  const axisLimits = React.useMemo(() => {
    if (!points || points.length === 0) {
      return { xMin: undefined, xMax: undefined, yMin: undefined, yMax: undefined };
    }

    let minX = points[0].x;
    let maxX = points[0].x;
    let minY = points[0].y;
    let maxY = points[0].y;
    for (const p of points) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }

    const xRange = maxX - minX;
    const yRange = maxY - minY;

    // Use the larger range for both axes
    const baseRange = Math.max(xRange, yRange) || 1; // avoid 0
    const paddingFactor = 0.2; // 20% padding
    const fullRange = baseRange * (1 + paddingFactor);

    const xCenter = (minX + maxX) / 2;
    const yCenter = (minY + maxY) / 2;

    const halfRange = fullRange / 2;

    return {
      xMin: xCenter - halfRange,
      xMax: xCenter + halfRange,
      yMin: yCenter - halfRange,
      yMax: yCenter + halfRange,
    };
  }, [points]);

  return (
    <Box>
      {loading ? (
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
      ) : error ? (
        <Box>
          <Alert severity="error">
            {error}
          </Alert>
        </Box>
      ) : !loading && !error && points && points.length > 0 ? (
          <Box sx={{ flex: 1, minHeight: 0 }}>
            <Box
              ref={embeddingSpaceContainerRef}
              sx={{ width: "100%" }}
            >
              {embeddingSpaceSize && (
                <ScatterChart
                  width={embeddingSpaceSize}
                  height={embeddingSpaceSize * 0.8}
                  margin={{ top: 10, right: 10, bottom: 10, left: 10 }}
                  series={scatterSeries.map((group) => ({
                    label: labelMap[group.label] || group.label,
                    data: group.data,
                    markerSize: 5,
                    valueFormatter: (_value, context) => {
                      const idx = context.dataIndex;
                      const point = group.data[idx];
                      const score = scoreByChildId.get(point.id);
                      return score != null
                        ? `${point.name} (score ${(score * 100).toFixed(1)}%)`
                        : point.name;
                    },
                  }))}
                  // xAxis={[{ disableLine: true, disableTicks: true }]}
                  // yAxis={[{ disableLine: true, disableTicks: true }]}
                  xAxis={[{
                    label: "Dimension 1",
                    disableLine: false,
                    disableTicks: true,
                    min: axisLimits.xMin,
                    max: axisLimits.xMax,
                  }]}
                  yAxis={[{
                    label: "Dimension 2",
                    disableLine: false,
                    disableTicks: true,
                    min: axisLimits.yMin,
                    max: axisLimits.yMax,
                  }]}
                  grid={{ horizontal: false, vertical: false }}
                  sx={{
                    // Hide any remaining tick labels just in case
                    "& .MuiChartsAxis-tickLabel": {
                      display: "none",
                    },
                  }}
                />
              )}
            </Box>
          </Box>
      ) : (
        <Typography variant="body2">
          No embedding points to display.
        </Typography>
      )}
    </Box>
  )
}
