from rest_framework import serializers
from .models import Movie,User

class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = super(UserSerializer, self).create(validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user