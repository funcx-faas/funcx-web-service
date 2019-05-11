from flask import Flask, render_template, request
from flask_wtf import Form
from wtforms import TextField, TextAreaField, validators, SelectField, SubmitField

from funcx_sdk.client import FuncXClient

app = Flask(__name__)
app.secret_key = 'Tylers Dev Key'


default_func = """def hello_world(): \n    return \"Hello!\""""


""" Here we have the Python endpoints that operate the funcX GUI. They should:

    1. Register (and Write!) Functions.
    2. List Functions.
    3. Submit (RUN) Functions.
"""


class PythonForm(Form):
    name = TextField("Function Name (unique)",validators=[validators.Required("Please enter a function name.")])
    PyFunc = TextAreaField("Function", default=default_func)  # TODO: Python validator.
    language = SelectField('Programming Language', choices=[('py', 'Python3.6'), ('bash', 'BASH')])
    submit = SubmitField("Register")


@app.route('/login', methods=['GET', 'POST'])
def login():
    return("TODO: ADD THE LOGIN TOMORROW!")


# TOOD: Move this into login endpoint w/ some HTML. :)
fx_client = FuncXClient()
@app.route('/register-function', methods=['POST', 'GET'])
def register_function():
    form = PythonForm()

    if request.method == 'POST':
        data = request.form
        PyFunc = data['PyFunc']
        name = data['name']

        try:
            # TODO: Entrypoint support in submission?
            fx_client.register_function(name, PyFunc, 'ryan_add', description="Test function to see if GUI registration works. ")
        except Exception as e:
            print(e)
    return render_template('register.html', form=form)


if __name__ == '__main__':
    # TODO: Move this to a login endpoint.

    app.run(debug=True)
