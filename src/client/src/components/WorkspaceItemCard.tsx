import React from "react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import ScienceIcon from "@mui/icons-material/Science";
import BiotechIcon from "@mui/icons-material/Biotech";
import DeleteIcon from "@mui/icons-material/Delete";
import CircularProgress from "@mui/material/CircularProgress";
import { SessionItem } from "../features/session/types";
import { alpha } from "@mui/material/styles";

type WorkspaceItemCardProps = {
  item: SessionItem;
  selected: boolean;
  onToggleSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

// Helper to format "X ago"
function formatUpdatedAgo(updatedAt?: number): string {
  if (!updatedAt) return "Never updated";
  const now = Date.now();
  const diffMs = now - updatedAt;
  if (diffMs < 0) return "just now";

  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;

  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export const WorkspaceItemCard: React.FC<WorkspaceItemCardProps> = ({
  item,
  selected,
  onToggleSelect,
  onDelete
}) => {
  const isCompound = item.kind === "compound"; // there are only two types: "compound" and "gene_cluster"

  // Tick every 15s so "X ago" updates
  const [, forceTick] = React.useState(0);
  React.useEffect(() => {
    const id = window.setInterval(() => {
      forceTick(n => n + 1);
    }, 5000);
    return () => { window.clearInterval(id); }
  }, [])

  const isQueued = item.status === "queued";
  const showSpinner = item.status === "processing";
  const isError = item.status === "error";
  const isDone = item.status === "done";

  return (
    <Box
      onClick={() => onToggleSelect(item.id)}
      sx={(theme) => {
        const t = theme.vars || theme;
        return {
          borderRadius: 1,
          border: `1px solid ${selected ? t.palette.primary.main : "transparent"}`,
          p: 1.5,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 1.5,
          cursor: "pointer",
          "&:hover": { boxShadow: 10 },
          backgroundColor: selected ? alpha("#000000", 0.04) : alpha("#000000", 0.02),
          ...theme.applyStyles("dark", { backgroundColor: selected ? alpha("#ffffff", 0.06) : alpha("#ffffff", 0.03) }),
        }
      }}
    >
      <Stack direction="row" spacing={1.5} alignItems="center">
        <Checkbox
          size="small"
          checked={selected}
          onClick={(e) => {
            e.stopPropagation();
            onToggleSelect(item.id);
          }}
        />

        {isCompound ? (
          <ScienceIcon fontSize="small" />
        ) : (
          <BiotechIcon fontSize="small" />
        )}

        <Box>
          <Typography variant="body2" fontWeight={500} noWrap>
            {isCompound ? item.name : item.fileName}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Updated {formatUpdatedAgo(item.updatedAt)}
          </Typography>
        </Box>
      </Stack>
      
      <Stack direction="row" spacing={1} alignItems="center">
        {isQueued && (
          <Chip
            label="Queued"
            color="warning"
            size="small"
            sx={{ fontSize: "0.7rem", height: 20 }}
          />
        )}
        
        {showSpinner && (<CircularProgress size={16} thickness={4} />)}

        {isDone && (
          <Chip
            label="Ready"
            color="success"
            size="small"
            sx={{ fontSize: "0.7rem", height: 20 }}
          />
        )}

        {isError && (
          <Tooltip
            title={item.errorMessage || "An unknown error occurred."}
            placement="left"
            arrow
          >
            <Chip
              label="Error"
              color="error"
              size="small"
              sx={{ fontSize: "0.7rem", height: 20 }}
            />
          </Tooltip>
        )}

        <IconButton
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(item.id);
          }}
        >
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Stack>
    </Box>
  )
}
