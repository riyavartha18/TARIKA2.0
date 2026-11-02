"""Customer Lifetime Value (CLV) analysis module.

Reads the reusable per-buyer metrics persisted by the RFM analysis (lifetime
Monetary value + segment label) and derives everything else on demand from the
live `public.orders` history. Calculated CLV results are never persisted: the
dashboard always answers from the current source data plus the stored RFM
metrics, held in the short-lived snapshot cache exactly like an RFM run.
"""
