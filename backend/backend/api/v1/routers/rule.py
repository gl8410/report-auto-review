import io
import csv
from collections import defaultdict
from typing import List, Optional, Dict
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, or_
from backend.api.deps import get_session, get_current_user
from backend.models.user import Profile
from backend.models.rule import RuleGroup, Rule
from backend.models.review import ReviewTask, ReviewResultItem
from backend.models.comparison import ComparisonResult
from backend.schemas.rule import (
    RuleGroupCreate, RuleGroupResponse,
    RuleCreate, RuleResponse, RuleUpdate
)
from backend.integrations.llm_client import parse_rules_from_text
from backend.services.document_service import extract_text_from_file
from backend.core.config import settings

router = APIRouter()

# Valid values for rule fields
VALID_REVIEW_TYPES = ["内容完整性", "计算结果准确性", "禁止条款", "前后逻辑一致性", "措施遵从性", "计算正确性"]
VALID_RISK_LEVELS = ["低风险", "中风险", "高风险"]

# ============== Rule Group Endpoints ==============

def build_group_tree_response_in_memory(
    group: RuleGroup,
    children_map: Dict[str, List[RuleGroup]]
) -> RuleGroupResponse:
    """
    Recursively build RuleGroupResponse from pre-fetched data.
    """
    # Build children recursively from map
    children_dtos = []
    if group.id in children_map:
        # Sort children by creation time (newest first)
        sorted_children = sorted(children_map[group.id], key=lambda x: x.created_at, reverse=True)
        for child in sorted_children:
            children_dtos.append(build_group_tree_response_in_memory(child, children_map))

    # Construct Response Model
    return RuleGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        type=group.type,
        parent_id=group.parent_id,
        created_at=group.created_at,
        children=children_dtos
    )

@router.get("/rule-groups", response_model=List[RuleGroupResponse])
def get_rule_groups(
    session: Session = Depends(get_session),
    current_user: Profile = Depends(get_current_user)
):
    """Get all rule groups (hierarchical tree, top-level only), ensuring security visibility recursively."""
    # 1. Fetch ALL groups visible to the user in a single query
    query = select(RuleGroup).where(
        or_(
            RuleGroup.owner_id == str(current_user.id),
            RuleGroup.type == "public",
            RuleGroup.owner_id == None
        )
    )
    all_groups = session.exec(query).all()

    # 2. Build adjacency list (children map) and find roots
    children_map = defaultdict(list)
    root_groups = []
    
    # Create a set of accessible IDs for O(1) lookup
    accessible_ids = {g.id for g in all_groups}
    
    for group in all_groups:
        if group.parent_id and group.parent_id in accessible_ids:
            children_map[group.parent_id].append(group)
        else:
            # It's a root if it has no parent OR its parent is not accessible
            root_groups.append(group)
            
    # 3. Sort roots
    root_groups.sort(key=lambda x: x.created_at, reverse=True)

    # 4. Build response tree
    response_groups = []
    for group in root_groups:
        response_groups.append(build_group_tree_response_in_memory(group, children_map))
            
    return response_groups

