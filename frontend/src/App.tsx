import { useState } from "react";
import { AirportSearchBox } from "./components/AirportSearchBox";
import { SelectedLocationCard } from "./components/SelectedLocationCard";
import type { SearchResult } from "./types/airportSearchTypes";
import { UI_MESSAGES } from "./constants/uiConstants";

function App() {
  const [fromResult, setFromResult] = useState<SearchResult | null>(null);
  const [toResult, setToResult] = useState<SearchResult | null>(null);

  return (
    <div className="app-container">
      <header className="app-header">
        <h1 className="app-title">{UI_MESSAGES.APP_TITLE}</h1>
        <p className="app-subtitle">{UI_MESSAGES.APP_SUBTITLE}</p>
      </header>

      <main className="search-grid">
        <div className="search-card">
          <AirportSearchBox
            label={UI_MESSAGES.FROM_LABEL}
            placeholder="e.g. London, Bali, HNL, 東京"
            onSelect={setFromResult}
            selectedResult={fromResult}
          />
          <SelectedLocationCard
            title="Selected Origin"
            result={fromResult}
          />
        </div>

        <div className="search-card">
          <AirportSearchBox
            label={UI_MESSAGES.TO_LABEL}
            placeholder="e.g. Florida, Dubai, BLR, São Paulo"
            onSelect={setToResult}
            selectedResult={toResult}
          />
          <SelectedLocationCard
            title="Selected Destination"
            result={toResult}
          />
        </div>
      </main>

      <footer style={{ marginTop: "40px", color: "var(--text-muted)", fontSize: "0.85rem", textAlign: "center" }}>
        Fly Fairly Airport Search Demo Prototype &bull; Powered by Python FastAPI &amp; React TypeScript
      </footer>
    </div>
  );
}

export default App;
