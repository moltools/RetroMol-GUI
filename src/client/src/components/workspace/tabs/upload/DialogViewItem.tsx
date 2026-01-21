import React from "react";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import { SessionItem } from "../../../../features/session/types";
import { DialogWindow } from "../../../shared/DialogWindow";
import { SvgViewer } from "../../../shared/SvgViewer";

type DialogViewItemProps = {
  sessionId: string;
  item: SessionItem;
  open: boolean;
  onClose: () => void;
};

export const DialogViewItem: React.FC<DialogViewItemProps> = ({
  sessionId,
  item,
  open,
  onClose,
}) => {
  const isCompound = item.kind === "compound"; // there are only two types: "compound" and "cluster"

  const [loading, setLoading] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string | null>(null);
  const [svg, setSvg] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) {
      return;
    };

    if (!isCompound) {
      return;
    };

    const fetchSvg = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/drawItem?sessionId=${encodeURIComponent(sessionId)}&itemId=${encodeURIComponent(item.id)}`
        );

        if (!response.ok) {
          throw new Error(`Error fetching SVG: ${response.statusText}`);
        };

        const data = await response.json();

        if (!("svg" in data) || typeof data.svg !== "string") {
          throw new Error("Invalid response format: missing or invalid 'svg' property");
        };

        // Data should contain 'svg' prop with SVG content
        if (data.svg.trim() === "") {
          throw new Error("Received empty SVG content");
        };

        setSvg(data.svg);
      } catch (err: any) {
        setError(err.message || "Unknown error");
      } finally {
        setLoading(false);
      };
    };

    fetchSvg();
  }, [open, isCompound, sessionId, item.id]);
  
  return (
    <DialogWindow
      open={open}
      onClose={onClose}
      title="View item"
      dividers
      actions={[
        { label: "Close", variant: "text", color: "inherit", onClick: onClose },
      ]}
    >
      {!isCompound && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Viewing is only available for compounds.
        </Alert>
      )}

      {loading && (
        <CircularProgress size={24} />
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {(isCompound && !loading && !error) && (
        <SvgViewer
          svg={svg || ""}
          onZoomChange={() => {}}
          onElementClick={() => {}}
          height={600}
        />
      )}
    </DialogWindow>
  );
};
