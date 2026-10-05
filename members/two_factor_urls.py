from django.urls import path

from .two_factor import (
    MemberBackupTokensView,
    MemberDisableView,
    MemberQRGeneratorView,
    MemberSetupCompleteView,
    MemberSetupView,
    PasskeyDeleteView,
    PasskeyListView,
    PasskeyRenameView,
    TwoFactorProfileRedirectView,
)

app_name = 'two_factor'

urlpatterns = [
    path('', TwoFactorProfileRedirectView.as_view(), name='profile'),
    path('setup/', MemberSetupView.as_view(), name='setup'),
    path('qrcode/', MemberQRGeneratorView.as_view(), name='qr'),
    path('setup/complete/', MemberSetupCompleteView.as_view(), name='setup_complete'),
    path('backup/tokens/', MemberBackupTokensView.as_view(), name='backup_tokens'),
    path('disable/', MemberDisableView.as_view(), name='disable'),
    path('passkeys/', PasskeyListView.as_view(), name='passkeys'),
    path('passkeys/<int:pk>/rename/', PasskeyRenameView.as_view(), name='passkey_rename'),
    path('passkeys/<int:pk>/delete/', PasskeyDeleteView.as_view(), name='passkey_delete'),
]
