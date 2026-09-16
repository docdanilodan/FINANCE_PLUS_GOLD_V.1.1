from financeplus.security import can, Role, Permission

def test_admin_all_and_viewer_read_only():
    assert can(Role.ADMIN,Permission.USER_ADMIN)
    assert can(Role.VIEWER,Permission.CLIENT_READ)
    assert not can(Role.VIEWER,Permission.CLIENT_WRITE)
