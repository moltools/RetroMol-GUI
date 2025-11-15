import React from "react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import { alpha, useTheme } from "@mui/material/styles";

type CoverageBarProps = {
  coverage: number; // value between 0 and 1
  getTooltipTitle: (value: number) => string;
  getCoverageColor: (theme: any, value: number) => string;
  tooltipPosition?: "top" | "bottom" | "left" | "right";
  width?: number | string;
  height?: number | string;
}

export const CoverageBar: React.FC<CoverageBarProps> = ({
  coverage,
  getTooltipTitle,
  getCoverageColor,
  tooltipPosition = "top",
  width = "100%",
  height = 16
}) => {
  const theme = useTheme();
  const value = Math.max(0, Math.min(1, coverage));

  return (
    <Box sx={{ mt: 0.5 }}>
      <Tooltip title={getTooltipTitle(value)} placement={tooltipPosition} arrow>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Box
            sx={(theme) => {
              const t = theme.vars || theme;
              return {
                flexGrow: 1,
                height: height,
                width: width,
                borderRadius: 999,
                overflow: "hidden",
                backgroundColor: alpha("#000000", 0.1),
                ...theme.applyStyles("dark", { backgroundColor: alpha("#ffffff", 0.1) })
            }}}
          >
            <Box
              sx={(theme) => {
                const t = theme.vars || theme;
                const barColor = getCoverageColor(t, value);
                return {
                  width: `${value * 100}%`,
                  height: "100%",
                  backgroundColor: barColor,
                  transition: "width 200ms ease-out",
                };
              }}
            />
          </Box>
        </Stack>
      </Tooltip>
    </Box>
  )
}
