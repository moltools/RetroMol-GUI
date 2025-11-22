import React from "react";
import Box from "@mui/material/Box";
import { DialogWindow } from "../components/DialogWindow";
import { QuerySettings } from "../features/session/types";

type DialogQuerySettingsProps = {
  open: boolean;
  onClose: () => void;
  settings: QuerySettings;
  onSave: (newSettings: QuerySettings) => void;
}

export const DialogQuerySettings: React.FC<DialogQuerySettingsProps> = ({
  open,
  onClose,
  settings,
  onSave,
}) => {
  return (
    <DialogWindow
      open={open}
      onClose={onClose}
      title="Query settings"
      dividers
      actions={[
        { label: "Close", variant: "text", color: "inherit", onClick: onClose },
      ]}
    >
      <Box display="flex" flexDirection="column" gap={2} py={1}>
        {/* Intentionally left empty for future query settings */}
      </Box>
    </DialogWindow>
  )
}
