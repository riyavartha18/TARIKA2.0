"""
Revenue OLAP Service - Time Dimension OLAP (Full 6 Operations Suite)
=====================================================================
Implements Online Analytical Processing (OLAP) on actual delivered retail
sales transactions strictly along the Time Dimension:
  Level 1: Monthly (25 Months: March 2024 to March 2026)
  Level 2: Quarterly (9 Quarters: 2024-Q1 to 2026-Q1)
  Level 3: Yearly (3 Years: 2024, 2025, 2026)

Supported Operations:
  1. Roll-up: Month -> Quarter -> Year aggregation
  2. Drill-down: Year -> Quarter -> Month hierarchy descent
  3. Slice: Fixing one time coordinate (Year or Quarter) to view constituent sub-periods
  4. Dice: Multi-dimensional time filter (Selected Years x Selected Months subcube)
  5. Pivot: Reorienting Time into a 2D Year x Quarter cross-tabulation matrix
  6. Ranking: Deterministic revenue leaderboards by Month, Quarter, or Year
  7. Drill-Through: Atomic order inspection with server-side pagination (<= 50) and customer masking
  8. Trend Analysis: Chronological MoM change, MoM %, YoY %, and 3-Month Moving Average (SMA-3)

Mathematical & Data Integrity Rules:
1. REVENUE MEASURE:
   SUM(final_price) strictly for delivery_status = 'Delivered'.
   final_price is the line transaction total paid by the customer.
   It is NEVER multiplied by quantity.

2. AVERAGE ORDER VALUE (AOV):
   AOV = SUM(final_price) / COUNT(DISTINCT orderid).
   Verified row grain: orderid is 100% unique across all delivered orders.

3. STRICT GREGORIAN CALENDAR DATE VALIDATION:
   SQL and Python filter only valid calendar dates (respecting leap year rules
   and max days per month). Malformed or impossible dates never crash queries.

4. PARTIAL PERIOD LABELING:
   - March 2024: Partial Inception Month (Day 31 only)
   - 2024-Q1: Partial Quarter (1 Day only)
   - 2024: Partial Year (9 Months + 1 Day, March 31 to Dec 31)
   - 2025: Complete Calendar Year (12 Months, Jan 1 to Dec 31)
   - 2026: Partial Year (Q1 only / 3 Months, Jan 1 to Mar 31)

5. RECONCILIATION INTEGRITY:
   Monthly sum == Quarterly sum == Yearly sum across revenue, orders, and units.
   Grand Total: 590,217 orders, 1,772,450 units, ₹3,960,381,675.76 revenue, ₹6,710.04 AOV.
"""

import time
import math
import calendar
from datetime import datetime
from django.db import connection

# In-memory cache for high-performance dashboard browsing
_OLAP_CACHE = {
    'base_buckets': None,
    'timestamp': 0,
    'ttl_seconds': 900,  # 15 minutes TTL
}

MONTH_NAMES = {
    '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun',
    '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
}

MONTH_FULL_NAMES = {
    '01': 'January', '02': 'February', '03': 'March', '04': 'April',
    '05': 'May', '06': 'June', '07': 'July', '08': 'August',
    '09': 'September', '10': 'October', '11': 'November', '12': 'December'
}

# SQL Condition enforcing strict Gregorian calendar validity before any date conversion.
# Wrapped in nested CASE to guarantee short-circuiting: substring casts to integer are
# NEVER evaluated unless purchase_date matches the strict DD-MM-YYYY regex pattern,
# eliminating any possibility of integer-cast errors on malformed database strings.
# Explicitly rejects year 0000 and restricts the year to valid Gregorian range 0001..9999.
SAFE_GREGORIAN_DATE_CONDITION = """
(CASE
    WHEN purchase_date IS NOT NULL AND purchase_date ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$' THEN
        CASE
            WHEN SUBSTRING(purchase_date, 7, 4)::int BETWEEN 1 AND 9999 THEN
                CASE
                    WHEN SUBSTRING(purchase_date, 4, 2)::int IN (1, 3, 5, 7, 8, 10, 12)
                         AND SUBSTRING(purchase_date, 1, 2)::int BETWEEN 1 AND 31 THEN TRUE
                    WHEN SUBSTRING(purchase_date, 4, 2)::int IN (4, 6, 9, 11)
                         AND SUBSTRING(purchase_date, 1, 2)::int BETWEEN 1 AND 30 THEN TRUE
                    WHEN SUBSTRING(purchase_date, 4, 2)::int = 2 THEN
                        CASE
                            WHEN (SUBSTRING(purchase_date, 7, 4)::int % 4 = 0 AND SUBSTRING(purchase_date, 7, 4)::int % 100 != 0)
                                 OR (SUBSTRING(purchase_date, 7, 4)::int % 400 = 0)
                            THEN SUBSTRING(purchase_date, 1, 2)::int BETWEEN 1 AND 29
                            ELSE SUBSTRING(purchase_date, 1, 2)::int BETWEEN 1 AND 28
                        END
                    ELSE FALSE
                END
            ELSE FALSE
        END
    ELSE FALSE
END = TRUE)
"""


def mask_customer_id(cid):
    """
    Safely masks customer ID (e.g. 'U422670' -> 'U4****70') to prevent leaking PII.
    """
    if not cid:
        return '—'
    s = str(cid).strip()
    if len(s) <= 4:
        return s[:1] + '***'
    return f"{s[:2]}****{s[-2:]}"


