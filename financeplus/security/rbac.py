from __future__ import annotations
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    OPERATOR = "operator"
    VIEWER = "viewer"
    CLIENT = "client"

class Permission(str, Enum):
    CLIENT_READ = "client:read"
    CLIENT_WRITE = "client:write"
    PRACTICE_READ = "practice:read"
    PRACTICE_WRITE = "practice:write"
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    ANALYSIS_RUN = "analysis:run"
    REPORT_EXPORT = "report:export"
    INTEGRATION_RUN = "integration:run"
    USER_ADMIN = "user:admin"
    AUDIT_READ = "audit:read"

ROLE_PERMISSIONS = {
    Role.ADMIN: set(Permission),
    Role.ANALYST: {Permission.CLIENT_READ, Permission.CLIENT_WRITE, Permission.PRACTICE_READ, Permission.PRACTICE_WRITE, Permission.DOCUMENT_READ, Permission.DOCUMENT_WRITE, Permission.ANALYSIS_RUN, Permission.REPORT_EXPORT, Permission.INTEGRATION_RUN, Permission.AUDIT_READ},
    Role.OPERATOR: {Permission.CLIENT_READ, Permission.CLIENT_WRITE, Permission.PRACTICE_READ, Permission.PRACTICE_WRITE, Permission.DOCUMENT_READ, Permission.DOCUMENT_WRITE, Permission.REPORT_EXPORT},
    Role.VIEWER: {Permission.CLIENT_READ, Permission.PRACTICE_READ, Permission.DOCUMENT_READ},
    Role.CLIENT: {Permission.CLIENT_READ, Permission.PRACTICE_READ, Permission.DOCUMENT_READ},
}

def permissions_for(role: Role | str) -> set[Permission]:
    try: r = Role(role)
    except Exception: return set()
    return set(ROLE_PERMISSIONS.get(r, set()))

def can(role: Role | str, permission: Permission | str) -> bool:
    try: p = Permission(permission)
    except Exception: return False
    return p in permissions_for(role)
