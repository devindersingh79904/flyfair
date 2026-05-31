import React from "react";
import type { SearchResult } from "../types/airportSearchTypes";

interface SelectedLocationCardProps {
  title: string;
  result: SearchResult | null;
}

export const SelectedLocationCard: React.FC<SelectedLocationCardProps> = ({
  title,
  result
}) => {
  if (!result) {
    return (
      <div className="selected-location-card card-empty">
        <span className="card-title-prefix">{title}</span>
        <p className="empty-text">No location selected. Use the search field above.</p>
      </div>
    );
  }

  const isGroup = result.type === "CITY_GROUP" || result.type === "REGION_GROUP";
  const showDebug = import.meta.env.VITE_SHOW_DEBUG_RANKING === "true";

  return (
    <div className="selected-location-card">
      <div className="card-header">
        <span className="card-title-prefix">{title}</span>
        <span className={`type-badge badge-${result.type.toLowerCase().replace("_", "-")}`}>
          {result.type.replace("_", " ")}
        </span>
      </div>
      
      {isGroup ? (
        <>
          <h3 className="location-name">{result.displayName} - All airports</h3>
          <p className="location-details">
            {result.country}
          </p>
          <div className="airports-section">
            <h4 className="section-title">Included airports:</h4>
            <ul className="airports-list">
              {result.airports.map((ap) => (
                <li key={ap.iata} className="airport-item">
                  <span className="iata-indicator">[{ap.iata}]</span>
                  <span className="airport-item-name">{ap.name}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : (
        <>
          <h3 className="location-name">{result.code || result.airports[0]?.iata} - {result.displayName}</h3>
          <p className="location-details">
            {result.city ? `${result.city}, ` : ""}
            {result.country}
          </p>
          <p className="location-details exact-text">Exact airport selected</p>
        </>
      )}

      {showDebug && (
        <div className="card-footer-debug">
          <span className="debug-label">Strategy: {result.matchReason}</span>
          <span className="debug-divider">|</span>
          <span className="debug-label">Score: {result.score}</span>
        </div>
      )}
    </div>
  );
};
