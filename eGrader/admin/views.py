from datetime import datetime
from flask import (current_app,
                   Blueprint,
                   flash,
                   redirect,
                   render_template,
                   request,
                   url_for)
from flask_principal import Permission, RoleNeed
from flask_security.utils import encrypt_password


from eGrader.accounts.models import User, Role
from eGrader.admin.exports import (list_graded_responses,
                                   list_exercises,
                                   list_sessions,
                                   list_users,
                                   list_responses)
from eGrader.admin.forms import CreateUserForm, UpdateUserForm
from eGrader.core import db
from eGrader.grader.models import ResponseGrade, Response, get_admin_metrics
from eGrader.utils import render_csv

admin_permission = Permission(RoleNeed('admin'))

admin = Blueprint('admin',
                  __name__,
                  url_prefix= '/admin',
                  template_folder='../templates/admin'
                  )


@admin.route('/', methods=['GET'])
@admin_permission.require()
def index():
    data = get_admin_metrics()
    return render_template('admin_index.html',
                           data=data,
                           active_page='index')


@admin.route('/users', methods=['GET', 'POST'])
@admin_permission.require()
def manage_users():
    users = db.session.query(User).order_by(User.id).all()
    form = CreateUserForm(request.form)

    if form.validate_on_submit():
        encrypted_password = encrypt_password(form.password.data)

        user = User(email=form.email.data,
                    active=True,
                    subject_id = form.subject_id.data if form.subject_id.data else None,
                    registered_at=datetime.now(),
                    confirmed_at=datetime.now(),
                    password=encrypted_password)
        db.session.add(user)

        if form.role_id.data:
            role = Role.query.get(form.roles.data)
            user.roles.append(role)
            db.session.add(role)

        db.session.commit()

    return render_template('admin_users.html',
                           form=form,
                           users=users,
                           active_page='users')


@admin.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_permission.require()
def edit_user(user_id):
    user = db.session.query(User).get(user_id)
    form = UpdateUserForm(request.form, user)

    if form.validate_on_submit():
        # if role is different then we need to delete the previous one and add the new one.
        user.email = form.email.data,
        user.subject_id= form.subject_id.data if form.subject_id.data else None

        if form.role_id.data :
            user.roles = []
            db.session.commit()
            role = Role.query.get(form.role_id.data)
            user.roles.append(role)
            db.session.add(role)
        else:
            user.roles = []
            db.session.commit()

        db.session.commit()

        flash('User data updated', 'success')
        return redirect(url_for('admin.manage_users'))

    return render_template('admin_edit_user.html',
                           form=form,
                           user=user,
                           active_page='users')


@admin.route('/export', methods=['GET'])
@admin_permission.require()
def export():
    return render_template('admin_exports.html', active_page='export')


@admin.route('/export/grades')
@admin_permission.require()
def export_graded_responses():
    grades = list_graded_responses()
    atts = ['id',
            'step_id',
            'user_id',
            'email',
            'response_id',
            'score',
            'misconception',
            'junk',
            'feedback_id',
            'session_id',
            'submitted_on']
    return render_csv(atts, grades, 'graded-responses')


@admin.route('/export/exercises')
@admin_permission.require()
def export_exercises():
    exercises = list_exercises()
    atts = ['id',
            'uid',
            'url',
            'subject',
            'chapter_id',
            'section_id']
    return render_csv(atts, exercises, 'exercises')


@admin.route('/export/sessions')
@admin_permission.require()
def export_sessions():
    sessions = list_sessions()
    atts = ['session_id',
            'user_id',
            'email',
            'started_on',
            'ended_on']

    return render_csv(atts, sessions, 'grading-sessions')


@admin.route('/export/users')
@admin_permission.require()
def export_users():
    users = list_users()
    atts = ['id',
            'email',
            'last_login_at',
            'login_count',
            'subject',
            'active']

    return render_csv(atts, users, 'users')


@admin.route('/export/responses')
@admin_permission.require()
def export_responses():
    responses = list_responses()
    atts = ['id',
            'exercise_id',
            'step_id',
            'subject',
            'free_response',
            'correct',
            'correct_answer_id',
            'deidentifier']

    return render_csv(atts, responses, 'responses')
