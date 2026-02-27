from typing import Dict, Any, Optional
from app.core.supabase import get_supabase_client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class CreditService:
    @staticmethod
    async def deduct_credits(
        user_id: str,
        cost: int,
        app_id: str,
        feature: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call Supabase deduct_credits RPC function using Service Role Key.
        
        Args:
            user_id: User UUID
            cost: Credits to deduct (positive integer)
            app_id: Application identifier from config
            feature: Feature name from config
            metadata: Additional context (task_id, document_id, etc.)
            
        Returns:
            {
                "success": bool,
                "message": str (if failed),
                "new_balance": int (if succeeded)
            }
            
        Raises:
            Exception: If RPC call fails
        """
        if not settings.ENABLE_CREDIT_SYSTEM:
            return {"success": True, "message": "Credit system disabled"}

        if metadata is None:
            metadata = {}
            
        try:
            # Use Service Role Key for admin access (bypasses RLS)
            supabase = get_supabase_client(use_service_role=True)
            
            # Call RPC function
            # Parameter names must match the PL/pgSQL function signature
            response = supabase.rpc('deduct_credits', {
                'p_user_id': user_id,
                'p_cost_amount': cost,
                'p_app_id': app_id,
                'p_feature_name': feature,
                'p_metadata': metadata
            }).execute()
            
            # Extract result
            result = response.data
            
            if not result.get('success'):
                logger.warning(
                    f"Credit deduction failed for user {user_id}: {result.get('message')}"
                )
                return result
            
            logger.info(
                f"Successfully deducted {cost} credits from user {user_id} "
                f"for {app_id}:{feature}. New balance: {result.get('new_balance')}"
            )
            return result
            
        except Exception as e:
            logger.error(f"Error calling deduct_credits RPC: {e}")
            raise Exception(f"扣费失败: {str(e)}")
    
    @staticmethod
    async def refund_credits(
        user_id: str,
        amount: int,
        app_id: str,
        feature: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Refund credits by calling deduct_credits with negative amount.
        
        Args:
            user_id: User UUID
            amount: Credits to refund (positive integer, will be negated)
            app_id: Application identifier
            feature: Feature name (e.g., "review_task_refund")
            metadata: Additional context
            
        Returns:
            Same as deduct_credits
        """
        if metadata is None:
            metadata = {}
            
        # Add refund flag to metadata
        metadata['refund'] = True
        
        # Call deduct_credits with negative amount
        # Note: We pass the amount as negative to deduct_credits to increase balance
        return await CreditService.deduct_credits(
            user_id=user_id,
            cost=-amount,
            app_id=app_id,
            feature=feature,
            metadata=metadata
        )

    @staticmethod
    async def check_balance(user_id: str) -> int:
        """
        Get current total balance for a user.
        """
        try:
            # Just read profile, service role not strictly needed but safe to use
            supabase = get_supabase_client(use_service_role=True)
            
            response = supabase.table('profiles').select(
                'subscription_credits, topup_credits'
            ).eq('id', user_id).single().execute()
            
            data = response.data
            if not data:
                return 0
                
            return data.get('subscription_credits', 0) + data.get('topup_credits', 0)
            
        except Exception as e:
            logger.error(f"Error checking balance for user {user_id}: {e}")
            return 0