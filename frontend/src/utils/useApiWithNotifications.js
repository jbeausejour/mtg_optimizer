import { useState } from 'react';
import { useNotification } from './NotificationContext';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

export const useApiWithNotifications = () => {
  const [loading, setLoading] = useState(false);
  const { 
    messageApi,
    notificationApi
  } = useNotification();
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleApiError = (error, operation = 'operation', item = '') => {
    console.error(`API Error in ${operation}:`, error);
    
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;
      
      switch (status) {
        case 401:
          notificationApi.warning({
            message: 'Session Expired',
            description: 'Please log in again to continue',
            placement: 'topRight',
          });
          logout();
          navigate('/login');
          break;
        case 403:
          notificationApi.error({
            message: 'Permission Denied',
            description: 'You do not have permission to perform this action',
            placement: 'topRight',
          });
          break;
        case 404:
          notificationApi.error({
            message: `Failed to ${operation}`,
            description: `${item} not found`,
            placement: 'topRight',
          });
          break;
        case 422:
          notificationApi.error({
            message: 'Validation Error',
            description: data.message || 'Validation failed',
            placement: 'topRight',
          });
          break;
        case 500:
          notificationApi.error({
            message: 'Server Error',
            description: 'Internal server error occurred',
            placement: 'topRight',
          });
          break;
        default:
          notificationApi.error({
            message: `Failed to ${operation}`,
            description: data.message || data.error || 'An error occurred',
            placement: 'topRight',
          });
      }
    } else if (error.request) {
      notificationApi.error({
        message: 'Network Error',
        description: 'Please check your internet connection and try again',
        placement: 'topRight',
      });
    } else {
      notificationApi.error({
        message: `Failed to ${operation}`,
        description: error.message || 'An unexpected error occurred',
        placement: 'topRight',
      });
    }
  };

  const executeWithNotifications = async (
    apiCall,
    {
      operation = 'operation',
      item = '',
      successMessage = null,
      loadingMessage = null,
      showLoadingIndicator = true,
      showSuccessNotification = true,
      onSuccess = null,
      onError = null,
    } = {}
  ) => {
    let loadingHide = null;
    
    try {
      setLoading(true);
      
      if (showLoadingIndicator) {
        const message = loadingMessage || `Processing ${operation}...`;
        // Use the direct API for v5
        loadingHide = messageApi.loading(message);
      }

      const result = await apiCall();
      
      if (showSuccessNotification && successMessage) {
        // Use the direct API for v5
        notificationApi.success({
          message: successMessage,
          placement: 'topRight',
        });
      }
      
      if (onSuccess) {
        onSuccess(result);
      }
      
      return result;
    } catch (error) {
      handleApiError(error, operation, item);
      
      if (onError) {
        onError(error);
      }
      
      throw error; // Re-throw so calling code can handle if needed
    } finally {
      setLoading(false);
      if (loadingHide) {
        loadingHide();
      }
    }
  };

  // Convenience methods for common operations
  const createWithNotifications = (apiCall, item = 'item', options = {}) => {
    return executeWithNotifications(apiCall, {
      operation: 'create',
      item,
      ...options,
    });
  };

  const updateWithNotifications = (apiCall, item = 'item', options = {}) => {
    return executeWithNotifications(apiCall, {
      operation: 'update',
      item,
      ...options,
    });
  };

  const deleteWithNotifications = (apiCall, item = 'item', options = {}) => {
    return executeWithNotifications(apiCall, {
      operation: 'delete',
      item,
      ...options,
    });
  };

  const saveWithNotifications = (apiCall, item = 'settings', options = {}) => {
    return executeWithNotifications(apiCall, {
      operation: 'save',
      item,
      ...options,
    });
  };

  const fetchWithNotifications = (apiCall, options = {}) => {
    return executeWithNotifications(apiCall, {
      operation: 'fetch',
      showSuccessNotification: false,
      showLoadingIndicator: false,
      ...options,
    });
  };

  return {
    loading,
    executeWithNotifications,
    createWithNotifications,
    updateWithNotifications,
    deleteWithNotifications,
    saveWithNotifications,
    fetchWithNotifications,
    handleApiError,
  };
};