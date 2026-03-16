from django.urls import path

from feedback import views

app_name = "feedback"

urlpatterns = [
    path("<int:order_id>/submit/", views.submit_feedback, name="submit"),
    path("board/", views.feedback_board, name="board"),
    path("moderate/", views.moderate_feedback_view, name="moderate"),
    path("moderate/<int:feedback_id>/", views.moderate_action, name="moderate_action"),
]
