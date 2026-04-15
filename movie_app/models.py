from django.db import models

# Create your models here.
class Movie(models.Model):
    name = models.CharField(max_length=255)
    year = models.CharField(max_length=200)
    image= models.TextField(default='')
    description = models.TextField()
 
 
class User(models.Model):
    email = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    password  = models.CharField(max_length=255)