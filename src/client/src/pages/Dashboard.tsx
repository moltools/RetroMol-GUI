import CssBaseline from "@mui/material/CssBaseline";
import AppTheme from "../theme/AppTheme";
import { OverlayProvider } from "../components/workspace/OverlayProvider";
import { NotificationProvider } from "../components/workspace/NotificationProvider";
import { Workspace } from "../components/workspace/Workspace";

interface DashboardProps {
  disableCustomTheme?: boolean;
};

export default function Dashboard(props: DashboardProps) {
  return (
    <AppTheme {...props}>
      <CssBaseline enableColorScheme />
      <OverlayProvider>
        <NotificationProvider>
          <Workspace />
        </NotificationProvider>
      </OverlayProvider>
    </AppTheme>
  );
};
