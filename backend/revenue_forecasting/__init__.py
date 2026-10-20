"""
Revenue Forecasting Data Mining Module
--------------------------------------
Separate logical module that sits directly on top of the existing Demand
Prediction hierarchy. It consumes existing predicted-sales output (never a
second, duplicate demand model) and converts it into expected revenue:

    Existing Demand Prediction  ->  Predicted Sales Quantity
                                          |
                                   Revenue Forecasting
                                          |
                        Predicted Sales x Selling Price  ->  Expected Revenue

All core business logic lives in Python (see revenue_forecast.py / services.py);
the React frontend only consumes and displays the calculated results.
"""
default_app_config = 'revenue_forecasting.apps.RevenueForecastingConfig'
