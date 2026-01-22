"""add_credit_system

Revision ID: e5f8a9b3c1f3
Revises: d5f8a9b3c1e2
Create Date: 2026-01-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f8a9b3c1f3'
down_revision: Union[str, Sequence[str], None] = 'add_mineru_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Add credits_charged to review_tasks
    op.add_column('review_tasks', sa.Column('credits_charged', sa.Integer(), nullable=False, server_default='0'))

    # 1. Create usage_logs table if not exists
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.usage_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL, -- Weak reference if auth.users is not accessible
        app_id TEXT,
        feature_name TEXT,
        credits_consumed INTEGER,
        metadata JSONB DEFAULT '{}',
        consumed_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # 2. Add validation/indexes if possible
    # We skip strict FK to auth.users in Alembic if running as non-superuser 
    # or if schemas are separated, but typically Supabase handles this.
    # Provided SQL assumed references auth.users(id).
    
    # 3. Create deduct_credits function
    op.execute("""
create or replace function public.deduct_credits(
  p_user_id uuid,
  p_cost_amount int,
  p_app_id text,
  p_feature_name text,
  p_metadata jsonb
)
returns json
language plpgsql
security definer
as $$
declare
  v_sub_bal int;
  v_topup_bal int;
  v_remaining_cost int;
  v_total_bal int;
begin
  -- 1. Lock row and read balance
  select subscription_credits, topup_credits 
  into v_sub_bal, v_topup_bal
  from public.profiles
  where id = p_user_id
  for update;

  -- User not found
  if not found then
    return json_build_object('success', false, 'message', '用户不存在');
  end if;

  v_total_bal := v_sub_bal + v_topup_bal;

  -- 2. Check balance
  if v_total_bal < p_cost_amount then
    return json_build_object('success', false, 'message', '余额不足');
  end if;

  -- 3. Deduction logic
  v_remaining_cost := p_cost_amount;

  if v_sub_bal >= v_remaining_cost then
    -- Scenario A: Subscription credits sufficient
    update public.profiles 
    set subscription_credits = subscription_credits - v_remaining_cost,
        updated_at = now()
    where id = p_user_id;
  else
    -- Scenario B: Subscription credits insufficient
    v_remaining_cost := v_remaining_cost - v_sub_bal;
    update public.profiles 
    set subscription_credits = 0,
        topup_credits = topup_credits - v_remaining_cost,
        updated_at = now()
    where id = p_user_id;
  end if;

  -- 4. Log usage
  insert into public.usage_logs (
    user_id, 
    credits_consumed, 
    app_id, 
    feature_name, 
    metadata
  )
  values (
    p_user_id, 
    p_cost_amount, 
    p_app_id, 
    p_feature_name, 
    p_metadata
  );

  return json_build_object(
    'success', true, 
    'new_balance', (v_total_bal - p_cost_amount)
  );
end;
$$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.deduct_credits(uuid, int, text, text, jsonb);")
    # We might choose NOT to drop the table to separate data from code,
    # but strictly speaking downgrade should reverse upgrade.
    op.execute("DROP TABLE IF EXISTS public.usage_logs;")
    
    op.drop_column('review_tasks', 'credits_charged')