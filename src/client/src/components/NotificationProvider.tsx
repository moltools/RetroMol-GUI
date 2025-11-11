import React, { createContext, useContext, useState } from "react";

// Define possible notification levels
export type NotificationLevel = "error" | "warning" | "success" | "info";

// Extend the Notification interface with a "level" property
export interface Notification {
  id: number;
  content: string;
  timestamp: Date;
  isNew: boolean;
  level: NotificationLevel;
}

export interface NotificationContextType {
  notifications: Notification[];
  pushNotification: (content: string, level?: NotificationLevel) => void;
  markAllAsRead: () => void;
}

const NotificationContext = createContext<NotificationContextType>({
  notifications: [],
  pushNotification: () => {},
  markAllAsRead: () => {},
})

export function useNotifications() {
  return useContext(NotificationContext);
}

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const pushNotification = (content: string, level: NotificationLevel = "info") => {
    console.log("Pushing notification:", content, level);
    setNotifications((prev) => {
      const newNotification: Notification = {
        id: Date.now(), // or use some uuid mechanism
        content,
        timestamp: new Date(),
        isNew: true,
        level, // store the level so you can adjust styling
      };

      let updated = [...prev, newNotification];

      // Keep a maximum of 50 notifications
      if (updated.length > 50) {
        updated = updated.slice(updated.length - 50);
      }
      return updated;
    })
  }

  const markAllAsRead = () => {
    setNotifications((prev) =>
      prev.map((notification) => ({ ...notification, isNew: false }))
    )
  }

  return (
    <NotificationContext.Provider value={{ notifications, pushNotification, markAllAsRead }}>
      {children}
    </NotificationContext.Provider>
  )
}
