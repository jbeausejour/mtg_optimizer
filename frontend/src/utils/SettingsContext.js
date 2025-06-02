import React, { createContext, useContext, useState, useEffect } from 'react';
import api from './api';

const SettingsContext = createContext();

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};

export const SettingsProvider = ({ children }) => {
  const [settings, setSettings] = useState({
    itemsPerPage: 20, // Default value
    theme: 'light',
    defaultOptimizationStrategy: 'milp',
    priceAlertThreshold: 10,
    enablePriceAlerts: false,
    scryfallApiKey: ''
  });
  const [loading, setLoading] = useState(true);

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      if (!token) {
        setLoading(false);
        return;
      }

      const response = await api.get('/settings', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      
      setSettings(prevSettings => ({
        ...prevSettings,
        ...response.data
      }));
    } catch (error) {
      console.error('Error fetching settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateSettings = async (newSettings) => {
    try {
      const token = localStorage.getItem('accessToken');
      await api.post('/settings', newSettings, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      
      setSettings(prevSettings => ({
        ...prevSettings,
        ...newSettings
      }));
      
      return true;
    } catch (error) {
      console.error('Error updating settings:', error);
      return false;
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const value = {
    settings,
    updateSettings,
    loading,
    refreshSettings: fetchSettings
  };

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
};