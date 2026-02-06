"""OpenSearch Tools for log analysis and observability.

Allows agents to query logs from the centralized OpenSearch cluster.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from langchain_core.tools import tool
from opensearchpy import OpenSearch, RequestsHttpConnection

from src.config import get_settings

logger = logging.getLogger(__name__)

def get_opensearch_client() -> Optional[OpenSearch]:
    """Get authenticated OpenSearch client."""
    settings = get_settings()
    
    if not settings.opensearch_url:
        logger.warning("OpenSearch URL not configured.")
        return None
        
    try:
        auth = (settings.opensearch_username, settings.opensearch_password)
        
        # Initialize client
        client = OpenSearch(
            hosts=[settings.opensearch_url],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30
        )
        return client
    except Exception as e:
        logger.error(f"Failed to create OpenSearch client: {e}")
        return None

@tool
async def search_logs(query: str, time_range: str = "1h", limit: int = 20) -> str:
    """Search application logs in OpenSearch (Dev/Stage clusters).
    
    Use this tool to investigate errors, check system status, or trace transaction IDs.
    
    Args:
        query: Lucene query string (e.g., 'level:ERROR AND service:login', 'trace_id:abc-123').
        time_range: Lookback period. Supported values: '15m', '1h', '6h', '24h', '7d'.
        limit: Maximum number of log entries to return (default 20, max 50).
    """
    logger.info(f"Tool invoked: search_logs(query={query}, time_range={time_range}, limit={limit})")
    
    settings = get_settings()
    client = get_opensearch_client()
    
    if not client:
        return "Error: OpenSearch is not configured on this bot instance."
    
    # Calculate time range
    now = datetime.utcnow()
    if time_range == "15m":
        start_time = now - timedelta(minutes=15)
    elif time_range == "1h":
        start_time = now - timedelta(hours=1)
    elif time_range == "6h":
        start_time = now - timedelta(hours=6)
    elif time_range == "24h":
        start_time = now - timedelta(hours=24)
    elif time_range == "7d":
        start_time = now - timedelta(days=7)
    else:
        return f"Error: Invalid time_range '{time_range}'. Use 15m, 1h, 6h, 24h, or 7d."
        
    # Construct Query DSL
    dsl = {
        "size": min(limit, 50),
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {
            "bool": {
                "must": [
                    {"query_string": {"query": query}},
                    {"range": {
                        "@timestamp": {
                            "gte": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                            "lte": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                            "format": "strict_date_optional_time"
                        }
                    }}
                ]
            }
        }
    }
    
    try:
        # Run search in thread
        response = await asyncio.to_thread(
            client.search,
            body=dsl,
            index=settings.opensearch_index_pattern
        )
        
        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            return f"No logs found for query '{query}' in the last {time_range}."
            
        # Format results
        result_lines = []
        for hit in hits:
            source = hit.get("_source", {})
            ts = source.get("@timestamp", "N/A")
            level = source.get("level", "INFO")
            msg = source.get("log", source.get("message", ""))
            service = source.get("kubernetes", {}).get("labels", {}).get("app", "unknown")
            
            # Truncate long messages
            if len(msg) > 300:
                msg = msg[:300] + "..."
                
            result_lines.append(f"[{ts}] {level} ({service}): {msg}")
            
        return "\n".join(result_lines)
        
    except Exception as e:
        logger.error(f"OpenSearch query failed: {e}")
        return f"Error executing search: {e}"

# Export tool list
ALL_OPENSEARCH_TOOLS = [search_logs]
