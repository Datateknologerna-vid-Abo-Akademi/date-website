"""
Central place for view-cache keys/timeouts so signals can invalidate them.
"""

SHORT_VIEW_CACHE_TIMEOUT = 30

DATE_INDEX_CACHE_KEY = "viewcache:date:index"
EVENTS_INDEX_CACHE_KEY = "viewcache:events:index"
