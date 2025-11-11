import * as React from "react";
import { List, ListItem, ListItemButton, ListItemIcon, ListItemText, Stack } from "@mui/material";
import { Explore as ExploreIcon, HomeRounded as HomeRoundedIcon, UploadFile as UploadFileIcon } from "@mui/icons-material";
import { useNavigate, useLocation } from "react-router-dom";

const mainListItems = [
  { 
    text: "Dashboard", 
    icon: <HomeRoundedIcon />,
    to: `/dashboard`
  },
  { 
    text: "Upload", 
    icon: <UploadFileIcon />,
    to: `/dashboard/upload`
  },
  { 
    text: "Explore", 
    icon: <ExploreIcon />,
    to: `/dashboard/explore`
  },
]

interface MenuItemProps {
  text: string;
  icon: React.ReactNode;
  to: string;
}

const MenuItem: React.FC<MenuItemProps> = ({ text, icon, to }) => {
  const navigate = useNavigate();
  const location = useLocation();

  // Check if the current pathname matches the menu"s target path.
  const isSelected = location.pathname === to;

  const handleClick = () => {
    navigate(to);
  }

  return (
    <ListItem disablePadding sx={{ display: "block" }}>
      <ListItemButton
        selected={isSelected}
        onClick={() => { handleClick(); }}
      >
        <ListItemIcon>{icon}</ListItemIcon>
        <ListItemText primary={text} />
      </ListItemButton>
    </ListItem>
  )
}

export const MenuContent: React.FC = () => {
  return (
    <Stack sx={{ flexGrow: 1, p: 1, justifyContent: "space-between" }}>
      <List dense>
        {mainListItems.map((item, index) => (
          <MenuItem
            key={index}
            text={item.text}
            icon={item.icon}
            to={item.to}
          />
        ))}
      </List>
    </Stack>
  )
}
