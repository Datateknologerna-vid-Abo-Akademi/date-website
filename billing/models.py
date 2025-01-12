from django.db import models

# Create your models here.

class EventInvoice(models.Model):
    participant = models.ForeignKey('events.EventAttendees', on_delete=models.CASCADE)
    invoice_number = models.IntegerField(unique=True)
    reference_number = models.CharField(max_length=20, unique=True)
    invoice_date = models.DateField()
    due_date = models.DateField()
    amount = models.FloatField(default=0)
    currency = models.CharField(max_length=3, default='EUR')


class EventBillingConfiguration(models.Model):
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE)
    due_date = models.DateField()
    integration_type = models.IntegerField()
    price = models.CharField()
    price_selector = models.CharField()
