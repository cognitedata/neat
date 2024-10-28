import logo from './logo.svg';
import './App.css';
import * as React from 'react';
import BasicTabs from './MainContainer.tsx';
import CssBaseline from '@mui/material/CssBaseline';

function App() {
  // window.addEventListener("contextmenu", e => e.preventDefault());
  return (
    <div >
      <BasicTabs/>
    </div>

  );
}

export default App;