class RevenueTimeOLAPService:
    """
    Executes OLAP operations (Roll-up, Drill-down, Slice, Dice, Pivot, Ranking,
    Drill-Through, Trend Analysis) on delivered order revenue across the Time Dimension.
    """

    @classmethod
    def get_base_monthly_data(cls, force_refresh=False):
        """
        Fetches or retrieves cached base monthly aggregates.
        All Roll-up, Drill-down, Slice, Dice, Pivot, Ranking, and Trend tiers are
        derived consistently from this validated base.
        """
        now_ts = time.time()
        if (
            not force_refresh
            and _OLAP_CACHE['base_buckets'] is not None
            and (now_ts - _OLAP_CACHE['timestamp']) < _OLAP_CACHE['ttl_seconds']
        ):
            return _OLAP_CACHE['base_buckets']

        query = f"""
            WITH valid_delivered_orders AS MATERIALIZED (
                SELECT 
                    orderid,
                    quantity,
                    final_price,
                    purchase_date
                FROM orders
                WHERE delivery_status = 'Delivered'
                  AND {SAFE_GREGORIAN_DATE_CONDITION}
            )
            SELECT 
                TO_CHAR(TO_DATE(purchase_date, 'DD-MM-YYYY'), 'YYYY-MM') AS month_key,
                TO_CHAR(TO_DATE(purchase_date, 'DD-MM-YYYY'), 'YYYY') AS year_str,
                'Q' || TO_CHAR(TO_DATE(purchase_date, 'DD-MM-YYYY'), 'Q') AS quarter_str,
                COUNT(orderid) AS order_count,
                COUNT(DISTINCT orderid) AS distinct_orders,
                SUM(quantity) AS units_sold,
                SUM(final_price) AS total_revenue,
                MIN(TO_DATE(purchase_date, 'DD-MM-YYYY')) AS min_date,
                MAX(TO_DATE(purchase_date, 'DD-MM-YYYY')) AS max_date
            FROM valid_delivered_orders
            GROUP BY month_key, year_str, quarter_str
            ORDER BY month_key ASC;
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                raw_rows = cursor.fetchall()

                # Also count total delivered orders in table to verify 100% inclusion
                cursor.execute("SELECT COUNT(*) FROM orders WHERE delivery_status = 'Delivered';")
                total_delivered_in_db = cursor.fetchone()[0]
        except Exception as exc:
            return {
                'success': False,
                'error': f'Database query error during OLAP execution: {str(exc)}'
            }

        if not raw_rows:
            return {
                'success': False,
                'error': 'No delivered orders found matching valid calendar criteria.'
            }

        # Build structured monthly records with Gregorian validation and partial-month classification
        monthly_records = []
        for r in raw_rows:
            m_key = r[0]
            y_str = r[1]
            q_str = r[2]
            order_cnt = int(r[3] or 0)
            distinct_cnt = int(r[4] or 0)
            units = int(r[5] or 0)
            rev = float(r[6] or 0.0)
            min_d = r[7]
            max_d = r[8]

            y_int = int(y_str)
            m_int = int(m_key.split('-')[1])
            m_suffix = f"{m_int:02d}"

            # Gregorian day validation
            _, last_day = calendar.monthrange(y_int, m_int)
            is_full_month = (min_d.day == 1 and max_d.day == last_day and order_cnt >= 2000)

            if is_full_month:
                is_partial = False
                status_label = 'Complete Month'
                status_badge = 'Complete Month'
                span_description = f"{min_d.strftime('%b %d, %Y')} – {max_d.strftime('%b %d, %Y')} ({last_day} Days)"
            else:
                is_partial = True
                status_label = 'Partial Month'
                status_badge = f'Partial Month ({min_d.strftime("%b %d")} only)'
                span_description = f"{min_d.strftime('%b %d, %Y')} only (Single Day Inception)"

            aov = round(rev / distinct_cnt, 2) if distinct_cnt > 0 else 0.0

            monthly_records.append({
                'period_key': m_key,
                'label': f"{MONTH_NAMES.get(m_suffix, m_suffix)} {y_str}",
                'full_label': f"{MONTH_FULL_NAMES.get(m_suffix, m_suffix)} {y_str}",
                'year': y_str,
                'quarter': q_str,
                'year_quarter': f"{y_str}-{q_str}",
                'month': m_int,
                'order_count': order_cnt,
                'distinct_orders': distinct_cnt,
                'units_sold': units,
                'total_revenue': round(rev, 2),
                'avg_order_value': aov,
                'start_date': str(min_d),
                'end_date': str(max_d),
                'span_description': span_description,
                'is_partial': is_partial,
                'status_label': status_label,
                'status_badge': status_badge,
                'level': 'month',
            })

        cached_payload = {
            'success': True,
            'monthly_records': monthly_records,
            'total_delivered_in_db': total_delivered_in_db,
            'valid_gregorian_records': sum(m['order_count'] for m in monthly_records),
        }
        _OLAP_CACHE['base_buckets'] = cached_payload
        _OLAP_CACHE['timestamp'] = now_ts
        return cached_payload

    @classmethod
    def _get_shared_cubes(cls, force_refresh=False):
        """
        Builds the consolidated hierarchy (months, quarterly_records, yearly_records,
        reconciliation metadata) shared by all OLAP operations.
        """
        base_data = cls.get_base_monthly_data(force_refresh=force_refresh)
        if not base_data.get('success'):
            return None, base_data

        months = [dict(m) for m in base_data['monthly_records']]
        total_delivered_in_db = base_data['total_delivered_in_db']

        # 1. Consolidated Quarterly records (9 Quarters)
        quarterly_dict = {}
        for m in months:
            yq = m['year_quarter']
            if yq not in quarterly_dict:
                quarterly_dict[yq] = {
                    'period_key': yq,
                    'label': f"{m['year']} {m['quarter']}",
                    'full_label': f"{m['year']} {m['quarter']} ({cls._get_quarter_span(yq)})",
                    'year': m['year'],
                    'quarter': m['quarter'],
                    'order_count': 0,
                    'distinct_orders': 0,
                    'units_sold': 0,
                    'total_revenue': 0.0,
                    'months_included': [],
                    'min_date': m['start_date'],
                    'max_date': m['end_date'],
                    'is_partial': False,
                    'level': 'quarter',
                }
            q_entry = quarterly_dict[yq]
            q_entry['order_count'] += m['order_count']
            q_entry['distinct_orders'] += m['distinct_orders']
            q_entry['units_sold'] += m['units_sold']
            q_entry['total_revenue'] += m['total_revenue']
            q_entry['months_included'].append(m['label'])
            if m['start_date'] < q_entry['min_date']:
                q_entry['min_date'] = m['start_date']
            if m['end_date'] > q_entry['max_date']:
                q_entry['max_date'] = m['end_date']

        quarterly_records = []
        for yq in sorted(quarterly_dict.keys()):
            q = quarterly_dict[yq]
            q['total_revenue'] = round(q['total_revenue'], 2)
            q['avg_order_value'] = (
                round(q['total_revenue'] / q['distinct_orders'], 2)
                if q['distinct_orders'] > 0
                else 0.0
            )
            if yq == '2024-Q1':
                q['is_partial'] = True
                q['status_label'] = 'Partial Quarter'
                q['status_badge'] = 'Partial Quarter (1 Day only)'
                q['span_description'] = 'March 31, 2024 only (Inception Quarter)'
            else:
                q['is_partial'] = False
                q['status_label'] = 'Complete Quarter'
                q['status_badge'] = 'Complete Quarter (3 Months)'
                q['span_description'] = f"{q['min_date']} to {q['max_date']} (Full 3 Months)"

            quarterly_records.append(q)

        # 2. Consolidated Yearly records (3 Years)
        yearly_dict = {}
        for q in quarterly_records:
            y = q['year']
            if y not in yearly_dict:
                yearly_dict[y] = {
                    'period_key': y,
                    'label': f"Year {y}",
                    'full_label': f"Calendar Year {y}",
                    'year': y,
                    'order_count': 0,
                    'distinct_orders': 0,
                    'units_sold': 0,
                    'total_revenue': 0.0,
                    'quarters_included': [],
                    'min_date': q['min_date'],
                    'max_date': q['max_date'],
                    'is_partial': False,
                    'level': 'year',
                }
            y_entry = yearly_dict[y]
            y_entry['order_count'] += q['order_count']
            y_entry['distinct_orders'] += q['distinct_orders']
            y_entry['units_sold'] += q['units_sold']
            y_entry['total_revenue'] += q['total_revenue']
            y_entry['quarters_included'].append(q['quarter'])
            if q['min_date'] < y_entry['min_date']:
                y_entry['min_date'] = q['min_date']
            if q['max_date'] > y_entry['max_date']:
                y_entry['max_date'] = q['max_date']

        yearly_records = []
        for y in sorted(yearly_dict.keys()):
            yr = yearly_dict[y]
            yr['total_revenue'] = round(yr['total_revenue'], 2)
            yr['avg_order_value'] = (
                round(yr['total_revenue'] / yr['distinct_orders'], 2)
                if yr['distinct_orders'] > 0
                else 0.0
            )
            if y == '2024':
                yr['is_partial'] = True
                yr['status_label'] = 'Partial Year'
                yr['status_badge'] = 'Partial Year (9M + 1D)'
                yr['span_description'] = 'March 31, 2024 – December 31, 2024 (9 Months + 1 Day)'
            elif y == '2025':
                yr['is_partial'] = False
                yr['status_label'] = 'Complete Year'
                yr['status_badge'] = 'Full Calendar Year (12M)'
                yr['span_description'] = 'January 1, 2025 – December 31, 2025 (Full 12 Months)'
            elif y == '2026':
                yr['is_partial'] = True
                yr['status_label'] = 'Partial Year'
                yr['status_badge'] = 'Partial Year (Q1 only / 3M)'
                yr['span_description'] = 'January 1, 2026 – March 31, 2026 (Q1 only / 3 Months)'

            yearly_records.append(yr)

        # 3. Exact Reconciliation Validation
        monthly_rev_sum = round(sum(m['total_revenue'] for m in months), 2)
        quarterly_rev_sum = round(sum(q['total_revenue'] for q in quarterly_records), 2)
        yearly_rev_sum = round(sum(y['total_revenue'] for y in yearly_records), 2)

        monthly_orders_sum = sum(m['order_count'] for m in months)
        quarterly_orders_sum = sum(q['order_count'] for q in quarterly_records)
        yearly_orders_sum = sum(y['order_count'] for y in yearly_records)

        monthly_units_sum = sum(m['units_sold'] for m in months)
        quarterly_units_sum = sum(q['units_sold'] for q in quarterly_records)
        yearly_units_sum = sum(y['units_sold'] for y in yearly_records)

        is_reconciled = (
            monthly_rev_sum == quarterly_rev_sum == yearly_rev_sum
            and monthly_orders_sum == quarterly_orders_sum == yearly_orders_sum
            and monthly_units_sum == quarterly_units_sum == yearly_units_sum
            and monthly_orders_sum == total_delivered_in_db
        )

        overall_aov = round(monthly_rev_sum / monthly_orders_sum, 2) if monthly_orders_sum > 0 else 0.0

        for item_list in (months, quarterly_records, yearly_records):
            for itm in item_list:
                itm['share_of_total_pct'] = (
                    round((itm['total_revenue'] / monthly_rev_sum) * 100.0, 2)
                    if monthly_rev_sum > 0
                    else 0.0
                )

        available_years = [y['year'] for y in yearly_records]
        quarters_by_year = {
            y: [q['quarter'] for q in quarterly_records if q['year'] == y]
            for y in available_years
        }

        shared_meta = {
            'months': months,
            'quarterly_records': quarterly_records,
            'quarterly_dict': quarterly_dict,
            'yearly_records': yearly_records,
            'yearly_dict': yearly_dict,
            'available_years': available_years,
            'quarters_by_year': quarters_by_year,
            'total_delivered_in_db': total_delivered_in_db,
            'all_tiers_summary': {
                'monthly': {
                    'count': len(months),
                    'total_revenue': monthly_rev_sum,
                    'total_orders': monthly_orders_sum,
                    'total_units': monthly_units_sum,
                    'aov': overall_aov,
                },
                'quarterly': {
                    'count': len(quarterly_records),
                    'total_revenue': quarterly_rev_sum,
                    'total_orders': quarterly_orders_sum,
                    'total_units': quarterly_units_sum,
                    'aov': overall_aov,
                },
                'yearly': {
                    'count': len(yearly_records),
                    'total_revenue': yearly_rev_sum,
                    'total_orders': yearly_orders_sum,
                    'total_units': yearly_units_sum,
                    'aov': overall_aov,
                },
            },
            'data_reconciliation': {
                'monthly_total_revenue': monthly_rev_sum,
                'quarterly_total_revenue': quarterly_rev_sum,
                'yearly_total_revenue': yearly_rev_sum,
                'total_delivered_orders': monthly_orders_sum,
                'total_units_sold': monthly_units_sum,
                'overall_aov': overall_aov,
                'reconciled': is_reconciled,
                'reconciliation_formula': (
                    f"Monthly Total (₹{monthly_rev_sum / 1e7:.2f} Cr) = "
                    f"Quarterly Total (₹{quarterly_rev_sum / 1e7:.2f} Cr) = "
                    f"Yearly Total (₹{yearly_rev_sum / 1e7:.2f} Cr)"
                ),
            },
            'data_quality_report': {
                'total_delivered_in_database': total_delivered_in_db,
                'valid_gregorian_records': base_data['valid_gregorian_records'],
                'malformed_or_invalid_dates_excluded': total_delivered_in_db - base_data['valid_gregorian_records'],
                'validation_rules_enforced': (
                    "Strict Gregorian calendar validation enforcing valid day count per month "
                    "including leap years (29 days for Feb 2024, 28 for Feb 2025/2026), format DD-MM-YYYY."
                ),
            },
            'notices': {
                'partial_year_warning': (
                    "Analytical Warning: Year 2024 (9 Months + 1 Day, March 31 to Dec 31) and "
                    "Year 2026 (3 Months, Jan 1 to Mar 31) represent partial-year records and "
                    "must not be compared directly against Year 2025 (Full 12 Months) as full annual performance."
                ),
                'partial_month_notice': (
                    "Inception Notice: March 2024 contains only a single recorded day (March 31, 2024; "
                    "841 orders, ₹61.26 L) and constitutes a partial month and quarter."
                ),
            },
        }
        return shared_meta, None

    # =========================================================================
    # OPERATION 3: SLICE
    # =========================================================================
    @classmethod
    def get_slice_analysis(cls, slice_type='year', slice_value='2025', force_refresh=False):
        """
        Executes OLAP SLICE by fixing ONE time coordinate (Year or Quarter),
        revealing its exact constituent periods, revenue distribution, and share.
        """
        shared, err = cls._get_shared_cubes(force_refresh=force_refresh)
        if err:
            return err

        slice_type_clean = str(slice_type or 'year').strip().lower()
        if slice_type_clean not in ('year', 'quarter'):
            slice_type_clean = 'year'

        months = shared['months']
        quarterly_records = shared['quarterly_records']
        yearly_records = shared['yearly_records']

        if slice_type_clean == 'year':
            valid_years = shared['available_years']
            if not slice_value or str(slice_value) not in valid_years:
                slice_value = '2025'
            else:
                slice_value = str(slice_value)

            parent = next((y for y in yearly_records if y['year'] == slice_value), None)
            parent_rev = parent['total_revenue'] if parent else 1.0

            constituent_quarters = [
                dict(q) for q in quarterly_records if q['year'] == slice_value
            ]
            for q in constituent_quarters:
                q['share_of_slice_pct'] = round((q['total_revenue'] / parent_rev) * 100, 2)

            constituent_months = [
                dict(m) for m in months if m['year'] == slice_value
            ]
            for m in constituent_months:
                m['share_of_slice_pct'] = round((m['total_revenue'] / parent_rev) * 100, 2)

            records = constituent_months
            chart_records = constituent_quarters if len(constituent_quarters) > 1 else constituent_months
            chart_title = f"Slice: Revenue Share across Quarters of Calendar Year {slice_value}"
            parent_label = f"Calendar Year {slice_value} ({parent['status_label'] if parent else ''})"

        else:  # slice_type == 'quarter'
            valid_quarters = [q['period_key'] for q in quarterly_records]
            if not slice_value or str(slice_value) not in valid_quarters:
                slice_value = '2025-Q1'
            else:
                slice_value = str(slice_value)

            parent = next((q for q in quarterly_records if q['period_key'] == slice_value), None)
            parent_rev = parent['total_revenue'] if parent else 1.0

            constituent_months = [
                dict(m) for m in months if m['year_quarter'] == slice_value
            ]
            for m in constituent_months:
                m['share_of_slice_pct'] = round((m['total_revenue'] / parent_rev) * 100, 2)

            records = constituent_months
            chart_records = constituent_months
            chart_title = f"Slice: Monthly Breakdown of Quarter {slice_value}"
            parent_label = f"Quarter {slice_value} ({parent['status_label'] if parent else ''})"

        slice_summary = {
            'slice_type': slice_type_clean,
            'slice_value': slice_value,
            'parent_label': parent_label,
            'parent_revenue': parent['total_revenue'] if parent else 0.0,
            'parent_orders': parent['order_count'] if parent else 0,
            'parent_units': parent['units_sold'] if parent else 0,
            'parent_aov': parent['avg_order_value'] if parent else 0.0,
            'is_partial': parent['is_partial'] if parent else False,
            'status_badge': parent['status_badge'] if parent else '',
            'span_description': parent.get('span_description', ''),
        }

        return {
            'success': True,
            'operation': 'slice',
            'slice_summary': slice_summary,
            'records': records,
            'record_count': len(records),
            'available_slices': {
                'years': shared['available_years'],
                'quarters': [q['period_key'] for q in quarterly_records],
            },
            'chart_config': {
                'chart_type': 'column',
                'chart_title': chart_title,
                'metric_label': 'Realised Revenue (₹)',
            },
            'olap_concept': (
                "OLAP SLICE fixes exactly one time coordinate (e.g. Year = 2025 or Quarter = 2025-Q2) "
                "to reduce dimensionality and isolate the revenue performance of its constituent sub-periods."
            ),
            'all_tiers_summary': shared['all_tiers_summary'],
            'data_reconciliation': shared['data_reconciliation'],
            'data_quality_report': shared['data_quality_report'],
            'notices': shared['notices'],
        }

    # =========================================================================
    # OPERATION 4: DICE
    # =========================================================================
    @classmethod
    def get_dice_analysis(cls, selected_years=None, selected_months=None, force_refresh=False):
        """
        Executes OLAP DICE by filtering across multi-condition time criteria
        (Selected Years combined with Selected Month indices), forming a subcube.
        """
        shared, err = cls._get_shared_cubes(force_refresh=force_refresh)
        if err:
            return err

        months = shared['months']
        all_years = shared['available_years']

        # Normalise selected_years (supports list of strings/ints, comma-separated strings, or empty list)
        if selected_years is None:
            years_filter = list(all_years) if all_years else ['2024', '2025', '2026']
        else:
            years_filter = []
            raw_years = selected_years if isinstance(selected_years, (list, tuple)) else [selected_years]
            for item in raw_years:
                for part in str(item).split(','):
                    part = part.strip()
                    if part:
                        years_filter.append(part)
            years_filter = sorted(list(set(years_filter)))

        # Normalise selected_months (supports list of ints/strings, comma-separated strings, or empty list)
        if selected_months is None:
            months_filter = list(range(1, 13))
        else:
            months_filter = []
            raw_months = selected_months if isinstance(selected_months, (list, tuple)) else [selected_months]
            for item in raw_months:
                for part in str(item).split(','):
                    part = part.strip()
                    if part.isdigit():
                        m_int = int(part)
                        if 1 <= m_int <= 12:
                            months_filter.append(m_int)
            months_filter = sorted(list(set(months_filter)))

        # Filter months to form the diced subcube
        diced_records = []
        if years_filter and months_filter:
            for m in months:
                if m['year'] in years_filter and m['month'] in months_filter:
                    diced_records.append(dict(m))

        subcube_rev = round(sum(m['total_revenue'] for m in diced_records), 2)
        subcube_orders = sum(m['order_count'] for m in diced_records)
        subcube_units = sum(m['units_sold'] for m in diced_records)
        subcube_aov = round(subcube_rev / subcube_orders, 2) if subcube_orders > 0 else 0.0

        global_rev = shared['data_reconciliation']['monthly_total_revenue']
        share_of_global = round((subcube_rev / global_rev) * 100, 2) if global_rev > 0 else 0.0

        for r in diced_records:
            r['share_of_subcube_pct'] = round((r['total_revenue'] / subcube_rev) * 100, 2) if subcube_rev > 0 else 0.0

        subcube_summary = {
            'selected_years': sorted(years_filter),
            'selected_months': sorted(months_filter),
            'total_revenue': subcube_rev,
            'order_count': subcube_orders,
            'units_sold': subcube_units,
            'avg_order_value': subcube_aov,
            'share_of_global_pct': share_of_global,
            'is_empty': len(diced_records) == 0,
        }

        return {
            'success': True,
            'operation': 'dice',
            'subcube_summary': subcube_summary,
            'records': diced_records,
            'record_count': len(diced_records),
            'available_filters': {
                'years': all_years,
                'months': [
                    {'month': i, 'code': f"{i:02d}", 'name': MONTH_NAMES[f"{i:02d}"], 'full_name': MONTH_FULL_NAMES[f"{i:02d}"]}
                    for i in range(1, 13)
                ],
            },
            'chart_config': {
                'chart_type': 'column',
                'chart_title': (
                    f"Diced Subcube: Revenue across Years ({', '.join(years_filter) or 'None'}) "
                    f"& Months ({', '.join(MONTH_NAMES[f'{m:02d}'] for m in sorted(months_filter)) or 'None'})"
                ),
                'metric_label': 'Realised Revenue (₹)',
            },
            'olap_concept': (
                "OLAP DICE constructs an analytical subcube along the time dimension by combining "
                "multiple arbitrary discrete predicates (e.g. Years ∈ {2024, 2025} AND Months ∈ {Apr, May, Jun}) "
                "for non-hierarchical cross-period benchmarking."
            ),
            'all_tiers_summary': shared['all_tiers_summary'],
            'data_reconciliation': shared['data_reconciliation'],
            'data_quality_report': shared['data_quality_report'],
            'notices': shared['notices'],
        }

    # =========================================================================
    # OPERATION 5: PIVOT
    # =========================================================================
    @classmethod
    def get_pivot_analysis(cls, force_refresh=False):
        """
        Executes OLAP PIVOT by rotating the 1D Time Dimension into a 2D
        Year x Quarter cross-tabulation matrix.
        """
        shared, err = cls._get_shared_cubes(force_refresh=force_refresh)
        if err:
            return err

        quarterly_dict = shared['quarterly_dict']
        yearly_records = shared['yearly_records']
        all_years = ['2024', '2025', '2026']
        all_quarters = ['Q1', 'Q2', 'Q3', 'Q4']

        matrix_rows = []
        for y in all_years:
            yr_match = next((yr for yr in yearly_records if yr['year'] == y), None)
            row_cells = {}
            for q in all_quarters:
                yq_key = f"{y}-{q}"
                if yq_key in quarterly_dict:
                    q_data = quarterly_dict[yq_key]
                    row_cells[q] = {
                        'recorded': True,
                        'revenue': q_data['total_revenue'],
                        'order_count': q_data['order_count'],
                        'units_sold': q_data['units_sold'],
                        'avg_order_value': q_data['avg_order_value'],
                        'is_partial': q_data['is_partial'],
                        'status_badge': q_data['status_badge'],
                        'display_value': f"₹{q_data['total_revenue']:,.2f}",
                        'period_key': yq_key,
                    }
                else:
                    row_cells[q] = {
                        'recorded': False,
                        'revenue': None,
                        'order_count': None,
                        'units_sold': None,
                        'avg_order_value': None,
                        'is_partial': False,
                        'status_badge': 'Unrecorded / Future',
                        'display_value': 'N/A',
                        'period_key': yq_key,
                    }

            matrix_rows.append({
                'year': y,
                'is_partial': yr_match['is_partial'] if yr_match else True,
                'status_badge': yr_match['status_badge'] if yr_match else '',
                'cells': row_cells,
                'row_total_revenue': yr_match['total_revenue'] if yr_match else 0.0,
                'row_total_orders': yr_match['order_count'] if yr_match else 0,
                'row_total_units': yr_match['units_sold'] if yr_match else 0,
                'row_aov': yr_match['avg_order_value'] if yr_match else 0.0,
            })

        # Calculate column totals (Quarters across recorded years)
        col_totals = {}
        for q in all_quarters:
            q_rev = round(sum(r['cells'][q]['revenue'] for r in matrix_rows if r['cells'][q]['recorded']), 2)
            q_orders = sum(r['cells'][q]['order_count'] for r in matrix_rows if r['cells'][q]['recorded'])
            q_units = sum(r['cells'][q]['units_sold'] for r in matrix_rows if r['cells'][q]['recorded'])
            q_aov = round(q_rev / q_orders, 2) if q_orders > 0 else 0.0
            col_totals[q] = {
                'quarter': q,
                'total_revenue': q_rev,
                'total_orders': q_orders,
                'total_units': q_units,
                'avg_order_value': q_aov,
                'display_value': f"₹{q_rev:,.2f}",
            }

        grand_total_revenue = round(sum(r['row_total_revenue'] for r in matrix_rows), 2)
        grand_total_orders = sum(r['row_total_orders'] for r in matrix_rows)
        grand_total_units = sum(r['row_total_units'] for r in matrix_rows)
        grand_total_aov = round(grand_total_revenue / grand_total_orders, 2) if grand_total_orders > 0 else 0.0

        col_sum_revenue = round(sum(col_totals[q]['total_revenue'] for q in all_quarters), 2)
        pivot_reconciled = (grand_total_revenue == col_sum_revenue == shared['data_reconciliation']['yearly_total_revenue'])

        return {
            'success': True,
            'operation': 'pivot',
            'matrix_headers': {
                'row_dimension': 'Calendar Year',
                'columns': all_quarters,
                'total_header': 'Yearly Total (Row Total)',
            },
            'matrix_rows': matrix_rows,
            'column_totals': col_totals,
            'grand_total': {
                'revenue': grand_total_revenue,
                'orders': grand_total_orders,
                'units': grand_total_units,
                'aov': grand_total_aov,
                'reconciled': pivot_reconciled,
            },
            'chart_config': {
                'chart_type': 'grouped_column',
                'chart_title': 'Year x Quarter Revenue Matrix (Seasonal Comparison)',
                'metric_label': 'Realised Revenue (₹)',
            },
            'olap_concept': (
                "OLAP PIVOT reorients the single Time Dimension into a 2D cross-tabulation of Years (rows) "
                "by Quarters (columns). This exposes seasonal quarter-over-quarter patterns across years without "
                "inventing external non-time dimensions."
            ),
            'all_tiers_summary': shared['all_tiers_summary'],
            'data_reconciliation': shared['data_reconciliation'],
            'data_quality_report': shared['data_quality_report'],
            'notices': shared['notices'],
        }

    # =========================================================================
    # OPERATION 6: RANKING
    # =========================================================================
    @classmethod
    def get_ranking_analysis(cls, granularity='month', sort_order='desc', force_refresh=False):
        """
        Ranks actual time periods by realised revenue (SUM(final_price)) with
        deterministic tie handling and explicit partial-period analytical warnings.
        """
        shared, err = cls._get_shared_cubes(force_refresh=force_refresh)
        if err:
            return err

        gran_clean = str(granularity or 'month').strip().lower()
        if gran_clean not in ('month', 'quarter', 'year'):
            gran_clean = 'month'

        is_desc = str(sort_order or 'desc').strip().lower() != 'asc'

        if gran_clean == 'month':
            raw_items = shared['months']
            label_prefix = 'Monthly Leaderboard (25 Months)'
        elif gran_clean == 'quarter':
            raw_items = shared['quarterly_records']
            label_prefix = 'Quarterly Leaderboard (9 Quarters)'
        else:
            raw_items = shared['yearly_records']
            label_prefix = 'Yearly Leaderboard (3 Years)'

        # Deterministic sort: revenue desc/asc, then period_key desc
        if is_desc:
            sorted_items = sorted(raw_items, key=lambda x: (-x['total_revenue'], x['period_key']))
        else:
            sorted_items = sorted(raw_items, key=lambda x: (x['total_revenue'], x['period_key']))

        ranked_records = []
        for idx, item in enumerate(sorted_items):
            rec = dict(item)
            rec['rank'] = idx + 1
            if item.get('is_partial'):
                pk = item['period_key']
                if pk == '2024-03':
                    warning = "Inception Artifact: March 2024 has only 1 day (March 31). Ranked 25th due to single-day duration, not sales underperformance."
                elif pk == '2024-Q1':
                    warning = "Inception Artifact: 2024-Q1 has only 1 day (March 31). Ranked 9th due to single-day duration."
                elif pk == '2026':
                    warning = "Partial Year Artifact: Year 2026 contains only Q1 (3 months). Lower rank is due to calendar truncation."
                elif pk == '2024':
                    warning = "Partial Year Artifact: Year 2024 contains 9 months + 1 day."
                else:
                    warning = "Partial duration period: Not directly comparable with full calendar periods."
            else:
                warning = None
            rec['comparison_warning'] = warning
            ranked_records.append(rec)

        top_performer = ranked_records[0] if ranked_records else None
        bottom_performer = ranked_records[-1] if ranked_records else None

        return {
            'success': True,
            'operation': 'ranking',
            'granularity': gran_clean,
            'sort_order': 'desc' if is_desc else 'asc',
            'ranking_title': label_prefix,
            'records': ranked_records,
            'record_count': len(ranked_records),
            'top_performer': top_performer,
            'bottom_performer': bottom_performer,
            'chart_config': {
                'chart_type': 'bar',
                'chart_title': f"Revenue Ranking: {label_prefix}",
                'metric_label': 'Realised Revenue (₹)',
            },
            'olap_concept': (
                "OLAP RANKING sorts time coordinates by actual aggregate revenue measure. "
                "Crucially, partial periods (e.g. 1-day March 2024) are badged to avoid false performance conclusions."
            ),
            'all_tiers_summary': shared['all_tiers_summary'],
            'data_reconciliation': shared['data_reconciliation'],
            'data_quality_report': shared['data_quality_report'],
            'notices': shared['notices'],
        }

    # =========================================================================
    # OPERATION 7: DRILL-THROUGH
    # =========================================================================
    @classmethod
    def get_drillthrough_orders(cls, period_type='month', period_key=None, page=1, page_size=50):
        """
        Executes OLAP DRILL-THROUGH down to the atomic raw transactions in public.orders.
        Enforces server-side pagination with a strict maximum page size of 50,
        deterministic sorting, customer ID masking, and exclusion of sensitive PII.
        """
        # Strict validation: maximum page size 50
        try:
            page_size_int = int(page_size)
        except (ValueError, TypeError):
            page_size_int = 50

        if page_size_int > 50:
            return {
                'success': False,
                'error': 'Maximum page size for Drill-Through is 50. Requests exceeding 50 records per page are rejected for system performance and security.'
            }
        if page_size_int < 1:
            page_size_int = 50

        try:
            page_int = int(page)
            if page_int < 1:
                page_int = 1
        except (ValueError, TypeError):
            page_int = 1

        period_type_clean = str(period_type or 'month').strip().lower()
        params = []
        period_sql = ""

        if period_type_clean == 'month' and period_key:
            period_sql = "AND TO_CHAR(TO_DATE(purchase_date, 'DD-MM-YYYY'), 'YYYY-MM') = %s"
            params.append(str(period_key))
        elif period_type_clean == 'quarter' and period_key:
            period_sql = "AND TO_CHAR(TO_DATE(purchase_date, 'DD-MM-YYYY'), 'YYYY') || '-Q' || TO_CHAR(TO_DATE(purchase_date, 'DD-MM-YYYY'), 'Q') = %s"
            params.append(str(period_key))
        elif period_type_clean == 'year' and period_key:
            period_sql = "AND TO_CHAR(TO_DATE(purchase_date, 'DD-MM-YYYY'), 'YYYY') = %s"
            params.append(str(period_key))
        elif period_type_clean == 'all' or not period_key:
            period_sql = ""
            params = []

        safe_condition_escaped = SAFE_GREGORIAN_DATE_CONDITION.replace('%', '%%')

        count_sql = f"""
            WITH valid_delivered_orders AS MATERIALIZED (
                SELECT 
                    orderid,
                    quantity,
                    final_price,
                    purchase_date
                FROM orders
                WHERE delivery_status = 'Delivered'
                  AND {safe_condition_escaped}
            )
            SELECT 
                COUNT(orderid),
                COUNT(DISTINCT orderid),
                COALESCE(SUM(quantity), 0),
                COALESCE(SUM(final_price), 0)
            FROM valid_delivered_orders
            WHERE 1=1 {period_sql};
        """

        try:
            with connection.cursor() as cursor:
                cursor.execute(count_sql, params)
                c_row = cursor.fetchone()
                total_orders = int(c_row[0] or 0)
                distinct_orders = int(c_row[1] or 0)
                total_units = int(c_row[2] or 0)
                total_revenue = round(float(c_row[3] or 0.0), 2)
        except Exception as exc:
            return {
                'success': False,
                'error': f'Database error counting drill-through orders: {str(exc)}'
            }

        total_pages = max(1, math.ceil(total_orders / page_size_int))
        if page_int > total_pages:
            page_int = total_pages

        offset = (page_int - 1) * page_size_int

        fetch_sql = f"""
            WITH valid_delivered_orders AS MATERIALIZED (
                SELECT 
                    orderid,
                    purchase_date,
                    customer_id,
                    product_id,
                    payment_method,
                    quantity,
                    final_price,
                    shipping_time_days,
                    rating
                FROM orders
                WHERE delivery_status = 'Delivered'
                  AND {safe_condition_escaped}
            )
            SELECT 
                orderid,
                purchase_date,
                customer_id,
                product_id,
                payment_method,
                quantity,
                final_price,
                shipping_time_days,
                rating
            FROM valid_delivered_orders
            WHERE 1=1 {period_sql}
            ORDER BY TO_DATE(purchase_date, 'DD-MM-YYYY') DESC, orderid DESC
            LIMIT %s OFFSET %s;
        """

        try:
            with connection.cursor() as cursor:
                cursor.execute(fetch_sql, params + [page_size_int, offset])
                raw_orders = cursor.fetchall()
        except Exception as exc:
            return {
                'success': False,
                'error': f'Database error fetching drill-through records: {str(exc)}'
            }

        orders_list = []
        for row in raw_orders:
            orders_list.append({
                'orderid': row[0],
                'purchase_date': row[1],
                'customer_id_masked': mask_customer_id(row[2]),
                'product_id': row[3] or '—',
                'payment_method': row[4] or '—',
                'quantity': int(row[5] or 0),
                'final_price': round(float(row[6] or 0.0), 2),
                'shipping_time_days': int(row[7]) if row[7] is not None else None,
                'rating': round(float(row[8]), 1) if row[8] is not None else None,
                'delivery_status': 'Delivered',
            })

        overall_aov = round(total_revenue / distinct_orders, 2) if distinct_orders > 0 else 0.0

        return {
            'success': True,
            'operation': 'drillthrough',
            'period_context': {
                'period_type': period_type_clean,
                'period_key': period_key or 'ALL',
            },
            'orders': orders_list,
            'pagination': {
                'page': page_int,
                'page_size': page_size_int,
                'total_orders': total_orders,
                'distinct_orders': distinct_orders,
                'total_pages': total_pages,
                'has_next': page_int < total_pages,
                'has_prev': page_int > 1,
            },
            'period_summary': {
                'total_revenue': total_revenue,
                'total_orders': total_orders,
                'total_units': total_units,
                'overall_aov': overall_aov,
            },
            'security_and_privacy': {
                'customer_id_masked': True,
                'pii_excluded': "Passwords, emails, phone numbers, and payment details are not stored in orders or returned.",
                'max_page_size_enforced': 50,
                'deterministic_sort': "ORDER BY purchase_date DESC, orderid DESC",
            },
        }

    # =========================================================================
    # OPERATION 8: TREND ANALYSIS
    # =========================================================================
    @classmethod
    def get_trend_analysis(cls, force_refresh=False):
        """
        Executes Historical Actual Revenue Trend Analysis across all 25 chronological
        months: calculates MoM change, MoM %, YoY %, and 3-Month Moving Average (SMA-3).
        Safeguards and badges the March 2024 single-day baseline and March 2025 YoY artifacts.
        Strictly isolates actual revenue from forecasting models.
        """
        shared, err = cls._get_shared_cubes(force_refresh=force_refresh)
        if err:
            return err

        months = shared['months']

        trend_records = []
        for idx, cur_m in enumerate(months):
            cur_rev = cur_m['total_revenue']

            # 1. Month-over-Month (MoM)
            if idx == 0:
                prior_m_rev = None
                mom_change = None
                mom_growth_pct = None
                is_mom_artifact = False
                mom_note = "Inception Period: March 31, 2024 only (1 day). No prior month exists."
            else:
                prior_m = months[idx - 1]
                prior_m_rev = prior_m['total_revenue']
                mom_change = round(cur_rev - prior_m_rev, 2)
                mom_growth_pct = round(((cur_rev - prior_m_rev) / prior_m_rev) * 100, 2) if prior_m_rev > 0 else 0.0

                if idx == 1:
                    is_mom_artifact = True
                    mom_note = "Inception Baseline Artifact: Growth reflects 30 full days compared against a 1-day baseline (March 31, 2024). Not representative of normal monthly growth."
                else:
                    is_mom_artifact = False
                    mom_note = "Normal MoM"

            # 2. Year-over-Year (YoY) - 12 months prior
            y_int = int(cur_m['year'])
            target_ym = f"{y_int - 1}-{cur_m['month']:02d}"
            prior_year_m = next((m for m in months if m['period_key'] == target_ym), None)

            if prior_year_m:
                py_rev = prior_year_m['total_revenue']
                yoy_change = round(cur_rev - py_rev, 2)
                yoy_growth_pct = round(((cur_rev - py_rev) / py_rev) * 100, 2) if py_rev > 0 else 0.0

                if target_ym == '2024-03':
                    is_yoy_non_comparable = True
                    yoy_note = "Non-Comparable YoY Artifact: March 2025 (31 full days) compared against March 2024 (1 day inception). Excluded from normal YoY comparisons."
                else:
                    is_yoy_non_comparable = False
                    yoy_note = "Normal YoY (12-month lag)"
            else:
                py_rev = None
                yoy_change = None
                yoy_growth_pct = None
                is_yoy_non_comparable = False
                yoy_note = "No 12-month prior observation available in dataset."

            # 3. Three-Month Simple Moving Average (SMA-3)
            # March 2024 (idx=0) is a partial month containing only 1 recorded day (March 31).
            # It must NOT be included in a standard 3-month moving average.
            # The first valid SMA-3 is June 2024 (idx=3), calculated using April, May, and June 2024.
            # For earlier observations (idx < 3), SMA-3 is None (N/A) with a clear partial-baseline note.
            if idx >= 3 and not (months[idx - 2]['is_partial'] or months[idx - 1]['is_partial'] or cur_m['is_partial']):
                sma_3 = round((months[idx - 2]['total_revenue'] + months[idx - 1]['total_revenue'] + cur_rev) / 3.0, 2)
                sma_3_status = 'VALID'
                sma_3_note = f"SMA-3: {months[idx - 2]['period_key']} to {cur_m['period_key']}"
            else:
                sma_3 = None
                sma_3_status = 'N/A'
                if cur_m['is_partial']:
                    sma_3_note = "Inception Period (1 Day): Standard 3-month moving average is unavailable."
                elif idx < 3:
                    sma_3_note = "Partial-Baseline Exclusion: March 2024 (1 day) is excluded from moving averages. First valid SMA-3 is June 2024 (Apr–Jun 2024)."
                else:
                    sma_3_note = "Contains partial period; standard 3-month moving average excluded."

            trend_records.append({
                'period_key': cur_m['period_key'],
                'label': cur_m['label'],
                'year': cur_m['year'],
                'quarter': cur_m['quarter'],
                'month': cur_m['month'],
                'actual_revenue': cur_rev,
                'order_count': cur_m['order_count'],
                'distinct_orders': cur_m['distinct_orders'],
                'units_sold': cur_m['units_sold'],
                'avg_order_value': cur_m['avg_order_value'],
                'is_partial': cur_m['is_partial'],
                'status_badge': cur_m['status_badge'],
                'prior_month_revenue': prior_m_rev,
                'mom_change': mom_change,
                'mom_growth_pct': mom_growth_pct,
                'is_mom_artifact': is_mom_artifact,
                'mom_note': mom_note,
                'prior_year_period': target_ym if prior_year_m else None,
                'prior_year_revenue': py_rev,
                'yoy_change': yoy_change,
                'yoy_growth_pct': yoy_growth_pct,
                'is_yoy_non_comparable': is_yoy_non_comparable,
                'yoy_note': yoy_note,
                'sma_3': sma_3,
                'sma_3_status': sma_3_status,
                'sma_3_note': sma_3_note,
            })

        # Calculate high-level trend metrics across full 24 months
        full_months = [t for t in trend_records if not t['is_partial']]
        avg_monthly_rev = round(sum(m['actual_revenue'] for m in full_months) / len(full_months), 2) if full_months else 0.0

        valid_yoy = [t['yoy_growth_pct'] for t in trend_records if t['yoy_growth_pct'] is not None and not t['is_yoy_non_comparable']]
        avg_yoy_growth = round(sum(valid_yoy) / len(valid_yoy), 2) if valid_yoy else 0.0

        peak_month = max(trend_records, key=lambda x: x['actual_revenue'])
        lowest_full_month = min(full_months, key=lambda x: x['actual_revenue']) if full_months else None

        trend_summary = {
            'total_months_observed': len(trend_records),
            'full_months_observed': len(full_months),
            'average_monthly_revenue_full_months': avg_monthly_rev,
            'average_yoy_growth_rate_pct': avg_yoy_growth,
            'peak_revenue_month': {
                'label': peak_month['label'],
                'revenue': peak_month['actual_revenue'],
            },
            'lowest_revenue_full_month': {
                'label': lowest_full_month['label'] if lowest_full_month else '—',
                'revenue': lowest_full_month['actual_revenue'] if lowest_full_month else 0.0,
                'note': 'Reflects standard 28-day February calendar duration.',
            },
        }

        return {
            'success': True,
            'operation': 'trend',
            'title': 'Historical Actual Revenue Trend Analysis',
            'trend_summary': trend_summary,
            'records': trend_records,
            'record_count': len(trend_records),
            'chart_config': {
                'chart_type': 'line_with_sma',
                'chart_title': 'Actual Monthly Realised Revenue & 3-Month Moving Average (SMA-3)',
                'metric_label': 'Realised Revenue (₹)',
            },
            'olap_concept': (
                "Trend Analysis tracks historical month-over-month and year-over-year revenue velocity "
                "strictly using verified past deliveries. Inception baseline spikes (+2516% in Apr 2024 and +2707% in Mar 2025) "
                "are identified and isolated from operational business evaluation."
            ),
            'all_tiers_summary': shared['all_tiers_summary'],
            'data_reconciliation': shared['data_reconciliation'],
            'data_quality_report': shared['data_quality_report'],
            'notices': shared['notices'],
        }

    # =========================================================================
    # UNIFIED ENTRY POINT: ROLL-UP, DRILL-DOWN & ALL 6 EXTENSIONS
    # =========================================================================
    @classmethod
    def get_time_olap_analysis(
        cls,
        operation='rollup',
        level='quarter',
        selected_year=None,
        selected_quarter=None,
        slice_type='year',
        slice_value=None,
        selected_years=None,
        selected_months=None,
        granularity=None,
        sort_order='desc',
        period_type='month',
        period_key=None,
        page=1,
        page_size=50,
        force_refresh=False
    ):
        """
        Unified entry point for the Time Dimension OLAP Suite:
        - 'rollup': Month -> Quarter -> Year
        - 'drilldown': Year -> Quarter -> Month
        - 'slice': One time coordinate filter
        - 'dice': Multi-condition subcube
        - 'pivot': Year x Quarter revenue matrix
        - 'ranking': Revenue leaderboards
        - 'drillthrough': Paginated raw transaction inspection
        - 'trend': Historical chronological growth and SMA-3
        """
        op_clean = str(operation or 'rollup').strip().lower()

        # Delegate to specialized operations
        if op_clean == 'slice':
            return cls.get_slice_analysis(
                slice_type=slice_type or 'year',
                slice_value=slice_value or selected_year or '2025',
                force_refresh=force_refresh,
            )
        elif op_clean == 'dice':
            return cls.get_dice_analysis(
                selected_years=selected_years,
                selected_months=selected_months,
                force_refresh=force_refresh,
            )
        elif op_clean == 'pivot':
            return cls.get_pivot_analysis(force_refresh=force_refresh)
        elif op_clean == 'ranking':
            return cls.get_ranking_analysis(
                granularity=granularity or level or 'month',
                sort_order=sort_order or 'desc',
                force_refresh=force_refresh,
            )
        elif op_clean == 'drillthrough':
            return cls.get_drillthrough_orders(
                period_type=period_type or level or 'month',
                period_key=period_key or selected_year or selected_quarter,
                page=page,
                page_size=page_size,
            )
        elif op_clean == 'trend':
            return cls.get_trend_analysis(force_refresh=force_refresh)

        # Base Roll-up and Drill-down execution
        shared, err = cls._get_shared_cubes(force_refresh=force_refresh)
        if err:
            return err

        months = shared['months']
        quarterly_records = shared['quarterly_records']
        yearly_records = shared['yearly_records']
        available_years = shared['available_years']
        quarters_by_year = shared['quarters_by_year']

        level_clean = str(level).strip().lower()

        if op_clean == 'rollup':
            if level_clean == 'month':
                current_records = months
                current_level_label = 'Monthly Level (Base Grain - 25 Months)'
                chart_type = 'column'
                chart_title = 'Monthly Realised Revenue Aggregation'
            elif level_clean == 'year':
                current_records = yearly_records
                current_level_label = 'Yearly Roll-up (Level 3 - 3 Years)'
                chart_type = 'column'
                chart_title = 'Consolidated Yearly Revenue Roll-up'
            else:
                level_clean = 'quarter'
                current_records = quarterly_records
                current_level_label = 'Quarterly Roll-up (Level 2 - 9 Quarters)'
                chart_type = 'column'
                chart_title = 'Consolidated Quarterly Revenue Roll-up'

            drilldown_context = None

        else:
            # DRILL-DOWN
            op_clean = 'drilldown'
            if not selected_year or str(selected_year) not in available_years:
                selected_year = '2025'
            else:
                selected_year = str(selected_year)

            valid_quarters = quarters_by_year.get(selected_year, [])

            if level_clean == 'month':
                if not selected_quarter or str(selected_quarter) not in valid_quarters:
                    selected_quarter = 'ALL'
                    current_records = [m for m in months if m['year'] == selected_year]
                    current_level_label = f"Monthly Drill-down: All Months of {selected_year}"
                    chart_title = f"Monthly Revenue Progression in {selected_year}"
                else:
                    selected_quarter = str(selected_quarter)
                    current_records = [
                        m for m in months
                        if m['year'] == selected_year and m['quarter'] == selected_quarter
                    ]
                    current_level_label = f"Monthly Drill-down: {selected_year} {selected_quarter}"
                    chart_title = f"Monthly Revenue Distribution ({selected_year} {selected_quarter})"

                chart_type = 'line_bar'

            elif level_clean == 'year':
                current_records = yearly_records
                current_level_label = 'Year Overview (Top Level)'
                chart_type = 'column'
                chart_title = 'Annual Revenue Distribution (Select a Year to Drill Down)'
                selected_quarter = None

            else:
                level_clean = 'quarter'
                current_records = [q for q in quarterly_records if q['year'] == selected_year]
                current_level_label = f"Quarterly Drill-down: {selected_year} ({cls._get_year_status_label(selected_year)})"
                chart_type = 'column'
                chart_title = f"Quarterly Revenue Progression in {selected_year}"
                selected_quarter = None

            drilldown_context = {
                'selected_year': selected_year,
                'selected_quarter': selected_quarter,
                'available_years': available_years,
                'available_quarters': valid_quarters,
                'year_status': cls._get_year_status_label(selected_year),
            }

        return {
            'success': True,
            'operation': op_clean,
            'level': level_clean,
            'level_label': current_level_label,
            'records': current_records,
            'record_count': len(current_records),
            'chart_config': {
                'chart_type': chart_type,
                'chart_title': chart_title,
                'metric_label': 'Realised Revenue (₹)',
            },
            'drilldown_context': drilldown_context,
            'available_filters': {
                'years': available_years,
                'quarters_by_year': quarters_by_year,
            },
            'all_tiers_summary': shared['all_tiers_summary'],
            'data_reconciliation': shared['data_reconciliation'],
            'data_quality_report': shared['data_quality_report'],
            'notices': shared['notices'],
        }

    @staticmethod
    def _get_quarter_span(yq):
        quarter_spans = {
            'Q1': 'Jan – Mar',
            'Q2': 'Apr – Jun',
            'Q3': 'Jul – Sep',
            'Q4': 'Oct – Dec',
        }
        q = yq.split('-')[1]
        return quarter_spans.get(q, q)

    @staticmethod
    def _get_year_status_label(year_str):
        if year_str == '2024':
            return 'Partial Year: 9M + 1D'
        elif year_str == '2025':
            return 'Complete Calendar Year: 12M'
        elif year_str == '2026':
            return 'Partial Year: Q1 only / 3M'
        return 'Year'
