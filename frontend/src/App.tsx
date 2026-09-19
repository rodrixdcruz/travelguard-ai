import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import Dashboard from './pages/Dashboard'
import PlanJourney from './pages/PlanJourney'
import NearMe from './components/NearMe'
import { DayPlanner, FoodNearYou, LocalSafetyPage } from './pages/Discovery'
import { Alerts, History, AiAssistant, Settings } from './pages/Placeholders'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/near-me" element={<NearMe />} />
          <Route path="/plan-day" element={<DayPlanner />} />
          <Route path="/food" element={<FoodNearYou />} />
          <Route path="/safety" element={<LocalSafetyPage />} />
          <Route path="/plan" element={<PlanJourney />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/history" element={<History />} />
          <Route path="/assistant" element={<AiAssistant />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
