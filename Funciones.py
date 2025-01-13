import os
from dotenv import load_dotenv
import requests
from simplejustwatchapi.justwatch import search as justwatch_search


load_dotenv()

def get_movie_awards(movie_title):
    """Función específica para obtener premios"""
    api_key = os.getenv('OMDB_API_KEY')
    url = f"http://www.omdbapi.com/?t={movie_title}&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()
        if data.get('Response') == 'True':
            return {
                'title': data.get('Title'),
                'awards': data.get('Awards', 'No hay información de premios'),
                'year': data.get('Year')
            }
        return "No se encontró información de la película"
    except Exception as e:
        return f"Error al buscar información de premios: {str(e)}"

def get_movie_ratings(movie_title):
    """Función específica para obtener ratings"""
    api_key = os.getenv('OMDB_API_KEY')
    url = f"http://www.omdbapi.com/?t={movie_title}&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()
        if data.get('Response') == 'True':
            return {
                'title': data.get('Title'),
                'ratings': data.get('Ratings', []),
                'imdbRating': data.get('imdbRating', 'N/A'),
                'metascore': data.get('Metascore', 'N/A')
            }
        return "No se encontró información de la película"
    except Exception as e:
        return f"Error al buscar ratings: {str(e)}"

