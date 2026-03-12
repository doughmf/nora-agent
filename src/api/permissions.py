"""
Syndra — Sistema de Permissões por Perfil

Hierarquia:
  super_admin > admin > sindico > colaborador
"""
from fastapi import HTTPException

# Roles válidos e sua hierarquia numérica
ROLE_HIERARCHY = {
    "super_admin": 4,
    "admin": 3,
    "sindico": 2,
    "colaborador": 1,
}

ROLE_LABELS = {
    "super_admin": "Super Admin",
    "admin": "Admin",
    "sindico": "Síndico",
    "colaborador": "Colaborador",
}

# Permissões por role
PERMISSIONS = {
    "super_admin": {
        "manage_condos",       # Criar/excluir condomínios
        "manage_users",        # Gerenciar usuários
        "manage_settings",     # Configurar IA e settings
        "view_dashboard",      # Dashboard e estatísticas
        "view_maintenance",    # Chamados de manutenção
        "view_bookings",       # Reservas de espaços
        "view_residents",      # Ver moradores
    },
    "admin": {
        "manage_users",
        "manage_settings",
        "view_dashboard",
        "view_maintenance",
        "view_bookings",
        "view_residents",
    },
    "sindico": {
        "manage_users",
        "view_dashboard",
        "view_maintenance",
        "view_bookings",
        "view_residents",
    },
    "colaborador": {
        "view_dashboard",
        "view_maintenance",
        "view_bookings",
        "view_residents",
    },
}


def has_permission(user: dict, permission: str) -> bool:
    """Verifica se o usuário tem a permissão solicitada."""
    role = user.get("role", "colaborador")
    return permission in PERMISSIONS.get(role, set())


def require_permission(user: dict, permission: str):
    """Lança 403 se o usuário não tiver a permissão."""
    if not has_permission(user, permission):
        role_label = ROLE_LABELS.get(user.get("role"), user.get("role"))
        raise HTTPException(
            status_code=403,
            detail=f"Acesso negado. Perfil '{role_label}' não tem permissão para esta ação."
        )


def can_manage_user(actor: dict, target_role: str) -> bool:
    """Um usuário só pode criar/editar usuários de hierarquia inferior à sua."""
    actor_level = ROLE_HIERARCHY.get(actor.get("role", ""), 0)
    target_level = ROLE_HIERARCHY.get(target_role, 0)
    return actor_level > target_level


def roles_available_for(actor: dict) -> list[dict]:
    """Retorna os roles que o actor pode atribuir a outros usuários."""
    actor_level = ROLE_HIERARCHY.get(actor.get("role", ""), 0)
    return [
        {"value": role, "label": ROLE_LABELS[role]}
        for role, level in ROLE_HIERARCHY.items()
        if level < actor_level
    ]
