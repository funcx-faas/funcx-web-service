from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length

class EditForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=20)])
    language = SelectField('Language', choices=[('Python 3', 'Python 3')], validators=[DataRequired()])
    content = TextAreaField('Content')
    submit = SubmitField('Save')