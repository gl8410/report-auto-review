# Credit System Integration Plan

## Executive Summary

This plan outlines the integration of the Credit System into the Report Review Lite application. The system simplifies credit management by centrally enforcing deduction logic via Supabase RPC functions and tracking usage in the `usage_logs` table.

**Key Requirements:**
1.  **Chargeable Action**: Only "Start Review Task" incurs a cost. All other operations (uploads, rule management, etc.) are free.
2.  **Data Storage**: All usage history is stored in Supabase (`usage_logs`). No usage history is stored in the local application database.
3.  **Mechanism**: Uses a transactional `deduct_credits` RPC function in Supabase to handle balance checks, deductions, and logging atomically.

## 1. Credit Pricing Strategy

### 1.1 Chargeable Operations

| Operation | Cost Formula | Description | Refund Policy |
|-----------|--------------|-------------|---------------|
| **Start Review Task** | `1 credit` × `rule_count` | Charged when task starts processing. Requires user confirmation. | Full refund if task fails in PENDING status |

### 1.2 Free Operations (No Charge)
- Document Uploads
- Rule Management (Add, Edit, Delete)
- Rule File Upload / CSV Import
- PDF Report Generation
- Viewing Results

## 2. Database Schema (Supabase)

### 2.1 Usage Logs Table
**Table**: `public.usage_logs`

Stores the history of all credit consumptions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary Key |
| `user_id` | UUID | Foreign Key to `auth.users` |
| `app_id` | Text | Application ID |
| `feature_name` | Text | Feature identifier (e.g., `start_review`) |
| `credits_consumed` | Integer | Amount deducted (negative for refunds) |
| `metadata` | JSONB | Context data |
| `consumed_at` | Timestamptz | Transaction time (Default: `now()`) |

### 2.2 User Profiles (Existing)

Existing `public.profiles` table contains:
- `subscription_credits`: Integer (Gifted balance)
- `topup_credits`: Integer (Purchased balance)

## 3. Database Functions

### 3.1 `deduct_credits` RPC Function

This PL/pgSQL function handles the atomic deduction and logging logic.

```sql
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
  -- 1. 锁定行并读取当前余额 (For Update 防止并发扣款)
  select subscription_credits, topup_credits 
  into v_sub_bal, v_topup_bal
  from public.profiles
  where id = p_user_id
  for update;

  -- 假如用户不存在
  if not found then
    return json_build_object('success', false, 'message', '用户不存在');
  end if;

  v_total_bal := v_sub_bal + v_topup_bal;

  -- 2. 检查余额是否足够
  if v_total_bal < p_cost_amount then
    return json_build_object('success', false, 'message', '余额不足');
  end if;

  -- 3. 执行扣费逻辑 (混合扣费: 先扣赠送，再扣充值)
  v_remaining_cost := p_cost_amount;

  if v_sub_bal >= v_remaining_cost then
    -- 场景A: 赠送积分足够支付全额
    update public.profiles 
    set subscription_credits = subscription_credits - v_remaining_cost,
        updated_at = now()
    where id = p_user_id;
  else
    -- 场景B: 赠送积分不够，先扣光赠送，剩下扣充值
    v_remaining_cost := v_remaining_cost - v_sub_bal;
    update public.profiles 
    set subscription_credits = 0,
        topup_credits = topup_credits - v_remaining_cost,
        updated_at = now()
    where id = p_user_id;
  end if;

  -- 4. 自动写入消费日志 (写入新的 usage_logs 表)
  -- 注意: consumed_at 默认是 now()，无需手动传
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
```

## 4. Backend Service Layer

### 4.1 CreditService Implementation
**File**: `backend/backend/services/credit_service.py`

Calls the Supabase RPC function.

```python
class CreditService:
    @staticmethod
    async def deduct_credits(
        user_id: str,
        cost: int,
        app_id: str,
        feature: str,
        metadata: dict = None
    ) -> dict:
        """
        Executes deduction via Supabase RPC.
        """
        # ... logic to call rpc 'deduct_credits' ...
        # Maps python args to SQL params:
        # p_user_id=user_id, p_cost_amount=cost, etc.
        pass

    @staticmethod
    async def refund_credits(
        user_id: str,
        amount: int,
        app_id: str,
        feature: str,
        metadata: dict = None
    ) -> dict:
        """
        Refunds credits by calling deduct_credits with negative cost.
        """
        return await CreditService.deduct_credits(
             user_id, 
             -amount, 
             app_id, 
             feature, 
             metadata
        )
```

## 5. Integration Points

### 5.1 Review Service (Only Charge Point)
**File**: `backend/backend/services/review_service.py`

1.  **On Task Creation (Start Review)**:
    *   Calculate cost: `cost = len(rules)`
    *   Call `CreditService.deduct_credits(...)`
    *   If successful: Proceed to create task.
    *   If failed: Abort and return error (402 Payment Required).

2.  **Refund Logic (Background)**:
    *   If a task fails while in `PENDING` state (and credits were charged):
    *   Call `CreditService.refund_credits(...)`.

### 5.2 Document & Rule Services
*   **No changes required**. No credit deduction logic will be added to these services.

## 6. Frontend Integration

### 6.1 Review Engine
*   **Pre-check**: Before submitting a review task, calculate estimated cost (`1 credit` × `rule_count`).
*   **Confirmation Dialog**:
    -   Display message in Chinese: "本次审查将消耗 **X** 积分 (1积分/每条规则)，是否继续？"
    -   User must click "Confirm" to proceed.
    -   Only after confirmation is the request sent to the backend to start the task and deduct credits.
*   **Error Handling**: Handle 402 Error (Insufficient Funds) by prompting users to recharge.

## 7. Migration & Setup

1.  **Supabase Setup**:
    *   Ensure `usage_logs` table exists.
    *   Deploy `deduct_credits` function.
2.  **Environment Variables**:
    *   `SUPABASE_SERVICE_ROLE_KEY`: Required for executing RPC securely.
    *   `APP_ID`: Configuration value (e.g., `report_review_lite`).
3.  **Code Changes**:
    *   Add `CreditService`.
    *   Modify `ReviewService` to inject credit check logic.
