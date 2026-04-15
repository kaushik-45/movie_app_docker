from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework import status
from django.http import Http404
from django.contrib.auth import authenticate
from .models import Movie,User
from .serializers import MovieSerializer,UserSerializer

class MovieAddView(APIView):
    def post(self,request):
        movieData = MovieSerializer(data = request.data)
        if movieData.is_valid():
            movieData.save()
            return Response(status=status.HTTP_201_CREATED)
        return Response(movieData.errors,status=status.HTTP_400_BAD_REQUEST)
    
class MovieListView(APIView):
    def get(self,request):
        movies = Movie.objects.all()
        serializer = MovieSerializer(movies,many=True) 
        return Response(serializer.data,status=status.HTTP_200_OK)   
    

class MovieById(APIView):
    def get(self,request,id):
        try:
            movie = Movie.objects.get(pk=id)
        except Movie.DoesNotExist:
            raise Http404     

        serilalizer = MovieSerializer(movie)
        return Response(serilalizer.data,status=status.HTTP_200_OK)
    
class MovieDelete(APIView):
    def delete(self,request,id):
        try:
            movie = Movie.objects.get(pk=id)
            movie.delete()
        except Movie.DoesNotExist:
            return Response({'error': f'Movie with id {id} not found'}, status.HTTP_404_NOT_FOUND)
       
        return Response({'message':'Yeah! movie deleted successfully'},status.HTTP_202_ACCEPTED)

class RegisterView(APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        username = request.data.get('username')
        password = request.data.get('password')

       
        if User.objects.filter(email=email).exists():
            return Response({'error': 'User with this email already exists'}, status=status.HTTP_400_BAD_REQUEST)

        
        user = User.objects.create(email=email, username=username, password=password)
        serializer =UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    

class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')

        
        user = User.objects.get(email=email)
        check = user.password==password

        if check is not None:
            return Response({'message': 'Login successful'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)