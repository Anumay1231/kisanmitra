"""The external tools the agent can call: weather API, market price API, dealership SQL database,
finance calculator and a scheme-rules retriever."""
from __future__ import annotations

import sqlite3
from typing import Optional

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from . import config

# ---------------------------------------------------------------- helpers

def _db():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _rows_to_text(rows, empty: str) -> str:
    if not rows:
        return empty
    return "\n".join("; ".join(f"{k}={r[k]}" for k in r.keys()) for r in rows)


# ---------------------------------------------------------------- 1. weather API

class WeatherArgs(BaseModel):
    location: str = Field(description="Village, town or district name, e.g. 'Dhamtari' or 'Raipur'")
    days: int = Field(default=3, ge=1, le=7, description="Number of forecast days (1-7)")


@tool("get_weather_forecast", args_schema=WeatherArgs)
def get_weather_forecast(location: str, days: int = 3) -> str:
    """Get the daily rain, temperature and wind forecast for an Indian location.
    Use before advising on spraying, harvesting, ploughing or any field operation that depends on rain."""
    try:
        geo = requests.get(config.GEOCODE_URL, params={"name": location, "count": 1, "country": "IN"},
                           timeout=config.HTTP_TIMEOUT).json()
        results = geo.get("results") or []
        if not results:
            return (f"TOOL_ERROR: location '{location}' not found by the geocoding service. "
                    "Ask the user for a nearby district or town name.")
        place = results[0]
        fc = requests.get(config.FORECAST_URL, params={
            "latitude": place["latitude"], "longitude": place["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
            "forecast_days": days, "timezone": "auto"}, timeout=config.HTTP_TIMEOUT).json()
        d = fc["daily"]
        lines = [f"Forecast for {place['name']}, {place.get('admin1', '')}:"]
        for i, day in enumerate(d["time"]):
            lines.append(
                f"{day}: rain {d['precipitation_sum'][i]} mm (chance {d['precipitation_probability_max'][i]}%), "
                f"temp {d['temperature_2m_min'][i]}-{d['temperature_2m_max'][i]} C, "
                f"max wind {d['wind_speed_10m_max'][i]} km/h")
        return "\n".join(lines)
    except requests.RequestException as exc:
        return f"TOOL_ERROR: weather service unreachable ({exc.__class__.__name__}). Answer without forecast data and say so."
    except (KeyError, ValueError) as exc:
        return f"TOOL_ERROR: unexpected weather response ({exc}). Do not guess the weather."


# ---------------------------------------------------------------- 2. market price API

class MandiArgs(BaseModel):
    commodity: str = Field(description="Crop name as used in mandi data, e.g. 'Paddy(Dhan)(Common)', 'Wheat', 'Soyabean'")
    state: str = Field(default="Chhattisgarh", description="State name, e.g. 'Chhattisgarh', 'Madhya Pradesh'")


@tool("get_mandi_price", args_schema=MandiArgs)
def get_mandi_price(commodity: str, state: str = "Chhattisgarh") -> str:
    """Get recent mandi (market) prices per quintal for a crop in a state, from the data.gov.in daily price dataset.
    Use when the user asks about selling crops, crop income or whether a purchase is affordable from expected income."""
    if not config.DATAGOV_KEY:
        return ("TOOL_ERROR: no data.gov.in API key configured, so live mandi prices are unavailable. "
                "Tell the user this and continue without price data, or ask them for their expected selling price.")
    try:
        r = requests.get(config.MANDI_URL, params={
            "api-key": config.DATAGOV_KEY, "format": "json", "limit": 10,
            "filters[commodity]": commodity, "filters[state]": state}, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        records = r.json().get("records", [])
        if not records:
            return (f"TOOL_ERROR: no mandi records for commodity='{commodity}' in state='{state}'. "
                    "The commodity name may not match the dataset; ask the user to confirm the crop name.")
        lines = [f"{rec.get('arrival_date')}: {rec.get('market')} ({rec.get('district')}) "
                 f"modal Rs {rec.get('modal_price')}/quintal (min {rec.get('min_price')}, max {rec.get('max_price')})"
                 for rec in records[:5]]
        return f"Mandi prices for {commodity} in {state}:\n" + "\n".join(lines)
    except requests.RequestException as exc:
        return f"TOOL_ERROR: mandi price service unreachable ({exc.__class__.__name__}). Continue without price data."


# ---------------------------------------------------------------- 3. dealership database

class InventoryArgs(BaseModel):
    category: Optional[str] = Field(default=None, description="'tractor', 'implement' or 'harvester'")
    min_hp: Optional[int] = Field(default=None, description="Minimum horsepower required")
    max_price: Optional[int] = Field(default=None, description="Maximum budget in rupees")
    in_stock_only: bool = Field(default=True, description="Only list machines currently in stock")


@tool("search_inventory", args_schema=InventoryArgs)
def search_inventory(category: Optional[str] = None, min_hp: Optional[int] = None,
                     max_price: Optional[int] = None, in_stock_only: bool = True) -> str:
    """Search the dealership's machine inventory (model, horsepower, price, stock, fuel use).
    Always use this instead of guessing which machines or prices the dealership has."""
    sql = "SELECT model, category, hp, price_inr, stock, fuel_lph, notes FROM machines WHERE 1=1"
    params: list = []
    if category:
        sql += " AND category = ?"; params.append(category.lower())
    if min_hp is not None:
        sql += " AND hp >= ?"; params.append(min_hp)
    if max_price is not None:
        sql += " AND price_inr <= ?"; params.append(max_price)
    if in_stock_only:
        sql += " AND stock > 0"
    sql += " ORDER BY price_inr"
    with _db() as con:
        rows = con.execute(sql, params).fetchall()
    return _rows_to_text(rows, "No machines match those filters. Suggest relaxing budget or horsepower.")


class ServiceArgs(BaseModel):
    customer: Optional[str] = Field(default=None, description="Customer name or part of it")
    model: Optional[str] = Field(default=None, description="Machine model, e.g. 'JD 5050D'")
    limit: int = Field(default=5, ge=1, le=20, description="How many recent records to return")


@tool("search_service_records", args_schema=ServiceArgs)
def search_service_records(customer: Optional[str] = None, model: Optional[str] = None, limit: int = 5) -> str:
    """Look up past service jobs (date, engine hours, issue, cost) for a customer or a machine model.
    Use for questions about service history, repeated faults or typical repair cost."""
    sql = ("SELECT service_date, customer, village, model, hours, issue, cost_inr "
           "FROM service_records WHERE 1=1")
    params: list = []
    if customer:
        sql += " AND customer LIKE ?"; params.append(f"%{customer}%")
    if model:
        sql += " AND model LIKE ?"; params.append(f"%{model}%")
    sql += " ORDER BY service_date DESC LIMIT ?"; params.append(limit)
    with _db() as con:
        rows = con.execute(sql, params).fetchall()
    return _rows_to_text(rows, "No service records found for that customer or model.")


class PartArgs(BaseModel):
    query: str = Field(description="Part name or part number, e.g. 'oil filter' or 'AL-172772'")


@tool("check_part_stock", args_schema=PartArgs)
def check_part_stock(query: str) -> str:
    """Check spare-part availability and price at the dealership by part name or part number."""
    with _db() as con:
        rows = con.execute(
            "SELECT part_no, name, model, price_inr, stock FROM parts WHERE name LIKE ? OR part_no LIKE ?",
            (f"%{query}%", f"%{query}%")).fetchall()
    return _rows_to_text(rows, f"No part matching '{query}' in the catalogue.")


# ---------------------------------------------------------------- 4. finance calculator

class FinanceArgs(BaseModel):
    price_inr: float = Field(description="On-road price of the machine in rupees")
    subsidy_percent: float = Field(default=0, ge=0, le=100, description="Subsidy percentage the buyer qualifies for")
    down_payment_inr: float = Field(default=0, ge=0, description="Amount paid upfront")
    annual_rate_percent: float = Field(default=9.5, gt=0, description="Annual loan interest rate")
    years: int = Field(default=5, ge=1, le=15, description="Loan tenure in years")


@tool("calculate_purchase_plan", args_schema=FinanceArgs)
def calculate_purchase_plan(price_inr: float, subsidy_percent: float = 0, down_payment_inr: float = 0,
                            annual_rate_percent: float = 9.5, years: int = 5) -> str:
    """Compute subsidy amount, net cost, loan principal, monthly EMI and total interest for a machine purchase.
    Always use this tool for any EMI, subsidy or affordability arithmetic instead of calculating mentally."""
    subsidy = price_inr * subsidy_percent / 100
    net = price_inr - subsidy
    principal = max(net - down_payment_inr, 0)
    r = annual_rate_percent / 12 / 100
    n = years * 12
    emi = principal * r * (1 + r) ** n / ((1 + r) ** n - 1) if principal > 0 else 0
    total_interest = emi * n - principal
    return (f"price=Rs {price_inr:,.0f}; subsidy({subsidy_percent}%)=Rs {subsidy:,.0f}; net=Rs {net:,.0f}; "
            f"down_payment=Rs {down_payment_inr:,.0f}; loan_principal=Rs {principal:,.0f}; "
            f"emi=Rs {emi:,.0f}/month for {n} months at {annual_rate_percent}%; "
            f"total_interest=Rs {total_interest:,.0f}; total_paid=Rs {principal + total_interest:,.0f}")


class FuelArgs(BaseModel):
    model: str = Field(description="Machine model present in the inventory, e.g. 'JD 5050D'")
    hours: float = Field(gt=0, description="Hours of operation")
    diesel_price_per_litre: float = Field(default=95.0, gt=0, description="Diesel price in rupees per litre")


@tool("estimate_operating_cost", args_schema=FuelArgs)
def estimate_operating_cost(model: str, hours: float, diesel_price_per_litre: float = 95.0) -> str:
    """Estimate diesel consumption and fuel cost for operating a machine for a number of hours.
    Uses the fuel consumption stored for that model in the dealership database."""
    with _db() as con:
        row = con.execute("SELECT model, fuel_lph FROM machines WHERE model LIKE ?", (f"%{model}%",)).fetchone()
    if row is None:
        return f"TOOL_ERROR: model '{model}' not in inventory. Call search_inventory first to get exact model names."
    if not row["fuel_lph"]:
        return f"TOOL_ERROR: {row['model']} is an implement with no engine, so it has no fuel consumption of its own."
    litres = row["fuel_lph"] * hours
    return (f"{row['model']}: {row['fuel_lph']} L/hour x {hours} hours = {litres:.1f} litres; "
            f"fuel cost = Rs {litres * diesel_price_per_litre:,.0f} at Rs {diesel_price_per_litre}/litre")


BASE_TOOLS = [get_weather_forecast, get_mandi_price, search_inventory, search_service_records,
              check_part_stock, calculate_purchase_plan, estimate_operating_cost]
