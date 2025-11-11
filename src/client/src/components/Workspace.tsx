import React from "react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import { alpha } from "@mui/material/styles";
import { Routes, Route, useNavigate } from "react-router-dom";
import { useNotifications } from "../components/NotificationProvider";
import { useOverlay } from "../components/OverlayProvider";
import { Session } from "../features/session/types";
import { getSession, saveSession } from "../features/session/api";
import { WorkspaceNavbar } from "./WorkspaceNavbar";
import { WorkspaceSideMenu } from "./WorkspaceSideMenu";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { WorkspaceDashboard } from "./WorkspaceDashboard";
import { WorkspaceUpload } from "./WorkspaceUpload";
import { WorkspaceExplore } from "./WorkspaceExplore";

export const Workspace: React.FC = () => {
  const { showOverlay, hideOverlay } = useOverlay();
  const { pushNotification } = useNotifications();
  const navigate = useNavigate();
  const [session, setSession] = React.useState<Session | null>(null);

  // Retrieve session from the server on component mount
  React.useEffect(() => {
    getSession()
      .then(sess => setSession(sess))
      .catch(err => {
        console.error("Error loading session:", err);
        navigate("/notfound");
      })
  }, [navigate])

  // Auto-save session whenever session changes
  React.useEffect(() => {
    if (!session) return;
    
    saveSession(session)
      .then(() => {}) // save successful; do nothing
      .catch(err => {
        const msg = err instanceof Error ? err.message : String(err);
        pushNotification(`Failed to save session: ${msg}`, "error");
      })
  }, [session])

  // Display loading overlay until session is set
  if (!session) {
    showOverlay();
    return null;
  } else {
    hideOverlay();
  }

  return (
    <Box sx={{ display: "flex"}}>
      <WorkspaceNavbar />
      <WorkspaceSideMenu />
      <Box
        component="main"
        sx={theme => ({
          flexGrow: 1,
          backgroundColor: theme.vars
            ? `rgba(${theme.vars.palette.background.defaultChannel} /  1)`
            : alpha(theme.palette.background.default, 1),
          overflow: "auto",
        })}
      >
        <Stack
          spacing={2}
          sx={{ alignItems: "center", mx: 3, pb: 5, mt: { xs: 8, md: 0 } }}
        >
          <WorkspaceHeader />
          <Routes>
            <Route index element={<WorkspaceDashboard />} />
            <Route path="upload" element={<WorkspaceUpload />} />
            <Route path="explore" element={<WorkspaceExplore />} />
          </Routes>
        </Stack>
      </Box>
    </Box>
  )
}
