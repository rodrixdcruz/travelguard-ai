import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { JourneyProvider } from './context/JourneyContext'
import { TouristLocationProvider } from './context/LocationContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <TouristLocationProvider>
      <JourneyProvider>
        <App />
      </JourneyProvider>
    </TouristLocationProvider>
  </React.StrictMode>,
)
