"""
Wikidata SPARQL verification for entity facts.
Free, authoritative, no API key needed.
Verifies: Nobel prizes, capitals, dates, people, organizations.
"""
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {"Accept": "application/json", "User-Agent": "OpenFactCheck/1.0"}


async def _sparql_query(query: str) -> List[Dict[str, Any]]:
    """Execute a SPARQL query against Wikidata."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=8.0,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data.get("results", {}).get("bindings", [])
    except Exception as e:
        logger.debug(f"Wikidata query failed: {e}")
        return []


async def verify_nobel_prize(person: str, field: Optional[str] = None, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Check if a person won a Nobel Prize using Wikidata.
    Returns verdict info or None if no data found.
    """
    # Normalize person name for SPARQL
    person_escaped = person.replace("'", "\\'")

    query = f"""
    SELECT ?person ?personLabel ?prizeLabel ?year WHERE {{
      ?person rdfs:label "{person_escaped}"@en .
      ?person wdt:P166 ?prize .
      ?prize wdt:P31/wdt:P279* wd:Q7191 .
      OPTIONAL {{ ?person p:P166 ?statement .
                  ?statement ps:P166 ?prize .
                  ?statement pq:P585 ?date .
                  BIND(YEAR(?date) AS ?year) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }} LIMIT 10
    """

    results = await _sparql_query(query)
    if not results:
        return None

    prizes = []
    for r in results:
        prize_label = r.get("prizeLabel", {}).get("value", "")
        prize_year = r.get("year", {}).get("value", "")
        prizes.append({
            "prize": prize_label,
            "year": int(prize_year) if prize_year else None,
        })

    # Check if the claimed field/year match
    if field and year:
        field_lower = field.lower()
        for p in prizes:
            prize_lower = p["prize"].lower()
            if field_lower in prize_lower and p["year"] == year:
                return {
                    "verdict": "supported",
                    "evidence": f"{person} won {p['prize']} in {p['year']}",
                    "source": "Wikidata",
                }
        # Person has prizes but not the claimed one
        actual = "; ".join(f"{p['prize']} ({p['year']})" for p in prizes if p['year'])
        return {
            "verdict": "contradicted",
            "evidence": f"{person} won: {actual}. Not {field} in {year}.",
            "source": "Wikidata",
        }
    elif field:
        field_lower = field.lower()
        for p in prizes:
            if field_lower in p["prize"].lower():
                return {
                    "verdict": "supported",
                    "evidence": f"{person} won {p['prize']}" + (f" in {p['year']}" if p['year'] else ""),
                    "source": "Wikidata",
                }
        actual = "; ".join(p['prize'] for p in prizes)
        return {
            "verdict": "contradicted",
            "evidence": f"{person} won: {actual}. Not in {field}.",
            "source": "Wikidata",
        }

    # Just checking if they won any Nobel
    if prizes:
        actual = "; ".join(f"{p['prize']} ({p['year']})" for p in prizes if p['year'])
        return {
            "verdict": "supported",
            "evidence": f"{person} Nobel Prizes: {actual}",
            "source": "Wikidata",
        }
    return None


async def check_person_has_no_nobel(person: str) -> Optional[Dict[str, Any]]:
    """Check if a person did NOT win a Nobel Prize."""
    person_escaped = person.replace("'", "\\'")

    # First check if person exists in Wikidata
    query = f"""
    SELECT ?person ?personLabel WHERE {{
      ?person rdfs:label "{person_escaped}"@en .
      ?person wdt:P31 wd:Q5 .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }} LIMIT 1
    """
    person_exists = await _sparql_query(query)
    if not person_exists:
        return None  # Can't verify — person not found

    # Now check if they have Nobel prizes
    query2 = f"""
    SELECT ?prizeLabel WHERE {{
      ?person rdfs:label "{person_escaped}"@en .
      ?person wdt:P166 ?prize .
      ?prize wdt:P31/wdt:P279* wd:Q7191 .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }} LIMIT 5
    """
    prizes = await _sparql_query(query2)
    if not prizes:
        return {
            "verdict": "no_nobel",
            "evidence": f"{person} exists in Wikidata but has no Nobel Prize records.",
            "source": "Wikidata",
        }
    return None


async def verify_capital(city: str, country: str) -> Optional[Dict[str, Any]]:
    """Verify if a city is the capital of a country."""
    city_escaped = city.replace("'", "\\'")
    country_escaped = country.replace("'", "\\'")

    query = f"""
    SELECT ?countryLabel ?capitalLabel WHERE {{
      ?country rdfs:label "{country_escaped}"@en .
      ?country wdt:P31/wdt:P279* wd:Q6256 .
      ?country wdt:P36 ?capital .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }} LIMIT 5
    """
    results = await _sparql_query(query)
    if not results:
        return None

    for r in results:
        actual_capital = r.get("capitalLabel", {}).get("value", "")
        if actual_capital.lower() == city.lower():
            return {
                "verdict": "supported",
                "evidence": f"{city} is the capital of {country}.",
                "source": "Wikidata",
            }

    actual = results[0].get("capitalLabel", {}).get("value", "unknown")
    return {
        "verdict": "contradicted",
        "evidence": f"The capital of {country} is {actual}, not {city}.",
        "source": "Wikidata",
    }


async def verify_year_event(entity: str, event_type: str, claimed_year: int) -> Optional[Dict[str, Any]]:
    """Verify the year of a historical event (founding, completion, etc.)."""
    entity_escaped = entity.replace("'", "\\'")

    # Map event types to Wikidata properties
    prop_map = {
        "founded": "P571",  # inception
        "established": "P571",
        "completed": "P571",
        "built": "P571",
        "fell": "P576",  # dissolved
        "ended": "P576",
        "started": "P580",  # start time
        "began": "P580",
    }

    prop = prop_map.get(event_type.lower())
    if not prop:
        return None

    query = f"""
    SELECT ?entityLabel ?date WHERE {{
      ?entity rdfs:label "{entity_escaped}"@en .
      ?entity wdt:{prop} ?date .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }} LIMIT 3
    """
    results = await _sparql_query(query)
    if not results:
        return None

    for r in results:
        date_str = r.get("date", {}).get("value", "")
        if date_str:
            actual_year = int(date_str[:4]) if len(date_str) >= 4 else None
            if actual_year:
                if actual_year == claimed_year:
                    return {
                        "verdict": "supported",
                        "evidence": f"{entity} {event_type} in {actual_year}.",
                        "source": "Wikidata",
                    }
                else:
                    return {
                        "verdict": "contradicted",
                        "evidence": f"{entity} {event_type} in {actual_year}, not {claimed_year}.",
                        "source": "Wikidata",
                    }
    return None
