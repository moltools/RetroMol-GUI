import React from "react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";
import { CSS } from "@dnd-kit/utilities";
import { useSortable } from "@dnd-kit/sortable";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";
import { MsaItem, Reference } from "./QueryResultView";

interface SortableRowProps {
  row: MsaItem;
  labelWidth: number;
  children: React.ReactNode;
};

const fmt = (v: number | null, digits: number) => 
    v == null || Number.isNaN(v) ? "" : v.toFixed(digits);

const referenceToUrl = (ref: Reference): string | null => {
  switch (ref.database_name.toLowerCase()) {
    case "npatlas":
      return `https://www.npatlas.org/explore/compounds/${ref.database_identifier}`;
    default:
      return null;
  };
};

export const SortableRow: React.FC<SortableRowProps> = ({
  row,
  labelWidth,
  children,
}) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: row.id });

  // Setup outlink to reference for row
  const [ref, setRef] = React.useState<Reference | null>(null);
  const url = React.useMemo(() => (ref ? referenceToUrl(ref) : null), [ref]);
  
  // Set reference on mount
  React.useEffect(() => {
    if (row.references && row.references.length > 0) {
      setRef(row.references[0]);
    } else {
      setRef(null);
    }
  }, [row.references]);

  const alignText = fmt(row.alignment_score, 2);
  const cosineText = fmt(row.cosine_score, 2);
  const scoreBlockWidth = 40;

  return (
    <>
      <Box
        ref={setNodeRef}
        sx={{
          transform: transform ? CSS.Transform.toString(transform) : undefined,
          transition,
          m: 0,
          p: 0,
          height: 20,
          fontWeight: 600,
          zIndex: 100,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 1,
          borderRadius: 1,
          backgroundColor: "background.paper",
          border: "1px solid transparent",
          borderColor: "transparent",
        }}
      >
        <Box
          {...listeners}
          {...attributes}
          sx={{
            display: "flex",
            alignItems: "center",
            cursor: "grab",
          }}
          onClick={e => e.stopPropagation()} // don't trigger center selection on drag
        >
          <DragIndicatorIcon fontSize="small" />
        </Box>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ width: "100%", pl: 1 }}>
          <Tooltip title={row.name || row.id} arrow>
            <Typography
              variant="body2"
              component={url ? "a" : "span"}
              href={url ?? undefined}
              target={url ? "_blank" : undefined}
              rel={url ? "noopener noreferrer" : undefined}
              onClick={(e) => {
                if (url) e.stopPropagation(); // prevent row drag / selection
              }}
              sx={{
                fontWeight: 600,
                maxWidth: labelWidth - 100,
                lineHeight: "20px",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                zIndex: 101,
                userSelect: "none",

                // link-only styling
                textDecoration: url ? "underline" : "none",
                cursor: url ? "pointer" : "default",
                color: "inherit",

                "&:hover": url
                  ? { color: "primary.main" }
                  : undefined,
              }}
            >
              {row.name || row.id}
            </Typography>
          </Tooltip>

          {/* Scores */}
          <Stack
            direction="column"
            sx={{
              width: scoreBlockWidth,
              flex: `0 0 ${scoreBlockWidth}px`,
              alignItems: "flex-end",
              justifyContent: "center",
              lineHeight: 1,
            }}
          >
            <Tooltip
              title={`Alignment score: ${alignText}`}
              placement="right"
              arrow
            >
              <Typography
                variant="caption"
                sx={{
                  lineHeight: 1,
                  fontFamily: "monospace",
                  fontSize: "0.70rem",
                }}
              >
                {alignText}
              </Typography>
            </Tooltip>
            <Tooltip
              title={`Cosine score: ${cosineText}`}
              placement="right"
              arrow
            >
              <Typography
                variant="caption"
                sx={{
                  lineHeight: 1,
                  fontFamily: "monospace",
                  fontSize: "0.70rem",
                }}
              >
                {cosineText}
              </Typography>
            </Tooltip>
          </Stack>
        </Stack>
      </Box>
      
      {/* Motifs */}
      {children}

      {/* Row line */}
      <Box
        sx={{
          gridColumn: "1 / -1", // span every column
          borderBottom: "1px solid",
          borderColor: "divider",
          height: 0,
          mt: "-19px",
          zIndex: 50,
        }}
      />
    </>
  );
};