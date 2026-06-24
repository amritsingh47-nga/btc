"""Amazon SMF1/SMF6 hourly-job detector.

Polls hiring.amazon.com for warehouse/fulfillment job postings, matches them
against your criteria (building/site code, title, pay), and sends an instant
alert the moment a match appears. Designed so an auto-apply step can be added
later without touching the detection/alerting core.
"""

__version__ = "0.1.0"
