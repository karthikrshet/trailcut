import '@razorpay/blade/fonts.css';
import './styles.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { ThemeRoot } from './theme';

const root = document.getElementById('root');
if (!root) throw new Error('#root element missing');

createRoot(root).render(
  <StrictMode>
    <ThemeRoot>
      <App />
    </ThemeRoot>
  </StrictMode>,
);
