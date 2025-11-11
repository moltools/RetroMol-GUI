import React, { useEffect } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import MuiDrawer, { drawerClasses } from "@mui/material/Drawer";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import CloseIcon from "@mui/icons-material/Close";
import { styled, useTheme } from "@mui/material/styles";
import { useNotifications } from "./NotificationProvider";

// Custom styling for the drawer
const drawerWidth = 400;
const Drawer = styled(MuiDrawer)({
  width: drawerWidth,
  flexShrink: 0,
  boxSizing: "border-box",
  mt: 10,
  [`& .${drawerClasses.paper}`]: {
    width: drawerWidth,
    boxSizing: "border-box",
  },
})

interface NotificationDrawerProps {
  open: boolean;
  handleClose: () => void;
}

export const NotificationDrawer: React.FC<NotificationDrawerProps> = ({ open, handleClose }) => {
  const { notifications, markAllAsRead } = useNotifications();
  const theme = useTheme();

  // When the drawer opens, mark all notifications as read
  useEffect(() => {
    if (open) { markAllAsRead(); }
  }, [open])

  return (
    <Drawer 
    anchor="right" 
    open={open} 
    onClose={handleClose}
  >
      <Box 
        sx={{ 
          width: drawerWidth, 
          height: "100%", 
          bgcolor: "background.paper",
          borderLeft: "1px solid", 
          borderColor: "divider", 
          pt: 1.5, 
          overflowY: "auto",
          display: "flex",
        }}
      >
      <Stack spacing={2} width="100%">
        
        <CloseIcon 
          onClick={handleClose} 
          aria-label="Close notifications" 
          sx={{ 
            position: "absolute", 
            right: 16, 
            cursor: "pointer", 
          }}
        />

        {notifications.length === 0 ? (
          <Typography 
            variant="body2"
            sx={{
              px: 3,
              pt: "4px",
              pb: 2,
            }}
          >
            No notifications to show.
          </Typography>
        ) : (
          <Stack
            sx={{
              overflowY: "auto",
              px: 3,
              pt: "4px",
              pb: 2,
            }}
          >
            {notifications.slice(0).reverse().map((notification) => (
              <ListItem
                key={crypto.randomUUID()}
                divider
                sx={{
                  borderLeft: `4px solid ${theme.palette[notification.level].main}`,
                  backgroundColor: "transparent",
                  transition: "background-color 0.3s ease",
                }}
              >
                <ListItemText
                  primary={
                    <Typography
                      variant="subtitle2"
                      sx={{ fontWeight: notification.isNew ? 600 : 400 }}
                    >
                      {notification.content}
                    </Typography>
                  }
                  secondary={
                    notification.isNew ? (
                      // show a chip with the level color for new notifications.
                      <Chip label="New" size="small" color={notification.level} />
                    ) : (
                      new Date(notification.timestamp).toLocaleString()
                    )
                  }
                  secondaryTypographyProps={{ component: "div" }}  // render wrapper as div instead of p
                />
              </ListItem>
            ))}
          </Stack>
        )}
      </Stack>
      </Box>
    </Drawer>
  )
}
