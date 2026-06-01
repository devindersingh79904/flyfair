import React, { useState, useEffect, useRef, useCallback } from "react";
import type { SearchResult } from "../types/airportSearchTypes";
import { searchAirports } from "../api/airportSearchApi";
import { SearchResultDropdown } from "./SearchResultDropdown";
import { debounce } from "../utils/debounce";
import { DEBOUNCE_DELAY, MIN_QUERY_LENGTH } from "../constants/apiConstants";
import { UI_MESSAGES } from "../constants/uiConstants";

interface AirportSearchBoxProps {
  label: string;
  placeholder: string;
  onSelect: (result: SearchResult | null) => void;
  selectedResult: SearchResult | null;
}

export const AirportSearchBox: React.FC<AirportSearchBoxProps> = ({
  label,
  placeholder,
  onSelect,
  selectedResult
}) => {
  const [inputValue, setInputValue] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dropdownVisible, setDropdownVisible] = useState(false);
  const [translationInfo, setTranslationInfo] = useState<{
    fallbackUsed: boolean;
    originalQuery?: string;
    translatedQuery?: string;
  } | null>(null);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (selectedResult) {
      const isGroup = selectedResult.type === "CITY_GROUP" || selectedResult.type === "REGION_GROUP";
      const displayValue = isGroup 
        ? `${selectedResult.displayName} (All airports)`
        : `${selectedResult.code || selectedResult.airports[0]?.iata} - ${selectedResult.displayName}`;
      setInputValue(displayValue);
    } else {
      setInputValue("");
    }
  }, [selectedResult]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setDropdownVisible(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const performSearch = async (query: string) => {
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setLoading(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setLoading(true);
    setError(null);
    try {
      const correlationId = `web-${Math.random().toString(36).substring(2, 11)}`;
      const response = await searchAirports(trimmed, 10, correlationId, abortController.signal);
      if (response.status === "SUCCESS" && response.data) {
        setResults(response.data.results);
        setTranslationInfo({
          fallbackUsed: response.data.translationFallbackUsed || false,
          originalQuery: trimmed,
          translatedQuery: response.data.translatedQuery
        });
      } else {
        setResults([]);
        setTranslationInfo(null);
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        return;
      }
      setError(err.message || UI_MESSAGES.ERROR_STATE_MESSAGE);
      setResults([]);
    } finally {
      if (abortControllerRef.current === abortController) {
        setLoading(false);
      }
    }
  };

  const debouncedSearch = useCallback(
    debounce((q: string) => performSearch(q), DEBOUNCE_DELAY),
    []
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);
    
    if (selectedResult) {
      onSelect(null);
    }

    setTranslationInfo(null);
    setDropdownVisible(true);
    debouncedSearch(val);
  };

  const handleSelectResult = (result: SearchResult) => {
    onSelect(result);
    setDropdownVisible(false);
  };

  const handleInputFocus = () => {
    if (inputValue.trim().length >= MIN_QUERY_LENGTH) {
      setDropdownVisible(true);
    }
  };

  const handleClear = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setInputValue("");
    setResults([]);
    onSelect(null);
    setError(null);
    setDropdownVisible(false);
    setTranslationInfo(null);
  };

  const showEmptyState =
    !loading &&
    !error &&
    inputValue.trim().length >= MIN_QUERY_LENGTH &&
    results.length === 0 &&
    dropdownVisible;

  return (
    <div className="search-box-container" ref={containerRef}>
      <label className="search-box-label">{label}</label>
      <div className="input-wrapper">
        <input
          type="text"
          className="search-box-input"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          placeholder={placeholder}
        />
        {inputValue && (
          <button className="clear-btn" onClick={handleClear} type="button" aria-label="Clear input">
            &times;
          </button>
        )}
        {loading && <div className="spinner"></div>}
      </div>

      {error && <div className="search-box-error">{error}</div>}

      {showEmptyState && (
        <div className="search-box-empty">{UI_MESSAGES.EMPTY_STATE_MESSAGE}</div>
      )}

      <SearchResultDropdown
        results={results}
        onSelect={handleSelectResult}
        visible={dropdownVisible && !loading && !error}
        translationInfo={translationInfo}
      />
    </div>
  );
};
