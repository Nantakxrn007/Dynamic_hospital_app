from django.urls import path
from . import views

urlpatterns = [
    path("", views.map_view, name="map_view"),
    path('analyze/', views.analyze_readiness, name='analyze_readiness'), # <--- เพิ่มบรรทัดนี้
    path('save-sim/', views.save_simulation, name='save_sim'),
    path('get-history/', views.get_history_list, name='get_history'),
    path('delete-history/', views.delete_simulation, name='delete_sim'), # <--- เพิ่มอันนี้
]
