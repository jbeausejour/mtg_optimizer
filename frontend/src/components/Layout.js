import React, { useEffect } from 'react';
import { Layout as AntLayout } from 'antd';
import { useTheme } from '../utils/ThemeContext';

const { Header, Content, Footer } = AntLayout;

const Layout = ({ children }) => {
  const { theme } = useTheme();

  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header style={{ 
        padding: 0, 
        background: 'transparent',
        boxShadow: 'none',
        border: 'none'
      }}>
        {children[0]} {/* This will be the Navigation component */}
      </Header>
      <Content style={{ 
        padding: '0 50px', 
        minHeight: 'calc(100vh - 134px)',
        background: 'transparent'
      }}>
        {children.slice(1)} {/* This will be the Routes */}
      </Content>
      <Footer style={{ 
        textAlign: 'center',
        background: 'transparent',
        border: 'none'
      }}>
        MTG Card Optimizer ©{new Date().getFullYear()}
      </Footer>
    </AntLayout>
  );
};

export default Layout;