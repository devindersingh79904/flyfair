import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.index_builder import IndexBuilder
from app.services.airport_search_service import AirportSearchService
idx = IndexBuilder("app/data")
svc = AirportSearchService(idx)
res, lat = svc.search("UK", 20)
for r in res.results:
    if r.id == 'airport:UKB':
        print(r.id, r.score, r.matchReason.value)
