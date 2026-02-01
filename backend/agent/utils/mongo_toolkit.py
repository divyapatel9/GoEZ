"""
MongoDB toolkit with custom tools for health data queries.
Provides reliable tools for querying health data from MongoDB.
"""

from typing import List, Optional, Any, Dict
from langchain_core.tools import BaseTool, tool
from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field
from pymongo import MongoClient
from datetime import datetime, timedelta
import json

from ..config import settings

# Global client cache
_mongo_client = None

def get_mongo_client() -> MongoClient:
    """Get or create MongoDB client."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(settings.mongodb_uri)
    return _mongo_client


def get_collection(collection_name: str):
    """Get a MongoDB collection."""
    client = get_mongo_client()
    db = client[settings.mongodb_database]
    return db[collection_name]


class QueryHealthDataInput(BaseModel):
    """Input for querying health data."""
    metric_path: str = Field(description="Dot-notation path to the metric, e.g., 'activity.steps', 'sleep.sleep_hours', 'recovery.heart_rate_bpm.avg'")
    days: int = Field(default=7, description="Number of days to look back")
    

class AggregateHealthDataInput(BaseModel):
    """Input for aggregating health data."""
    metric_path: str = Field(description="Dot-notation path to the metric, e.g., 'activity.steps', 'sleep.sleep_hours'")
    days: int = Field(default=7, description="Number of days to look back")
    operation: str = Field(default="avg", description="Aggregation operation: 'avg', 'sum', 'min', 'max', 'count'")


def create_health_tools(collection_name: str) -> List[BaseTool]:
    """
    Create custom health data query tools for a collection.
    
    Args:
        collection_name: Name of the MongoDB collection
        
    Returns:
        List of LangChain tools
    """
    
    @tool
    def get_health_data(metric_path: str, days: int = 7) -> str:
        """
        Get health data for a specific metric over a time period.
        
        Args:
            metric_path: Dot-notation path like 'activity.steps', 'sleep.sleep_hours', 'recovery.heart_rate_bpm.avg'
            days: Number of days to look back (default 7)
            
        Returns:
            JSON string with daily values for the metric
        """
        try:
            coll = get_collection(collection_name)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_str = start_date.strftime("%Y-%m-%d")
            
            # Query documents
            cursor = coll.find(
                {"date": {"$gte": start_str}},
                {"date": 1, metric_path: 1, "_id": 0}
            ).sort("date", -1).limit(days)
            
            results = []
            for doc in cursor:
                # Extract nested field value
                value = doc
                for key in metric_path.split("."):
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break
                
                results.append({
                    "date": doc.get("date"),
                    "value": value
                })
            
            if not results:
                return json.dumps({"error": "No data found for the specified period", "metric": metric_path, "days": days})
            
            return json.dumps({"metric": metric_path, "days": days, "data": results}, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @tool
    def aggregate_health_metric(metric_path: str, days: int = 7, operation: str = "avg") -> str:
        """
        Calculate aggregate statistics for a health metric.
        
        Args:
            metric_path: Dot-notation path like 'activity.steps', 'sleep.sleep_hours'
            days: Number of days to look back (default 7)
            operation: 'avg', 'sum', 'min', 'max', or 'count'
            
        Returns:
            JSON string with the aggregated result
        """
        try:
            coll = get_collection(collection_name)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_str = start_date.strftime("%Y-%m-%d")
            
            # Build aggregation pipeline
            op_map = {
                "avg": "$avg",
                "sum": "$sum", 
                "min": "$min",
                "max": "$max",
                "count": "$sum"
            }
            
            mongo_op = op_map.get(operation, "$avg")
            field_ref = f"${metric_path}"
            
            pipeline = [
                {"$match": {"date": {"$gte": start_str}}},
                {"$group": {
                    "_id": None,
                    "result": {mongo_op: field_ref if operation != "count" else 1},
                    "count": {"$sum": 1}
                }}
            ]
            
            results = list(coll.aggregate(pipeline))
            
            if not results:
                return json.dumps({"error": "No data found", "metric": metric_path, "days": days})
            
            result = results[0]
            return json.dumps({
                "metric": metric_path,
                "operation": operation,
                "days": days,
                "result": result.get("result"),
                "data_points": result.get("count")
            }, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @tool
    def get_schema_info() -> str:
        """
        Get the schema/structure of health data documents.
        
        Returns:
            JSON string describing available fields in the health data
        """
        try:
            coll = get_collection(collection_name)
            doc = coll.find_one()
            
            if not doc:
                return json.dumps({"error": "No documents found"})
            
            def get_structure(obj, prefix=""):
                """Recursively get structure of nested documents."""
                structure = {}
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == "_id":
                            continue
                        full_key = f"{prefix}.{key}" if prefix else key
                        if isinstance(value, dict):
                            structure[full_key] = "object"
                            structure.update(get_structure(value, full_key))
                        elif isinstance(value, list):
                            structure[full_key] = "array"
                        elif isinstance(value, (int, float)):
                            structure[full_key] = "number"
                        elif isinstance(value, str):
                            structure[full_key] = "string"
                        elif isinstance(value, bool):
                            structure[full_key] = "boolean"
                        else:
                            structure[full_key] = type(value).__name__
                return structure
            
            schema = get_structure(doc)
            return json.dumps({
                "collection": collection_name,
                "fields": schema,
                "sample_date": doc.get("date")
            }, default=str)
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @tool
    def get_date_range() -> str:
        """
        Get the date range of available health data.
        
        Returns:
            JSON string with earliest and latest dates
        """
        try:
            coll = get_collection(collection_name)
            
            # Get earliest
            earliest = coll.find_one(sort=[("date", 1)])
            # Get latest
            latest = coll.find_one(sort=[("date", -1)])
            
            return json.dumps({
                "collection": collection_name,
                "earliest_date": earliest.get("date") if earliest else None,
                "latest_date": latest.get("date") if latest else None,
                "total_documents": coll.count_documents({})
            })
            
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    return [get_health_data, aggregate_health_metric, get_schema_info, get_date_range]


def get_mongo_tools(collection_name: str, llm: BaseLanguageModel = None) -> List[BaseTool]:
    """
    Get MongoDB tools for a collection.
    
    Args:
        collection_name: Name of the MongoDB collection
        llm: Language model (not used, kept for API compatibility)
    
    Returns:
        List of LangChain tools for querying the collection
    """
    return create_health_tools(collection_name)


def get_mongodb_system_prompt(top_k: int = 5) -> str:
    """
    Get a system prompt for MongoDB health data analysis.
    
    Returns:
        Formatted system prompt string
    """
    return """You are a health data analyst with access to MongoDB tools.

Available tools:
1. get_health_data - Get raw daily values for a metric (e.g., activity.steps, sleep.sleep_hours)
2. aggregate_health_metric - Calculate avg/sum/min/max for a metric over time
3. get_schema_info - See what fields are available in the data
4. get_date_range - Check what date range of data exists

Common metric paths:
- activity.steps - Daily step count
- sleep.sleep_hours - Hours of sleep
- sleep.asleep_seconds - Sleep duration in seconds
- recovery.heart_rate_bpm.avg - Average heart rate
- recovery.hrv - Heart rate variability
- body.weight - Body weight

Always start by checking the schema if unsure about field names."""
