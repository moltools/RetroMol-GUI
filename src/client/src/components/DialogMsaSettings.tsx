import React from "react";
import Box from "@mui/material/Box";
import { DialogWindow } from "../components/DialogWindow";

type DialogMsaSettingsProps = {
  open: boolean;
  onClose: () => void;
}

export const DialogMsaSettings: React.FC<DialogMsaSettingsProps> = ({
  open,
  onClose,
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
        {/* Intentionally left empty for future MSA settings */}
      </Box>
    </DialogWindow>
  )
}
