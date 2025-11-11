"""
Supabase HTTP Client
Direct HTTP calls to Supabase PostgREST API using httpx
"""

import httpx
from typing import Optional, Dict, Any, List
from fastapi import HTTPException
from app.db import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY
import datetime
from decimal import Decimal


def sanitize_for_post(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_post(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_post(v) for v in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    else:
        return obj


class SupabaseHTTPClient:
    """
    HTTP client for Supabase PostgREST API.
    
    Uses httpx for async HTTP requests directly to PostgREST endpoints.
    Supports both user-scoped (with JWT) and admin (service role) operations.
    """
    
    def __init__(self, token: Optional[str] = None, is_admin: bool = False):
        """
        Initialize Supabase HTTP client.
        
        Args:
            token: Optional user JWT token for RLS enforcement
            is_admin: If True, use service role key (bypasses RLS)
        """
        self.base_url = f"{SUPABASE_URL}/rest/v1"
        
        # Determine which API key to use
        api_key = SUPABASE_SERVICE_KEY if is_admin else SUPABASE_ANON_KEY
        
        # Set headers
        self.headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation"  # Return created/updated records
        }
        
        # Set Authorization header
        if is_admin:
            # Admin uses service role key for auth
            self.headers["Authorization"] = f"Bearer {SUPABASE_SERVICE_KEY}"
        elif token:
            # User routes use provided JWT
            self.headers["Authorization"] = f"Bearer {token}"
        else:
            # Anonymous uses anon key
            self.headers["Authorization"] = f"Bearer {SUPABASE_ANON_KEY}"
    
    async def select(
        self, 
        table: str, 
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        SELECT query on a table.
        
        Args:
            table: Table name
            columns: Columns to select (default: "*")
            filters: Filter conditions (e.g., {"id": "eq.123", "status": "eq.active"})
            order: Order by (e.g., "created_at.desc")
            limit: Limit results
            offset: Offset results
        
        Returns:
            List of records
        """
        url = f"{self.base_url}/{table}"
        
        params = {"select": columns}
        
        if filters:
            params.update(filters)
        
        if order:
            params["order"] = order
        
        if limit:
            params["limit"] = limit
        
        if offset:
            params["offset"] = offset
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Supabase error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
    
    async def select_one(
        self,
        table: str,
        id_value: str,
        id_column: str = "id",
        columns: str = "*"
    ) -> Optional[Dict[str, Any]]:
        """
        SELECT a single record by ID.
        
        Args:
            table: Table name
            id_value: ID value
            id_column: ID column name (default: "id")
            columns: Columns to select
        
        Returns:
            Single record or None
        """
        filters = {id_column: f"eq.{id_value}"}
        results = await self.select(table, columns=columns, filters=filters, limit=1)
        return results[0] if results else None
    
    async def insert(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        INSERT a record.
        
        Args:
            table: Table name
            data: Record data
        
        Returns:
            Created record
        """
        url = f"{self.base_url}/{table}"
        data = sanitize_for_post(data)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=data)
                response.raise_for_status()
                result = response.json()
                return result[0] if isinstance(result, list) and result else result
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Supabase error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")
    
    async def update(
        self,
        table: str,
        id_value: str,
        data: Dict[str, Any],
        id_column: str = "id"
    ) -> Dict[str, Any]:
        """
        UPDATE a record by ID.
        
        Args:
            table: Table name
            id_value: ID value
            data: Updated data
            id_column: ID column name
        
        Returns:
            Updated record
        """
        url = f"{self.base_url}/{table}"
        params = {id_column: f"eq.{id_value}"}
        data = sanitize_for_post(data)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(url, headers=self.headers, params=params, json=data)
                response.raise_for_status()
                result = response.json()
                return result[0] if isinstance(result, list) and result else result
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Supabase error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
    
    async def delete(
        self,
        table: str,
        id_value: str,
        id_column: str = "id"
    ) -> bool:
        """
        DELETE a record by ID.
        
        Args:
            table: Table name
            id_value: ID value
            id_column: ID column name
        
        Returns:
            True if successful
        """
        url = f"{self.base_url}/{table}"
        params = {id_column: f"eq.{id_value}"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(url, headers=self.headers, params=params)
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Supabase error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
    
    async def count(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        COUNT records in a table.
        
        Args:
            table: Table name
            filters: Optional filter conditions
        
        Returns:
            Count of records
        """
        url = f"{self.base_url}/{table}"
        
        # Add Prefer header for count
        headers = {**self.headers, "Prefer": "count=exact"}
        params = {"select": "id"}  # Minimal select for count
        
        if filters:
            params.update(filters)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(url, headers=headers, params=params)
                response.raise_for_status()
                
                # Get count from Content-Range header
                content_range = response.headers.get("content-range", "")
                if "/" in content_range:
                    return int(content_range.split("/")[1])
                return 0
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Count failed: {str(e)}")
