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
  const [loading, setLoading] = React.useState<boolean>(true);

  // Retrieve session from the server on component mount
  React.useEffect(() => {
    let alive = true;
    setLoading(true);
    getSession()
      .then(sess => setSession(sess))
      .catch(err => {
        console.error("Error loading session:", err);
        navigate("/notfound");
      })
      .finally(() => { if (alive) setLoading(false); })
    return () => { alive = false; }
  }, [navigate])

  // Overlay follows loading state
  React.useEffect(() => {
    if (loading) showOverlay(); else hideOverlay();
  }, [loading, showOverlay, hideOverlay])

  // Auto-save session whenever session changes
  React.useEffect(() => {
    if (!session) return;
    saveSession(session).catch(err => {
      const msg = err instanceof Error ? err.message : String(err);
      pushNotification(`Failed to save session: ${msg}`, "error");
    })
  }, [session, pushNotification]);

  // While loading, render nothing (overlay is shown)
  if (loading) return null; 
  if (!session) return null; // should not happen, but TS type guard

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
            <Route path="upload" element={<WorkspaceUpload session={session} setSession={setSession} />} />
            <Route path="explore" element={<WorkspaceExplore session={session} setSession={setSession} />} />
          </Routes>
        </Stack>
      </Box>
    </Box>
  )
}
