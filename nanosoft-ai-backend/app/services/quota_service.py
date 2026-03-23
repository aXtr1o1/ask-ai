"""
Quota Fallback Service
Handles direct database queries when AI quota is exceeded
"""
import logging
import re
import json
from typing import Optional, Tuple, Dict, Any

from app.api.models.schemas import AssetRequest, PPMRequest, BDMRequest
from app.api.routes.assets import get_assets
from app.api.routes.ppm import get_ppm
from app.api.routes.bdm import get_bdm
from fastapi import HTTPException
from app.tools.facility_tools import getTime

logger = logging.getLogger("quota_fallback_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


class QuotaFallbackService:
    """
    Service to handle queries when AI quota is exceeded.
    Shows user a menu to choose which table to query.
    """
    
    # Keywords to detect query type
    ASSET_KEYWORDS = ["asset", "assets", "equipment"]
    PPM_KEYWORDS = ["ppm", "preventive", "maintenance", "planned"]
    BDM_KEYWORDS = ["bdm", "breakdown", "complaint", "complaints", "reactive"]
    
    def __init__(self):
        logger.info("🔄 QuotaFallbackService initialized")
    
    def is_quota_error(self, error: Exception) -> bool:
        """
        Treat ANY model failure as a fallback trigger.
        This covers: quota exceeded, token limit, timeout,
        internal model errors, network failures, etc.
        """
        error_str = str(error).lower()
        logger.warning(f"⚠️ Model failure detected — triggering fallback: {error_str[:120]}")
        return True
    
    def get_quota_exceeded_message(self) -> str:
        """
        Return the message asking user which table they want.
        
        Returns:
            str: Message to display to user
        """
        message = (
            "⚠️ **AI Quota Exceeded**\n\n"
            "Your AI usage quota has been exhausted, but I can still help you view data from **one** of these tables:\n\n"
            "• **Assets** - Equipment and asset information\n"
            "• **PPM** - Preventive maintenance tasks\n"
            "• **BDM** - Breakdown/complaint records\n\n"
            "**Please reply with which table you'd like to see:**\n"
            "Examples:\n"
            "- 'show me assets'\n"
            "- 'give me 50 complaints'\n"
            "- 'list all PPM'\n"
            "- '30 assets'"
        )
        
        logger.info("📋 Quota exceeded message generated")
        return message
    
    def parse_query_type(self, query: str) -> Optional[str]:
        """
        Detect which tool (ASSETS/PPM/BDM) the user is asking about.
        
        Args:
            query: User's query string
            
        Returns:
            str: "ASSETS", "PPM", "BDM", or None
        """
        query_lower = query.lower()
        
        # Check for each type
        if any(keyword in query_lower for keyword in self.ASSET_KEYWORDS):
            logger.info(f"✅ Detected query type: ASSETS")
            return "ASSETS"
        elif any(keyword in query_lower for keyword in self.PPM_KEYWORDS):
            logger.info(f"✅ Detected query type: PPM")
            return "PPM"
        elif any(keyword in query_lower for keyword in self.BDM_KEYWORDS):
            logger.info(f"✅ Detected query type: BDM")
            return "BDM"
        
        logger.warning("⚠️ Could not detect table type from user reply")
        return None
    
    def parse_limit(self, query: str) -> Optional[int]:
        """
        Extract limit from user query.
        Handles: "limit 10", "limit 50", "all", "show me 20 assets"
        
        Args:
            query: User's query string
            
        Returns:
            int: Limit value, or None for "all"
        """
        query_lower = query.lower()
        
        # Check for "all" keyword
        if " all" in query_lower or query_lower.startswith("all "):
            logger.info("📊 Detected 'all' - no limit will be set")
            return None
        
        # Pattern 1: "limit X" or "limit: X"
        limit_match = re.search(r'limit[\s:]+(\d+)', query_lower)
        if limit_match:
            limit = int(limit_match.group(1))
            logger.info(f"📊 Parsed limit from 'limit X': {limit}")
            return limit
        
        # Pattern 2: "show me X assets/ppm/bdm/complaints"
        number_match = re.search(r'(?:show|get|give|fetch|list)[\s\w]*?(\d+)', query_lower)
        if number_match:
            limit = int(number_match.group(1))
            logger.info(f"📊 Parsed limit from 'show X': {limit}")
            return limit
        
        # Pattern 3: Standalone number before keywords
        standalone_match = re.search(r'\b(\d+)\s+(?:asset|ppm|bdm|complaint)', query_lower)
        if standalone_match:
            limit = int(standalone_match.group(1))
            logger.info(f"📊 Parsed limit from standalone number: {limit}")
            return limit
        
        # Default: no limit found
        logger.info("📊 No explicit limit found - fetching ALL records")
        return None
    
    def build_minimal_payload(
        self,
        user_name: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Build minimal payload for database query.
        
        Args:
            user_name: Username for filtering
            limit: Optional limit for results (None = all records)
            
        Returns:
            dict: Minimal payload
        """
        # Use existing getTime function to get default dates (last 7 days)
        date_from, date_to = getTime(None, None)
        
        payload = {
            "user_name": user_name,
            "offset": 0,
            "date_from": date_from,
            "date_to": date_to
        }
        
        # Only add limit if it's not None
        if limit is not None:
            payload["limit"] = limit
            logger.info(f"📊 Limit set to {limit}")
        else:
            logger.info(f"📊 No limit - fetching ALL records")
        
        return payload
    
    def query_database(
        self,
        query_type: str,
        user_name: str,
        limit: Optional[int] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Query database directly based on type.
        
        Args:
            query_type: "ASSETS", "PPM", or "BDM"
            user_name: Username for filtering
            limit: Optional limit for results
            
        Returns:
            tuple: (result_dict, total_count)
        """
        payload = self.build_minimal_payload(user_name, limit)
        
        logger.info(f"🗄️ Querying {query_type} | payload: {payload}")
        
        try:
            if query_type == "ASSETS":
                req = AssetRequest(**payload)
                result = get_assets(req)
            elif query_type == "PPM":
                req = PPMRequest(**payload)
                result = get_ppm(req)
            elif query_type == "BDM":
                req = BDMRequest(**payload)
                result = get_bdm(req)
            else:
                raise ValueError(f"Unknown query type: {query_type}")
            
            # Extract records and count
            p_list = result.get("p_list", [])
            p_count = result.get("p_count", 0)
            
            logger.info(f"✅ Database query successful | records: {len(p_list)} | total: {p_count}")
            
            return result, p_count
            
        except HTTPException as e:
            logger.error(f"❌ Database query failed: {e.detail}")
            raise
        except Exception as e:
            logger.error(f"❌ Database query error: {e}", exc_info=True)
            raise
    
    def format_response(
        self,
        query_type: str,
        result: Dict[str, Any],
        total_count: int,
        limit: Optional[int] = None
    ) -> Tuple[str, str]:
        """
        Format database result into user-friendly response.
        
        Args:
            query_type: "ASSETS", "PPM", or "BDM"
            result: Database query result
            total_count: Total count of records
            limit: Limit used in query
            
        Returns:
            tuple: (final_response_text, context_summary)
        """
        p_list = result.get("p_list", [])
        entity_name = query_type.lower()
        
        if entity_name == "assets":
            entity_display = "assets"
        elif entity_name == "ppm":
            entity_display = "PPM tasks"
        elif entity_name == "bdm":
            entity_display = "complaints"
        else:
            entity_display = "records"
        
        # If no records found
        if total_count == 0:
            context_summary = f"No {entity_display} found."
            final_response = context_summary
            logger.info(f"📭 No records response: {context_summary}")
            return final_response, context_summary
        
        # Build context summary
        if limit and len(p_list) < total_count:
            context_summary = f"Found {total_count} {entity_display} (showing {len(p_list)})."
        else:
            context_summary = f"Found {total_count} {entity_display}."
        
        # Build full response with data
        response_data = {
            "context_summary": context_summary,
            "records": p_list
        }
        
        final_response = json.dumps(response_data)
        
        logger.info(f"✅ List response prepared | records: {len(p_list)} | total: {total_count}")
        
        return final_response, context_summary
    
    def handle_user_table_choice(
        self,
        user_reply: str,
        user_name: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Handle user's reply after quota exceeded message.
        Parse their choice and return data.
        
        Args:
            user_reply: User's reply (e.g., "show me 50 assets")
            user_name: Username for filtering
            
        Returns:
            tuple: (final_response_text, context_summary) or (None, None) if invalid
        """
        logger.info(f"🔄 Handling user table choice | reply: '{user_reply}'")
        
        # Step 1: Parse query type (ASSETS/PPM/BDM)
        query_type = self.parse_query_type(user_reply)
        if not query_type:
            logger.warning("⚠️ Could not determine table type from user reply")
            return None, None
        
        # Step 2: Parse limit
        limit = self.parse_limit(user_reply)
        logger.info(f"✅ Parsed limit: {limit if limit else 'ALL'}")
        
        # Step 3: Query database
        try:
            result, total_count = self.query_database(query_type, user_name, limit)
        except Exception as e:
            logger.error(f"❌ Database query failed: {e}")
            return None, None
        
        # Step 4: Format response
        final_response, context_summary = self.format_response(
            query_type, result, total_count, limit
        )
        
        logger.info(f"✅ Fallback response ready | context: '{context_summary}'")
        
        return final_response, context_summary


# Singleton instance
quota_fallback_service = QuotaFallbackService()