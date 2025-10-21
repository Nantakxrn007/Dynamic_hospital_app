from django.contrib.gis.db import models

class Province(models.Model):
    province_key = models.CharField(max_length=10, unique=True)
    name_th = models.CharField(max_length=100)
    region = models.CharField(max_length=100, null=True, blank=True)
    adequacy_index = models.FloatField(null=True, blank=True)
    geom = models.MultiPolygonField(srid=4326)

    def __str__(self):
        return self.name_th