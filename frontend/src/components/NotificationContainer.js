import React, { useEffect, useRef } from 'react';
import { message, notification } from 'antd';

/**
 * A simplified notification container that ensures proper rendering
 * of Ant Design notifications regardless of other component structures
 */
const NotificationContainer = () => {
  const messageContainerRef = useRef(null);
  const notificationContainerRef = useRef(null);

  useEffect(() => {
    // Create DOM elements once and store refs
    if (!messageContainerRef.current) {
      const msgContainer = document.createElement('div');
      msgContainer.className = 'ant-message-root';
      msgContainer.style.position = 'fixed';
      msgContainer.style.top = '24px';
      msgContainer.style.left = '50%';
      msgContainer.style.transform = 'translateX(-50%)';
      msgContainer.style.zIndex = '9999';
      document.body.appendChild(msgContainer);
      messageContainerRef.current = msgContainer;
    }

    if (!notificationContainerRef.current) {
      const notifContainer = document.createElement('div');
      notifContainer.className = 'ant-notification-root';
      notifContainer.style.position = 'fixed';
      notifContainer.style.zIndex = '9999';
      notifContainer.style.top = '24px';
      notifContainer.style.right = '24px';
      document.body.appendChild(notifContainer);
      notificationContainerRef.current = notifContainer;
    }

    console.log('Created message container:', messageContainerRef.current);
    console.log('Created notification container:', notificationContainerRef.current);
    
    // Configure message and notification to use these containers
    message.config({
      top: 24,
      duration: 3,
      maxCount: 3,
      getContainer: () => messageContainerRef.current,
    });

    notification.config({
      placement: 'topRight',
      duration: 4.5,
      maxCount: 3,
      getContainer: () => notificationContainerRef.current,
    });

    console.log('✅ Notification system initialized');

    // Test notification to verify setup
    setTimeout(() => {
      console.log('Showing test notification...');
      message.info('Notification system initialized');
    }, 1000);

    return () => {
      // Don't remove on unmount - this could disrupt notifications
    };
  }, []);

  return null;
};

export default NotificationContainer;