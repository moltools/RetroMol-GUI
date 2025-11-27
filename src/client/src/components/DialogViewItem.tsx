import React from "react";
import { Stack } from "@mui/material";
import { Typography } from "@mui/material";
import { DialogWindow } from "../components/DialogWindow";
import { SessionItem } from "../features/session/types";
import { SvgViewer } from "../components/SvgViewer";

type DialogViewItemProps = {
  open: boolean;
  item?: SessionItem | null;
  onClose: () => void;
}

export const DialogViewItem: React.FC<DialogViewItemProps> = ({
  open,
  item,
  onClose,
}) => {
  const [svg, setSvg] = React.useState<string | null>(null);

  // Set dummy SVG for demonstration purposes
  React.useEffect(() => {
    if (item) {
      // In a real application, fetch or generate the SVG based on the item
      const dummySvg = `<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
        <circle cx="100" cy="100" r="80" fill="lightblue" stroke="blue" stroke-width="2"/>
        <text x="100" y="115" font-size="20" text-anchor="middle" fill="darkblue">Item ${item.id}</text>
      </svg>`;
      setSvg(dummySvg);
    } else {
      setSvg(null);
    }
  }, [item]);

  return (
    <DialogWindow
      open={open}
      onClose={onClose}
      title="View item"
      dividers
      actions={[
        { label: "Cancel", variant: "text", color: "inherit", onClick: onClose },
      ]}
    >
      { item && (
        <Stack direction="column" spacing={2} alignItems="center">
          <Typography variant="caption" color="textSecondary">
            Viewing item ID: {item.id}
          </Typography>
          {svg && (
            <SvgViewer
              svg={svg}
              onZoomChange={() => {}}
              onElementClick={() => {}}
            />
          )}
        </Stack>
      )}
    </DialogWindow>
  )
}
