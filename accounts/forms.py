from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    UserChangeForm,
    AdminUserCreationForm,
)


class CustomUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = get_user_model()
        fields = AdminUserCreationForm.Meta.fields + ("role",)


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = get_user_model()
        fields = UserChangeForm.Meta.fields
