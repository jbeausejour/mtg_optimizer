import React from 'react';
import ErrorBoundary from './utils/ErrorBoundary';
import ReactDOM from 'react-dom/client';
import App from './App';
import './global.css';
import { ThemeProvider } from './utils/ThemeContext';

const root = ReactDOM.createRoot(document.getElementById('root'));

root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
