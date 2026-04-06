from oauth2_provider.oauth2_validators import OAuth2Validator

# Maps OAuth2 scope name → feature codename prefix
SCOPE_FEATURE_PREFIX = {
    'upload': 'archive.',
    'polls': 'polls.',
    'events': 'events.',
}


def _scoped_permissions(user, scopes: set) -> list:
    """Return only the feature permissions relevant to the requested scopes."""
    prefixes = [SCOPE_FEATURE_PREFIX[s] for s in scopes if s in SCOPE_FEATURE_PREFIX]
    if not prefixes:
        return []
    all_perms = user.feature_permission_codenames
    return [p for p in all_perms if any(p.startswith(prefix) for prefix in prefixes)]


class MemberOAuth2Validator(OAuth2Validator):
    def get_additional_claims(self, request):
        """Claims added to ID tokens."""
        user = request.user
        if not user or not user.is_authenticated:
            return {}

        scopes = set(getattr(request, 'scopes', []))
        claims = {}

        permissions = _scoped_permissions(user, scopes)
        if permissions:
            claims['permissions'] = permissions

        if user.membership_type:
            claims['membership_type'] = user.membership_type.get_permission_profile_display()

        return claims

    def get_userinfo_claims(self, request):
        """Claims returned by the /o/userinfo/ OIDC endpoint."""
        claims = super().get_userinfo_claims(request)
        user = request.user
        if user and user.is_authenticated:
            claims.update({
                'preferred_username': user.username,
                'email': user.email or '',
                'given_name': user.first_name,
                'family_name': user.last_name,
            })
            if user.membership_type:
                claims['membership_type'] = user.membership_type.get_permission_profile_display()
            scopes = set(getattr(request, 'scopes', []))
            permissions = _scoped_permissions(user, scopes)
            if permissions:
                claims['permissions'] = permissions
        return claims
