from django.db import models
from django.utils import timezone
import datetime

# Create your models here.

class Blog(models.Model):
    title = models.CharField(max_length=100)
    pub_date = models.DateTimeField()
    body = models.TextField()

    def summary(self):
        return self.body[:100]

    def pub_date_short(self):
        return self.pub_date.strftime('%d %e %Y')

    def was_published_recently(self):
        return self.pub_date >= timezone.now() - datetime.timedelta(days=1)

    def __str__(self):
        return self.title
    

class Comment(models.Model):
    user = models.CharField(max_length=50)
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    text = models.TextField(max_length=400)
    pub_date = models.DateTimeField(default=timezone.now)

    def pub_date_short(self):
        return self.pub_date.strftime('%d %e %Y')