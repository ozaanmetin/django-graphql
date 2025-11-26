from django.contrib import admin

# Register your models here.

from shop import models


admin.site.register(models.Store)
admin.site.register(models.Product)
admin.site.register(models.Order)
admin.site.register(models.OrderItem)
admin.site.register(models.Review)
