import * as React from "react";
import { Drawer, Stack, drawerClasses } from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import { MenuContent } from "./MenuContent";
import { NotificationDrawer } from "./NotificationDrawer";
import { BuildVersion } from "./BuildVersion";
import { WorkspaceControls } from "./WorkspaceControls";

interface SideMenuMobileProps {
  open: boolean | undefined;
  toggleDrawer: (newOpen: boolean) => () => void;
}

export const WorkspaceSideMenuMobile: React.FC<SideMenuMobileProps> = ({ open, toggleDrawer }) => {
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  // Open the notification drawer
  const handleDrawerOpen = () => {
    toggleDrawer(false)();
    setDrawerOpen(true);
  }

  // Close the notification drawer
  const handleDrawerClose = () => {
    setDrawerOpen(false);
  }

  return (
    <>
      <Drawer
        anchor="right"
        open={open}
        onClose={toggleDrawer(false)}
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          [`& .${drawerClasses.paper}`]: {
            backgroundImage: "none",
            backgroundColor: "background.paper",
            borderLeft: "1px solid", 
            borderColor: "divider", 
          },
        }}
      >
        <Stack sx={{ width: "250px", height: "100vh" }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <WorkspaceControls handleDrawerOpen={handleDrawerOpen} sx={{ p: 1.5, pb: 0 }} />
            <CloseIcon 
              onClick={toggleDrawer(false)}
              aria-label="Close notifications" 
              sx={{ 
                position: "absolute", 
                right: 16, 
                cursor: "pointer", 
              }}
            />
          </Stack>
          <Stack sx={{ flexGrow: 1 }}>
            <MenuContent />
            <BuildVersion />
          </Stack>
        </Stack>
      </Drawer>
      <NotificationDrawer open={drawerOpen} handleClose={handleDrawerClose} />
    </>
  )
}
