from django.db import models

class SimulationHistory(models.Model):
    province_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # เก็บ Input และ Output ทั้งหมดเป็น JSON ก้อนเดียว
    # ตัวอย่าง: {'inputs': {x1: 10, ...}, 'results': {R_final: 0.8, ...}}
    data = models.JSONField()
    
    # เก็บคำแนะนำ AI แยกออกมาเพื่อให้เรียกใช้ง่าย (หรือจะรวมใน JSON ก็ได้)
    ai_response = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.province_name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"