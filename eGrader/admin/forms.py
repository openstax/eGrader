import flask_wtf as WTF

from wtforms import (StringField,
                     SelectField,
                     PasswordField,
                     SubmitField, HiddenField)
from wtforms.validators import Optional

from flask_security.forms import (email_required,
                                  email_validator,
                                  password_required,
                                  password_length,
                                  unique_user_email)

from eGrader.grader.choices import get_subject_choices, get_role_choices



class CreateUserForm(WTF.Form):
    email = StringField('Email Address', validators=[email_required, email_validator, unique_user_email])
    subject_id = SelectField('Subject', validators=[Optional()])
    role_id = SelectField('Role', validators=[Optional()])
    password = StringField('Password', validators=[password_required, password_length])
    submit = SubmitField('Submit')

    def __init__(self, *args, **kwargs):
        WTF.Form.__init__(self, *args, **kwargs)
        self.subject_id.choices = get_subject_choices()
        self.role_id.choices = get_role_choices()


class UpdateUserForm(WTF.Form):
    id = HiddenField()
    email = StringField('Email Address', validators=[email_required, email_validator])
    subject_id = SelectField('Subject', validators=[Optional()])
    role_id = SelectField('Role', validators=[Optional()])
    submit = SubmitField('Submit')

    def __init__(self, *args, **kwargs):
        WTF.Form.__init__(self, *args, **kwargs)
        self.subject_id.choices = get_subject_choices()
        self.role_id.choices = get_role_choices()
