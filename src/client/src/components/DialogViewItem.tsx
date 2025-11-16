import React from "react";
import { DialogWindow } from "../components/DialogWindow";

type DialogViewItemProps = {
  open: boolean;
  itemId?: string | null;
  onClose: () => void;
}

export const DialogViewItem: React.FC<DialogViewItemProps> = ({
  open,
  itemId,
  onClose,
}) => {
  return (
    <DialogWindow
      open={open}
      onClose={onClose}
      title="View item"
      dividers
      maxWidth="sm"
      actions={[
        { label: "Cancel", variant: "text", color: "inherit", onClick: onClose },
      ]}
    >
      {/* TODO */}
      <div>Viewing item: {itemId}</div>
    </DialogWindow>
  )
}
