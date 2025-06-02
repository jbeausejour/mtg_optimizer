import React, { createContext, useContext } from 'react';
import { message, notification } from 'antd';

const NotificationContext = createContext();

export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
};

export const NotificationProvider = ({ children }) => {
  const [messageApi, messageHolder] = message.useMessage();
  const [notificationApi, notificationHolder] = notification.useNotification();

  const value = {
    messageApi,
    notificationApi,
  };

  return (
    <NotificationContext.Provider value={value}>
      {messageHolder}
      {notificationHolder}
      {children}
    </NotificationContext.Provider>
  );
};