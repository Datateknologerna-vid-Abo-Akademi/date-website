from django.db import models

# Create your models here.


class File(models.Model):
    title = models.CharField(max_length=150)
    pub_date = models.DateTimeField()
    file = models.FileField()

    def pub_date_pretty(self):
        return self.pub_date.strftime('%b %e %Y')

    def __str__(self):
        return self.title


class Picture(File):
    file = models.ImageField(upload_to='/Images')
