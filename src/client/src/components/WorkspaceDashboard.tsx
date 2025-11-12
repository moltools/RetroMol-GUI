import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import MuiLink from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { useNotifications } from "../components/NotificationProvider";
import type { QueryResult } from "../features/query/types";
import { runQuery } from "../features/query/api";
import { Histogram, histogramFromSQLResults } from "./PlotHistogram";
import { PieChart, pieFromSQLResults } from "./PlotPieChart";

const labelMap: Record<string, string> = {
  "mibig": "MIBiG",
  "npatlas": "NPAtlas",
};

export const WorkspaceDashboard: React.FC = () => {
  const theme = useTheme();
  const { pushNotification } = useNotifications();

  // States to hold query results
  const [resultCov, setResultCov] = React.useState<QueryResult | null>(null);
  const [resultFps, setResultFps] = React.useState<QueryResult | null>(null);

  React.useEffect(() => {
    let canceled = false;

    const fetchBoth = async () => {
      const queries = [
        runQuery({
          name: "binned_coverage",
          params: {},
          paging: { limit: 20, offset: 0 },
          order: { column: "bin_start", dir: "asc" },
        }),
        runQuery({
          name: "fingerprint_source_counts",
          params: {},
          paging: { limit: 100, offset: 0 },
          order: { column: "count_per_source", dir: "desc" },
        })
      ]

      const [covRes, fpsRes] = await Promise.allSettled(queries);
      if (canceled) return; // early exit if component unmounted

      if (covRes.status === "fulfilled") {
        setResultCov(covRes.value);
      } else {
        pushNotification(covRes.reason?.message ?? "Coverage query failed", "error");
      }

      if (fpsRes.status === "fulfilled") {
        setResultFps(fpsRes.value);
      } else {
        pushNotification(fpsRes.reason?.message ?? "Fingerprint source counts query failed", "error");
      }
    }

    fetchBoth();

    return () => {
      canceled = true;
    }
  }, [pushNotification]); 

  return (
    <Box 
      sx={{ 
        width: "100%", 
        mx: "auto", 
        display: "flex", 
        flexDirection: "column", 
        gap: "16px" 
      }}
    >
      <Card
        variant="outlined"
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          flexGrow: 1,
        }}
      >
        <CardContent>
          <Typography component="h1" variant="subtitle1">
            Getting started
          </Typography>
          <Typography variant="body1">
            Welcome to the RetroMol dashboard! Here you can find an overview of available data in the database.
            Use the navigation menu on the left to upload your data in the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/upload"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Upload tab
            </MuiLink>
            .
            Biosynthetic fingerprints are automatically parsed from your data during upload.
            You can use the biosynthetic fingerprints parsed from you data for exploratory data analysis in the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/explore"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Explore tab
            </MuiLink>
            .
            Exploratory data analysis allows you to retrieve similar biosynthetic fingerprints and their associated metadata from the database using your uploaded data.
          </Typography>
        </CardContent>
      </Card>
      <Grid container spacing={2} columns={12} alignItems='stretch' sx={{ mb: (theme) => theme.spacing(2) }}>
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: 'flex' }}>
          <Card variant="outlined" sx={{ display: "flex", "flexDirection": "column", flex: 1 }}>
            <CardContent>
              {resultCov ? (
                <Histogram
                  rows={histogramFromSQLResults(resultCov)}
                  title="Mapping coverage parsed NPAtlas compounds"
                  height={300}
                  binSize={0.05}
                  domain={{ min: 0, max: 1 }}
                  formatBinLabel={(start, end) => `${start}-${end}`}
                />
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Loading...
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: 'flex' }}>
          <Card variant="outlined" sx={{ display: "flex", "flexDirection": "column", flex: 1 }}>
            <CardContent>
              {resultFps ? (
                <PieChart
                  rows={pieFromSQLResults(resultFps, "source", "count_per_source")}
                  title="Source compound biosynthetic fingerprints (coverage &ge; 0.5)"
                  height={300}
                  labelFormatter={(label) => labelMap[label.toLowerCase()] ?? label}
                />
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Loading...
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
