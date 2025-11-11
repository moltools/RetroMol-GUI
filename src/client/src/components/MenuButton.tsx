import React from "react";
import { Badge, IconButton, IconButtonProps, Tooltip, badgeClasses } from "@mui/material";

export interface MenuButtonProps extends IconButtonProps {
  showBadge?: boolean;
  tooltip?: string;
}

export const MenuButton: React.FC<MenuButtonProps> = ({ showBadge = false, tooltip = "", ...props }) => {
  return (
    <Badge
      color="error"
      variant="dot"
      invisible={!showBadge}
      sx={{ [`& .${badgeClasses.badge}`]: { right: 2, top: 2 } }}
    >
      <Tooltip title={tooltip} placement="bottom" arrow>
      <IconButton size="small" {...props} />
      </Tooltip>
    </Badge>
  )
}
