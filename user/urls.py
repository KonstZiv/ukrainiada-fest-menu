from django.urls import path

from user import views

app_name = "user"

urlpatterns = [
    path("profile/", views.get_profile, name="profile"),
    path("profile/edit/", views.edit_profile, name="profile_edit"),
    path("sign-up/", views.sign_up, name="sign_up"),
    path("channels/", views.manage_channels, name="channels"),
]
