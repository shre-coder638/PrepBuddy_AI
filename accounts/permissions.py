
def get_authorized_staff_profile(user):
    """Return an allowed staff profile, or None if access is denied."""
    if not user.is_authenticated:
        return None

    profile = getattr(user, "staff_profile", None)
    if profile is None or profile.role not in {"clinic_staff", "doctor"}:
        return None

    return profile
