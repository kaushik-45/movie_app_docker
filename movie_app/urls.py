from django.urls import path
from . import apiviews

urlpatterns=[
     
     path("login/",apiviews.LoginView.as_view(),name="Login"),
     path("register/",apiviews.RegisterView.as_view(),name="Register"),
     path("add_movie/",apiviews.MovieAddView.as_view(),name = "MovieAddView"),
     path("get_movies/",apiviews.MovieListView.as_view(),name = "MovieListView"),
     path("movie/<int:id>/",apiviews.MovieById.as_view(), name= "MovieById"),
     path("movie/delete/<int:id>/",apiviews.MovieDelete.as_view(), name="MovieDelete")
     
]



