import Box from "@mui/material/Box";
import CssBaseline from "@mui/material/CssBaseline";
import AppTheme from "../theme/AppTheme";
import HomeAppBar from "../components/home/HomeAppBar";
import Hero from "../components/home/Hero";
import Footer from "../components/shared/Footer";

export default function Home(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props}>
      <CssBaseline enableColorScheme />
      <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <Box sx={{ flexGrow: 1 }}>
          <HomeAppBar />
          <Hero />
        </Box>
        <Footer />
      </Box>
    </AppTheme>
  )
}