from enum import Enum

class ResultType(str, Enum):
    AIRPORT = "AIRPORT"
    CITY_GROUP = "CITY_GROUP"
    REGION_GROUP = "REGION_GROUP"

class MatchReason(str, Enum):
    IATA_EXACT = "IATA_EXACT"
    ALIAS_EXACT = "ALIAS_EXACT"
    CITY_CODE_EXACT = "CITY_CODE_EXACT"
    CITY_GROUP_EXACT = "CITY_GROUP_EXACT"
    REGION_EXACT = "REGION_EXACT"
    IATA_PREFIX = "IATA_PREFIX"
    ALIAS_PREFIX = "ALIAS_PREFIX"
    CITY_PREFIX = "CITY_PREFIX"
    AIRPORT_NAME_PREFIX = "AIRPORT_NAME_PREFIX"
    AIRPORT_TOKEN_MATCH = "AIRPORT_TOKEN_MATCH"
    AIRPORT_NAME_EXACT = "AIRPORT_NAME_EXACT"
    CITY_EXACT = "CITY_EXACT"
    COUNTRY_EXACT = "COUNTRY_EXACT"
    COUNTRY_PREFIX = "COUNTRY_PREFIX"
    COUNTRY_ALIAS = "COUNTRY_ALIAS"
    COUNTRY_TOKEN_MATCH = "COUNTRY_TOKEN_MATCH"
    SUBSTRING_MATCH = "SUBSTRING_MATCH"
    SUBSEQUENCE_MATCH = "SUBSEQUENCE_MATCH"
    FUZZY_CITY = "FUZZY_CITY"
    FUZZY_AIRPORT = "FUZZY_AIRPORT"

class ResponseStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"

class Headers(str, Enum):
    CORRELATION_ID = "X-Correlation-ID"

class SearchBounds:
    MIN_LIMIT = 1
    MAX_LIMIT = 20
    DEFAULT_LIMIT = 10

PROTECTED_CITY_CODES = {"LON", "TYO", "SEL", "NYC", "PAR", "ROM"}
IATA_NATURAL_PENALTY = 150

BASE_SCORES = {
    MatchReason.IATA_EXACT: 1000,
    MatchReason.ALIAS_EXACT: 980,
    MatchReason.CITY_CODE_EXACT: 950,
    MatchReason.CITY_GROUP_EXACT: 930,
    MatchReason.REGION_EXACT: 900,
    MatchReason.COUNTRY_EXACT: 870,
    MatchReason.COUNTRY_ALIAS: 860,
    MatchReason.IATA_PREFIX: 850,
    MatchReason.ALIAS_PREFIX: 840,
    MatchReason.COUNTRY_PREFIX: 830,
    MatchReason.CITY_PREFIX: 820,
    MatchReason.AIRPORT_NAME_PREFIX: 780,
    MatchReason.COUNTRY_TOKEN_MATCH: 760,
    MatchReason.AIRPORT_TOKEN_MATCH: 720,
    MatchReason.AIRPORT_NAME_EXACT: 700,
    MatchReason.SUBSTRING_MATCH: 690,
    MatchReason.CITY_EXACT: 680,
    MatchReason.SUBSEQUENCE_MATCH: 650,
    MatchReason.FUZZY_CITY: 500,
    MatchReason.FUZZY_AIRPORT: 450,
}

class LogEvent(str, Enum):
    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    SEARCH_STARTED = "airport_search_started"
    SEARCH_COMPLETED = "airport_search_completed"
    DATA_LOAD_SUCCESS = "data_load_success"
    DATA_LOAD_FAILURE = "data_load_failure"
    UNHANDLED_EXCEPTION = "unhandled_exception"
    VALIDATION_ERROR = "validation_error"

TRANSLATION_PROVIDER_GOOGLE = "google"

