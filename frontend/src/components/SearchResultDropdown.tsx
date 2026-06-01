import React from "react";
import type { SearchResult, AirportSummary } from "../types/airportSearchTypes";

interface SearchResultDropdownProps {
  results: SearchResult[];
  onSelect: (result: SearchResult) => void;
  visible: boolean;
  translationInfo?: {
    fallbackUsed: boolean;
    originalQuery?: string;
    translatedQuery?: string;
  } | null;
}

export const SearchResultDropdown: React.FC<SearchResultDropdownProps> = ({
  results,
  onSelect,
  visible,
  translationInfo
}) => {
  if (!visible || results.length === 0) return null;

  const showDebug = import.meta.env.VITE_SHOW_DEBUG_RANKING === "true";

  const handleChildSelect = (e: React.MouseEvent, parentResult: SearchResult, ap: AirportSummary) => {
    e.stopPropagation();
    
    const childResult: SearchResult = {
      id: ap.id || `airport:${ap.iata}`,
      type: "AIRPORT",
      code: ap.iata,
      displayName: ap.name,
      city: ap.city,
      region: ap.region,
      country: ap.country,
      countryCode: ap.countryCode,
      score: parentResult.score,
      matchReason: parentResult.matchReason,
      airports: [ap]
    };
    onSelect(childResult);
  };

  const renderDebug = (result: SearchResult) => {
    if (!showDebug) return null;
    return (
      <div className="search-result-debug">
        <span className="debug-badge match-reason" title="Match Strategy">
          {result.matchReason}
        </span>
        <span className="debug-badge match-score" title="Deterministic Match Score">
          Score: {result.score}
        </span>
      </div>
    );
  };

  const renderedGroupChildIatas = new Set<string>();
  results.forEach(r => {
    if (r.type === "CITY_GROUP" || r.type === "REGION_GROUP") {
      r.airports.forEach(a => {
        if (a.iata) renderedGroupChildIatas.add(a.iata.toUpperCase());
      });
    }
  });

  return (
    <ul className="search-result-dropdown">
      {showDebug && translationInfo?.fallbackUsed && (
        <li className="search-result-row debug-translation-banner" style={{ padding: "8px 16px", background: "#f0f4f9", borderBottom: "1px solid #e0e0e0", fontSize: "12px", color: "#5f6368" }}>
          <div>
            <strong>Translated Fallback:</strong> {translationInfo.originalQuery} → {translationInfo.translatedQuery}
          </div>
        </li>
      )}
      {results.map((result) => {
        if (result.type === "CITY_GROUP" || result.type === "REGION_GROUP") {
          const isCity = result.type === "CITY_GROUP";
          return (
            <React.Fragment key={result.id}>
              <li className="search-result-row parent-group-row" onClick={() => onSelect(result)}>
                <div className="search-result-left">
                  <div className="search-result-header">
                    {result.code && <span className="group-code-badge">[ {result.code} ]</span>}
                    <span className="search-result-name">{result.displayName}, {result.country}</span>
                  </div>
                  <span className="search-result-sub">
                    {isCity ? `${result.displayName} all airports` : "Region airports"}
                  </span>
                  {renderDebug(result)}
                </div>
                <div className="search-result-right">
                  <span className={`type-badge badge-${result.type.toLowerCase().replace("_", "-")}`}>
                    {isCity ? "CITY GROUP" : "REGION GROUP"}
                  </span>
                </div>
              </li>
              
              {result.airports.map((ap) => (
                <li
                  key={ap.iata}
                  className="search-result-row child-airport-row"
                  onClick={(e) => handleChildSelect(e, result, ap)}
                >
                  <div className="indentation-guide">↳</div>
                  <div className="search-result-left">
                    <div className="search-result-header">
                      <span className="iata-code-badge">[ {ap.iata} ]</span>
                      <span className="search-result-name">{ap.name}</span>
                    </div>
                    <span className="search-result-sub">
                      {ap.city ? `${ap.city}, ${ap.country}` : "Included airport"}
                    </span>
                  </div>
                </li>
              ))}
            </React.Fragment>
          );
        }

        const iata = (result.airports[0]?.iata || result.code || "").toUpperCase();
        if (result.type === "AIRPORT" && iata && renderedGroupChildIatas.has(iata)) {
          return null;
        }

        return (
          <li key={result.id} className="search-result-row" onClick={() => onSelect(result)}>
            <div className="search-result-left">
              <div className="search-result-header">
                <span className="iata-code-badge">[ {result.airports[0]?.iata || result.code} ]</span>
                <span className="search-result-name">{result.displayName}</span>
              </div>
              <span className="search-result-sub">
                {result.city ? `${result.city}, ` : ""}
                {result.region ? `${result.region}, ` : ""}
                {result.country}
              </span>
              {renderDebug(result)}
            </div>
            <div className="search-result-right">
              <span className="type-badge badge-airport">AIRPORT</span>
            </div>
          </li>
        );
      })}
    </ul>
  );
};