@router.post("/rule-groups", response_model=RuleGroupResponse)
def create_rule_group(
    data: RuleGroupCreate,
    session: Session = Depends(get_session),
    current_user: Profile = Depends(get_current_user)
):
    """Create a new rule group."""
    if data.parent_id:
        parent = session.get(RuleGroup, data.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent rule group not found")

    group = RuleGroup(
        name=data.name,
        description=data.description,
        parent_id=data.parent_id,
        type=data.type,
        owner_id=str(current_user.id)
    )
    session.add(group)
    session.commit()
    session.refresh(group)
    return group

@router.get("/rule-groups/{group_id}", response_model=RuleGroupResponse)
def get_rule_group(group_id: str, session: Session = Depends(get_session)):
    """Get a specific rule group."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")
    return group

@router.put("/rule-groups/{group_id}", response_model=RuleGroupResponse)
def update_rule_group(
    group_id: str,
    data: RuleGroupCreate,
    session: Session = Depends(get_session),
    current_user: Profile = Depends(get_current_user)
):
    """Update a rule group."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")
    
    # Check permission: Allow if owner OR has no owner(legacy) OR is public
    is_owner = str(current_user.id) == group.owner_id
    is_legacy = group.owner_id is None
    is_public = group.type == "public"
    
    if not (is_owner or is_legacy or is_public):
        raise HTTPException(status_code=403, detail="Not authorized to update this group")

    group.name = data.name
    if data.description is not None:
        group.description = data.description
    
    # Update type if provided (assuming RuleGroupCreate has type now)
    if data.type is not None:
        group.type = data.type

    # Allow moving group to another parent
    if data.parent_id is not None:
         # Prevent circular reference
        if data.parent_id == group_id:
             raise HTTPException(status_code=400, detail="Cannot set parent to self")
        # Check if new parent exists
        parent = session.get(RuleGroup, data.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent rule group not found")
        group.parent_id = data.parent_id
        
    session.add(group)
    session.commit()
    session.refresh(group)
    return group

from sqlmodel import delete

def delete_group_recursive(session: Session, group: RuleGroup):
    """Recursively delete a group and its children using bulk operations."""
    print(f"Deleting group tree starting at: {group.name} ({group.id})")
    
    # 1. Get all descendant group IDs (plus the current group)
    all_group_ids = get_child_group_ids(session, group.id)
    # get_child_group_ids returns descendants including root? No, check implementation.
    # Implementation says: ids = [root_group_id], then bfs. So yes.
    
    print(f"Found {len(all_group_ids)} groups to delete.")
    
    if not all_group_ids:
        return

    # 2. Find all tasks associated with these groups
    # We need to chunk this if there are too many groups (SQLite limit is 999 vars)
    # But usually < 1000 groups in a deletion is safe. If not, we should loop.
    # For robust production code, chunking is better.
    
    chunk_size = 500
    for i in range(0, len(all_group_ids), chunk_size):
        chunk = all_group_ids[i:i + chunk_size]
        
        # 2.1 Delete Rules (Bulk)
        # Using sqlmodel delete statement
        session.exec(delete(Rule).where(Rule.group_id.in_(chunk)))
        
        # 2.2 Find Task IDs to delete results
        tasks = session.exec(select(ReviewTask.id).where(ReviewTask.rule_group_id.in_(chunk))).all()
        
        if tasks:
            task_ids = list(tasks)
            # Delete Review Results
            for k in range(0, len(task_ids), chunk_size):
                t_chunk = task_ids[k:k+chunk_size]
                # ReviewResultItems
                session.exec(delete(ReviewResultItem).where(ReviewResultItem.task_id.in_(t_chunk)))
                # ComparisonResults
                try:
                     session.exec(delete(ComparisonResult).where(ComparisonResult.task_id.in_(t_chunk)))
                except Exception as e:
                     print(f"Error deleting comparison results: {e}")

            # Delete Tasks
            session.exec(delete(ReviewTask).where(ReviewTask.id.in_(task_ids)))

        # 2.3 Delete Groups
        session.exec(delete(RuleGroup).where(RuleGroup.id.in_(chunk)))
        
    print(f"Bulk deletion completed.")

@router.delete("/rule-groups/{group_id}")
def delete_rule_group(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: Profile = Depends(get_current_user)
):
    """Delete a rule group and all its sub-groups and rules."""
    print(f"Request to delete rule group: {group_id}")
    try:
        group = session.get(RuleGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Rule group not found")
        
        # Check permission: owner or legacy
        if group.owner_id and group.owner_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to delete this group")

        delete_group_recursive(session, group)
        session.commit()
        print("Deletion successful")
        return {"message": "Rule group and all sub-groups deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in delete_rule_group: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def get_child_group_ids(session: Session, root_group_id: str) -> List[str]:
    """Recursively get all child group IDs using in-memory traversal to avoid N+1 queries."""
    # Fetch all parent-child relationships, selecting ONLY id and parent_id
    results = session.exec(select(RuleGroup.id, RuleGroup.parent_id)).all()
    
    # Build adjacency list
    children_map = defaultdict(list)
    for g_id, p_id in results:
        if p_id:
            children_map[p_id].append(g_id)
            
    # BFS to finding all descendants
    ids = [root_group_id]
    queue = [root_group_id]
    
    while queue:
        current_id = queue.pop(0)
        if current_id in children_map:
            children = children_map[current_id]
            ids.extend(children)
            queue.extend(children)
            
    return ids

# ============== Rule Endpoints ==============

@router.get("/rule-groups/{group_id}/rules", response_model=List[RuleResponse])
def get_rules(group_id: str, recursive: bool = False, session: Session = Depends(get_session)):
    """Get all rules in a group (optionally recursive)."""
    if recursive:
        group_ids = get_child_group_ids(session, group_id)
        rules = session.exec(select(Rule).where(Rule.group_id.in_(group_ids))).all()
    else:
        rules = session.exec(select(Rule).where(Rule.group_id == group_id)).all()
    return rules

@router.post("/rule-groups/{group_id}/rules", response_model=RuleResponse)
def create_rule(group_id: str, data: RuleCreate, session: Session = Depends(get_session), current_user: Profile = Depends(get_current_user)):
    """Create a new rule in a group."""
    # Verify group exists
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    # Validate review_type and importance
    if data.review_type and data.review_type not in VALID_REVIEW_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid review_type. Must be one of: {VALID_REVIEW_TYPES}")
    if data.risk_level not in VALID_RISK_LEVELS:
        raise HTTPException(status_code=400, detail=f"Invalid risk_level. Must be one of: {VALID_RISK_LEVELS}")

    rule = Rule(
        group_id=group_id,
        clause_number=data.clause_number,
        content=data.content,
        standard_name=data.standard_name,
        review_type=data.review_type,
        risk_level=data.risk_level
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule

@router.put("/rules/{rule_id}", response_model=RuleResponse)
def update_rule(rule_id: str, data: RuleUpdate, session: Session = Depends(get_session)):
    """Update a rule."""
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if data.clause_number is not None:
        rule.clause_number = data.clause_number
    if data.content is not None:
        rule.content = data.content
    if data.standard_name is not None:
        rule.standard_name = data.standard_name
    if data.review_type is not None:
        if data.review_type not in VALID_REVIEW_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid review_type. Must be one of: {VALID_REVIEW_TYPES}")
        rule.review_type = data.review_type
    if data.risk_level is not None:
        if data.risk_level not in VALID_RISK_LEVELS:
            raise HTTPException(status_code=400, detail=f"Invalid risk_level. Must be one of: {VALID_RISK_LEVELS}")
        rule.risk_level = data.risk_level

    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule

@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, session: Session = Depends(get_session)):
    """Delete a rule."""
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
    return {"message": "Rule deleted"}

# ============== File Upload & LLM Parsing ==============

async def process_uploaded_rules(group_id: str, content: str, filename: str, session: Session, current_user_id: str) -> int:
    """Background task to parse rules from uploaded file using LLM."""
    try:
        parsed = await parse_rules_from_text(content, filename)

        if not parsed.rules:
            raise ValueError("未能从文件中解析出任何规则")

        # Create rules from parsed data
        for parsed_rule in parsed.rules:
            rule = Rule(
                group_id=group_id,
                clause_number=parsed_rule.clause_number,
                content=parsed_rule.content,
                standard_name=parsed.standard_name,
                review_type=parsed_rule.review_type,
                risk_level=parsed_rule.risk_level
            )
            session.add(rule)
        session.commit()
        print(f"Successfully parsed {len(parsed.rules)} rules from {filename}")
        return len(parsed.rules)
    except Exception as e:
        print(f"Error processing rules: {e}")
        raise

@router.post("/rule-groups/{group_id}/upload")
async def upload_rules_file(
    group_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: Profile = Depends(get_current_user)
):
    """Upload a file (txt, md, pdf, docx) and parse rules using LLM."""
    # Verify group exists
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    filename = file.filename or "unknown"

    # Check file type
    allowed_extensions = ('.txt', '.md', '.pdf', '.docx')
    if not filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are supported")

    # Read file content
    content = await file.read()

    try:
        # Extract text based on file type
        text_content = await extract_text_from_file(content, filename)

        # Process rules with LLM
        rules_count = await process_uploaded_rules(group_id, text_content, filename, session, str(current_user.id))

        return {"message": f"成功从 '{filename}' 解析并导入 {rules_count} 条规则", "group_id": group_id, "rules_count": rules_count}
    except Exception as e:
        error_msg = str(e)
        print(f"Error uploading rules: {error_msg}")
        raise HTTPException(status_code=500, detail=f"处理文件失败: {error_msg}")

# ============== CSV Import/Export ==============

@router.get("/rule-groups/{group_id}/export-csv")
def export_rules_csv(group_id: str, session: Session = Depends(get_session)):
    """Export all rules in a group as CSV file."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    rules = session.exec(select(Rule).where(Rule.group_id == group_id)).all()

    # Create CSV in memory with UTF-8 BOM for Excel compatibility
    output = io.StringIO()
    # Add BOM for Excel to recognize UTF-8
    output.write('\ufeff')
    writer = csv.writer(output)

    # Write header
    writer.writerow(["id", "standard_name", "clause_number", "content", "review_type", "risk_level"])

    # Write rules
    for rule in rules:
        writer.writerow([
            rule.id,
            rule.standard_name or "",
            rule.clause_number,
            rule.content,
            rule.review_type or "",
            rule.risk_level
        ])

    output.seek(0)

    # URL-encode the filename for non-ASCII characters (RFC 5987)
    filename = f"{group.name}_rules.csv"
    encoded_filename = quote(filename, safe='')

    # Use both filename (ASCII fallback) and filename* (UTF-8 encoded) for compatibility
    content_disposition = f"attachment; filename=\"rules.csv\"; filename*=UTF-8''{encoded_filename}"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": content_disposition
        }
    )

@router.post("/rule-groups/{group_id}/import-csv")
async def import_rules_csv(
    group_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: Profile = Depends(get_current_user)
):
    """Import rules from CSV file."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")

    filename = file.filename or "unknown.csv"
    if not filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    try:
        text_content = content.decode('utf-8')
    except UnicodeDecodeError:
        text_content = content.decode('gbk', errors='ignore')

    # Parse CSV
    reader = csv.DictReader(io.StringIO(text_content))
    imported_count = 0

    for row in reader:
        # Validate required fields
        clause_number = row.get('clause_number', '').strip()
        content_text = row.get('content', '').strip()

        if not clause_number or not content_text:
            continue  # Skip invalid rows

        # Get optional fields with defaults
        standard_name = row.get('standard_name', '').strip() or None
        review_type = row.get('review_type', '').strip() or None
        risk_level = row.get('risk_level', '中风险').strip()

        # Validate review_type and importance
        if review_type and review_type not in VALID_REVIEW_TYPES:
            review_type = None
        if risk_level not in VALID_RISK_LEVELS:
            risk_level = "中风险"

        rule = Rule(
            group_id=group_id,
            standard_name=standard_name,
            clause_number=clause_number,
            content=content_text,
            review_type=review_type,
            risk_level=risk_level
        )
        session.add(rule)
        imported_count += 1

    session.commit()

    return {"message": f"Imported {imported_count} rules from CSV", "group_id": group_id}