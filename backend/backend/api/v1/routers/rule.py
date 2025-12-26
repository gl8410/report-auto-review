import io
import csv
from typing import List
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from backend.api.deps import get_session
from backend.models.rule import RuleGroup, Rule
from backend.models.review import ReviewTask, ReviewResultItem
from backend.models.comparison import ComparisonResult
from backend.schemas.rule import (
    RuleGroupCreate, RuleGroupResponse,
    RuleCreate, RuleResponse, RuleUpdate
)
from backend.integrations.llm_client import parse_rules_from_text
from backend.services.document_service import extract_text_from_file

router = APIRouter()

# Valid values for rule fields
VALID_REVIEW_TYPES = ["内容完整性", "计算结果准确性", "禁止条款", "前后逻辑一致性", "措施遵从性", "计算正确性"]
VALID_RISK_LEVELS = ["低风险", "中风险", "高风险"]

# ============== Rule Group Endpoints ==============

@router.get("/rule-groups", response_model=List[RuleGroupResponse])
def get_rule_groups(session: Session = Depends(get_session)):
    """Get all rule groups (hierarchical tree, top-level only)."""
    # Only select top-level groups
    groups = session.exec(select(RuleGroup).where(RuleGroup.parent_id == None).order_by(RuleGroup.created_at.desc())).all()
    return groups

@router.post("/rule-groups", response_model=RuleGroupResponse)
def create_rule_group(data: RuleGroupCreate, session: Session = Depends(get_session)):
    """Create a new rule group."""
    if data.parent_id:
        parent = session.get(RuleGroup, data.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent rule group not found")

    group = RuleGroup(
        name=data.name,
        description=data.description,
        parent_id=data.parent_id
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
def update_rule_group(group_id: str, data: RuleGroupCreate, session: Session = Depends(get_session)):
    """Update a rule group."""
    group = session.get(RuleGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Rule group not found")
    
    group.name = data.name
    if data.description is not None:
        group.description = data.description
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

def delete_group_recursive(session: Session, group: RuleGroup):
    """Recursively delete a group and its children."""
    print(f"Deleting group: {group.name} ({group.id})")
    # 1. Fetch and delete children
    children = session.exec(select(RuleGroup).where(RuleGroup.parent_id == group.id)).all()
    for child in children:
        delete_group_recursive(session, child)

    # 2. Delete associated Review Tasks and their Results
    tasks = session.exec(select(ReviewTask).where(ReviewTask.rule_group_id == group.id)).all()
    print(f"Found {len(tasks)} tasks for group {group.id}")
    for task in tasks:
        print(f"Deleting task {task.id}")
        # Delete results for this task
        results = session.exec(select(ReviewResultItem).where(ReviewResultItem.task_id == task.id)).all()
        print(f"  Deleting {len(results)} review results")
        for res in results:
            session.delete(res)
            
        # Delete comparison results for this task
        try:
            comp_results = session.exec(select(ComparisonResult).where(ComparisonResult.task_id == task.id)).all()
            print(f"  Deleting {len(comp_results)} comparison results")
            for cr in comp_results:
                session.delete(cr)
        except Exception as e:
            print(f"  Error deleting comparison results: {e}")
            # Continue deleting task even if comparison results deletion fails
            
        # Delete the task itself
        session.delete(task)
    
    # 3. Delete all rules in this group
    rules = session.exec(select(Rule).where(Rule.group_id == group.id)).all()
    print(f"Deleting {len(rules)} rules for group {group.id}")
    for rule in rules:
        session.delete(rule)
        
    # 4. Delete the group
    session.delete(group)

@router.delete("/rule-groups/{group_id}")
def delete_rule_group(group_id: str, session: Session = Depends(get_session)):
    """Delete a rule group and all its sub-groups and rules."""
    print(f"Request to delete rule group: {group_id}")
    try:
        group = session.get(RuleGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Rule group not found")
        
        delete_group_recursive(session, group)
        session.commit()
        print("Deletion successful")
        return {"message": "Rule group and all sub-groups deleted"}
    except Exception as e:
        print(f"Error in delete_rule_group: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def get_child_group_ids(session: Session, group_id: str) -> List[str]:
    """Recursively get all child group IDs."""
    ids = [group_id]
    children = session.exec(select(RuleGroup).where(RuleGroup.parent_id == group_id)).all()
    for child in children:
        ids.extend(get_child_group_ids(session, child.id))
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
def create_rule(group_id: str, data: RuleCreate, session: Session = Depends(get_session)):
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

async def process_uploaded_rules(group_id: str, content: str, filename: str, session: Session) -> int:
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
    session: Session = Depends(get_session)
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
        rules_count = await process_uploaded_rules(group_id, text_content, filename, session)

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
    session: Session = Depends(get_session)
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