import React, { createContext, useState, useContext, useEffect } from 'react';
import { ConfigProvider, theme as antdTheme } from 'antd';

const ThemeContext = createContext();

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState('light'); // Keep your existing API

  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prevTheme => {
      const newTheme = prevTheme === 'light' ? 'dark' : 'light';
      document.body.setAttribute('data-theme', newTheme);
      return newTheme;
    });
  };

  // Ant Design theme configuration
  const antdThemeConfig = {
    algorithm: theme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: '#1677ff',
      borderRadius: 6,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    },
    components: {
      Button: {
        borderRadius: 6,
        fontWeight: 500,
      },
      Card: {
        borderRadius: 8,
      },
      Table: {
        borderRadius: 6,
      },
      Tag: {
        borderRadius: 6,
        fontWeight: 500,
      },
      Collapse: {
        borderRadius: 6,
      },
      Menu: {
        // Let Ant Design handle menu theming automatically
      },
      Layout: {
        // Let Ant Design handle layout theming automatically
      }
    },
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      <ConfigProvider theme={antdThemeConfig}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);