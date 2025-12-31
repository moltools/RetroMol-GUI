import React from "react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Fade from "@mui/material/Fade";
import { alpha } from "@mui/material/styles";
import { Routes, Route, useNavigate } from "react-router-dom";
import { useNotifications } from "../components/NotificationProvider";
import { useOverlay } from "../components/OverlayProvider";
import { Session } from "../features/session/types";
import { getSession, refreshSession, saveSession } from "../features/session/api";
import { WorkspaceNavbar } from "./WorkspaceNavbar";
import { WorkspaceSideMenu } from "./WorkspaceSideMenu";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { WorkspaceDashboard } from "./WorkspaceDashboard";
import { WorkspaceUpload } from "./WorkspaceUpload";
import { WorkspaceExplore } from "./WorkspaceExplore";
import { WorkspaceQuery } from "./WorkspaceQuery";

export const Workspace: React.FC = () => {
  const { showOverlay, hideOverlay } = useOverlay();
  const { pushNotification } = useNotifications();
  const navigate = useNavigate();
  const [loading, setLoading] = React.useState<boolean>(true);
  const [session, setSession] = React.useState<Session | null>(null);

  // Track source of last update to session; prevents race conditions
  const lastUpdatedSourceRef = React.useRef<"local" | "remote" | null>(null);

  const setSessionLocal = React.useCallback(
    (updater: (prev: Session) => Session) => {
      lastUpdatedSourceRef.current = "local";
      setSession((prev) => (prev ? updater(prev) : prev));
    },
    []
  );

  const setSessionRemote = React.useCallback(
    (next: Session) => {
      lastUpdatedSourceRef.current = "remote";
      setSession(next);
    },
    []
  );

  // Retrieve session from the server on component mount
  React.useEffect(() => {
    let alive = true;
    setLoading(true);
    getSession()
      .then(sess => {
        if (!alive) return;
        setSessionRemote(sess);
      })
      .catch(err => {
        console.error("Error loading session:", err);
        navigate("/notfound");
      })
      .finally(() => { if (alive) setLoading(false); })
    return () => { alive = false; }
  }, [navigate])

  // Subscribe to server-sent events
  React.useEffect(() => {
    if (!session?.sessionId) return;

    let alive = true;

    // Debounce refreshes to avoid spamming if multiple events arrive quickly
    let refreshTimer: number | null = null;
    const scheduleRefresh = () => {
      if (!alive) return;
      if (refreshTimer !== null) return; // already scheduled
      refreshTimer = window.setTimeout(() => {
        refreshTimer = null;
        refreshSession(session.sessionId)
          .then((fresh) => {
            if (!alive) return;
            setSessionRemote(fresh);
          })
          .catch((err) => {
            const msg = err instanceof Error ? err.message : String(err);
            pushNotification(`Failed to refresh session: ${msg}`, "error");
          });
      }, 250); // based on chattiness of events
    };

    // Create SSE connection 
    const SSE_BASE = process.env.REACT_APP_SSE_BASE ?? "";
    console.log(`SSE connecting to ${SSE_BASE}/api/sessionEvents?sessionId=${session.sessionId}`);
    const es = new EventSource(
      `${SSE_BASE}/api/sessionEvents?sessionId=${encodeURIComponent(session.sessionId)}`
    );

    es.addEventListener("hello", () => {
      // Refresh once on connect so we're in sync
      scheduleRefresh();
    });

    // Backend should emit this when job/item status/results changed
    es.addEventListener("item_updated", () => {
      scheduleRefresh();
    });

    // Backend should emit this when session is merged/saved
    es.addEventListener("session_merged", () => {
      scheduleRefresh();
    });

    es.addEventListener("keepalive", () => {
      // No-op; just to keep connection alive
    });

    es.onopen = () => {
      console.log("SSE connection opened for session events");
    };

    es.onmessage = (e) => {
      // Generic message handler; shouldn't be called if specific events are handled
      console.debug("SSE message received:", e.data);
    };

    es.onerror = (err) => {
      // Fires on transient disconnects too; EventSource will retry automatically
      console.debug("SSE transient error; will retry", {
        readyState: es.readyState, // 0=CONNECTING, 1=OPEN, 2=CLOSED
      });
      // Don't close here; don't spam notifications
    };

    return () => {
      alive = false;
      if (refreshTimer !== null) window.clearTimeout(refreshTimer);
      es.close();
    };
  // }, [session?.sessionId, setSessionRemote, pushNotification]);
  }, [session?.sessionId, setSessionRemote]);

  // Overlay follows loading state
  React.useEffect(() => {
    if (loading) showOverlay(); else hideOverlay();
  }, [loading, showOverlay, hideOverlay])

  // Auto-save session whenever session changes
  React.useEffect(() => {
    if (!session) return;
    if (lastUpdatedSourceRef.current !== "local") return; // only auto-save if local changes

    // Reset source so we don't double-save
    lastUpdatedSourceRef.current = null;

    saveSession(session).catch(err => {
      const msg = err instanceof Error ? err.message : String(err);
      pushNotification(`Failed to save session: ${msg}`, "error");
    })
  }, [session]);

  if (!session && !loading) {
    // Hard failure; couldn't load session at all
    return null;
  }

  // Determine what to show
  const showContent = !!session && !loading;

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
            
          {/* Actual workspace content fades in once session is ready */}
          {session && (
            <Fade in={showContent} timeout={200} unmountOnExit>
              <Box sx={{ width: "100%" }}>
                <Routes>
                  <Route index element={<WorkspaceDashboard />} />
                  <Route path="upload" element={<WorkspaceUpload session={session} setSession={setSessionLocal} />} />
                  <Route path="explore" element={<WorkspaceExplore session={session} setSession={setSessionLocal} />} />
                  <Route path="query" element={<WorkspaceQuery session={session} setSession={setSessionLocal} />} />
                </Routes>
              </Box>
            </Fade>
          )}
          
        </Stack>
      </Box>
    </Box>
  )
}
