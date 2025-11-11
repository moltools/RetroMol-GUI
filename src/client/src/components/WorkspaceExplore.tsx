import React from "react";
import { Box, Card, CardContent, Typography } from "@mui/material";

export const WorkspaceExplore: React.FC = () => {
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
              The Explore tab is still under development. Please check back later for updates!
            </Typography>
          </CardContent>
        </Card>
      </Box>
    )
}
