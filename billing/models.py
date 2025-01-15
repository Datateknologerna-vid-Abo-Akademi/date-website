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

    def __str__(self):
        return f"{self.participant.event.title} - {self.participant.user} - {self.invoice_number}"


class EventBillingConfiguration(models.Model):
    event = models.OneToOneField('events.Event', blank=False, on_delete=models.CASCADE)
    due_date = models.DateField()
    integration_type = models.IntegerField()
    price = models.CharField()
    price_selector = models.CharField()

    def __str__(self):
        return self.event.title
