from flask import Flask, render_template, request, flash
from flask_bootstrap import Bootstrap5
from flask_wtf.csrf import CSRFProtect
from openai import OpenAI
from dotenv import load_dotenv
import os
from db import db, db_config
from models import User, Message
import json
from Funciones import get_movie_awards
from Funciones import get_movie_ratings
from forms import SignUpForm, LoginForm
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
from flask_bcrypt import Bcrypt
from flask import redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField
from wtforms.validators import DataRequired, Email

load_dotenv()

# Inicialización de la aplicación
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')


# Configuraciones e inicializaciones
bootstrap = Bootstrap5(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Inicia sesión para continuar'
login_manager.init_app(app)
bcrypt = Bcrypt(app)
db_config(app)

# Cliente OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

with app.app_context():
    db.create_all()
    print("¡Base de datos inicializada!")

@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(int(user_id))


# Configuración de herramientas para OpenAI
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_movie_awards",
            "description": "Obtiene información sobre los premios de una película",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_title": {
                        "type": "string",
                        "description": "El título de la película"
                    }
                },
                "required": ["movie_title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_movie_ratings",
            "description": "Obtiene información sobre los ratings y calificaciones de una película",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_title": {
                        "type": "string",
                        "description": "El título de la película"
                    }
                },
                "required": ["movie_title"]
            }
        }
    }
]


@app.route('/')
def index():
    return render_template('landing.html')


@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    user = db.session.query(User).get(current_user.id)
    nombre = user.nombre or ""
    user_id = user.id or 1
    generos_preferidos = user.generos_preferidos or ""
    peliculas_favoritas = user.peliculas_favoritas or ""
    directores_favoritos = user.directores_favoritos or ""

    if request.method == 'GET':
        return render_template('chat.html',
                               messages=user.messages,
                               nombre=nombre,
                               generos_preferidos=generos_preferidos,
                               peliculas_favoritas=peliculas_favoritas,
                               directores_favoritos=directores_favoritos,
                               user_id=user_id)

    intent = request.form.get('intent')
    user_message = request.form.get('message')
    if user_message == "":
        user_message = intent

    # Guardar nuevo mensaje en la BD
    db.session.add(Message(content=user_message, author="user", user=user))
    db.session.commit()

    messages_for_llm = [{
        "role": "system",
        "content": f"""Eres PeliQuest, un asistente experto en cine que proporciona recomendaciones personalizadas. 

REGLAS IMPORTANTES:
- Recomienda SOLO UNA película por respuesta
- Mantén las respuestas breves y concisas 
- No repitas películas ya recomendadas
- Evita dar explicaciones extensas
- No listes múltiples opciones

PERFIL DEL USUARIO:
- Nombre: {user.nombre}
- Géneros favoritos: {generos_preferidos}
- Películas favoritas: {peliculas_favoritas}
- Directores favoritos: {directores_favoritos}

Tu respuesta debe ser directa y específica, enfocándote en una única recomendación que mejor se ajuste al perfil y la consulta del usuario."""
    }]

    for message in user.messages:
        messages_for_llm.append({
            "role": message.author,
            "content": message.content,
        })

    chat_completion = client.chat.completions.create(
        messages=messages_for_llm,
        model="gpt-4",
        tools=tools,
        tool_choice="auto",
        temperature=1
    )

    if chat_completion.choices[0].message.tool_calls:
        for tool_call in chat_completion.choices[0].message.tool_calls:
            try:
                function_args = json.loads(tool_call.function.arguments)

                if tool_call.function.name == "get_movie_awards":
                    movie_title = function_args.get("movie_title")
                    movie_info = get_movie_awards(movie_title)
                    print("📽️ Consultando premios...")

                    messages_for_llm.append({
                        "role": "function",
                        "name": tool_call.function.name,
                        "content": json.dumps(movie_info)
                    })

                elif tool_call.function.name == "get_movie_ratings":
                    movie_title = function_args.get("movie_title")
                    movie_info = get_movie_ratings(movie_title)
                    print("⭐ Consultando ratings...")

                    messages_for_llm.append({
                        "role": "function",
                        "name": tool_call.function.name,
                        "content": json.dumps(movie_info)
                    })

                # Crear segunda respuesta después de procesar la función
                second_response = client.chat.completions.create(
                    messages=messages_for_llm,
                    model="gpt-4",
                    temperature=1
                )
                model_recommendation = second_response.choices[0].message.content

            except Exception as e:
                model_recommendation = f"Lo siento, ocurrió un error: {str(e)}"

    else:
        model_recommendation = chat_completion.choices[0].message.content

    db.session.add(Message(content=model_recommendation, author="assistant", user=user))
    db.session.commit()

    return render_template('chat.html',
                           messages=user.messages,
                           nombre=nombre,
                           generos_preferidos=generos_preferidos,
                           peliculas_favoritas=peliculas_favoritas,
                           directores_favoritos=directores_favoritos,
                           user_id=user_id)


@app.route('/user/<username>')
@login_required
def user(username):
    user = db.session.query(User).first()
    nombre = user.nombre or ""
    generos_preferidos = user.generos_preferidos or ""
    peliculas_favoritas = user.peliculas_favoritas or ""
    directores_favoritos = user.directores_favoritos or ""

    favorite_movies = peliculas_favoritas.split(",")
    return render_template('user.html', username=username, favorite_movies=favorite_movies)


class UpdateUserForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    generos_preferidos = StringField('Géneros Preferidos')
    peliculas_favoritas = StringField('Películas Favoritas')
    directores_favoritos = StringField('Directores Favoritos')


@app.route('/user/update/<int:id>', methods=['GET', 'POST'])
def update_user(id):
    user = db.session.query(User).get(id)
    form = UpdateUserForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            user.nombre = request.form['nombre']
            user.email = request.form['email']
            user.generos_preferidos = request.form['generos_preferidos'].lower()
            user.peliculas_favoritas = request.form['peliculas_favoritas'].lower()
            user.directores_favoritos = request.form['directores_favoritos'].lower()

            db.session.commit()
            return redirect(url_for('update_user', id=id, success='Información del usuario fue actualizada'))

    return render_template('update_user.html', user=user, form=form)


@app.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    form = SignUpForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            user = User(email=email, password_hash=bcrypt.generate_password_hash(password).decode('utf-8'))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('chat'))
    return render_template('sign-up.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
            user = db.session.query(User).filter_by(email=email).first()
            if user and bcrypt.check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect('chat')

            flash("El correo o la contraseña es incorrecta.", "error")

    return render_template('log-in.html', form=form)


@app.get('/logout')
def logout():
    logout_user()
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)