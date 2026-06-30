from typing import Dict, Any

def check_permission(user: Dict[str, Any], target_access_level: str, target_department: str = None) -> bool:
    """
    Checks if a user is allowed to read a page, segment, or proposition.
    Clearance levels: 'public' < 'team' < 'confidential' < 'restricted'
    If target_department is specified, user must belong to that department.
    Admin roles bypass checks.
    """
    user_role = user.get("role", "member").lower()
    if user_role == "admin":
        return True

    user_clearance = user.get("clearance_level", "public").lower()
    target_level = (target_access_level or "public").lower()

    rank = {"public": 0, "team": 1, "confidential": 2, "restricted": 3}
    
    user_rank = rank.get(user_clearance, 0)
    target_rank = rank.get(target_level, 0)

    if user_rank < target_rank:
        return False

    user_dept = user.get("department")
    if target_department and user_dept:
        if user_dept.lower() != target_department.lower():
            return False

    return True
