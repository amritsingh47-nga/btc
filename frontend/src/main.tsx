import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import { Shell } from './components/Shell'
import FuturesPage from './pages/Futures'
import StocksPage from './pages/Stocks'
import CryptoPage from './pages/Crypto'
import MacroPage from './pages/Macro'
import NewsPage from './pages/News'
import PortfolioPage from './pages/Portfolio'
import SettingsPage from './pages/Settings'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<Navigate to="/futures" replace />} />
          <Route path="/futures" element={<FuturesPage />} />
          <Route path="/stocks" element={<StocksPage />} />
          <Route path="/crypto" element={<CryptoPage />} />
          <Route path="/macro" element={<MacroPage />} />
          <Route path="/news" element={<NewsPage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/futures" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  </React.StrictMode>
)
