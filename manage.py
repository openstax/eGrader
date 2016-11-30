from datetime import datetime
from flask import url_for
from flask_script import Manager, prompt_bool
from flask_security import utils

from eGrader import create_app
from eGrader.models import *
from eGrader.core import db

app = create_app()
manager = Manager(app)


@manager.command
def drop_db():
    if prompt_bool(
            'Are you sure you want to lose all your data for {0} ? \nThis is process is not reversible'.format(
                app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1])
    ):
        db.drop_all()
        db.session.commit()
        print('Database has been dropped')


@manager.command
def reset_db():
    if prompt_bool(
            'Are you sure you want to lose all your data for {0}'.format(
                app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1])
    ):
        from alembic.command import downgrade, upgrade
        from alembic.config import Config as AlembicConfig
        config = AlembicConfig('alembic.ini')
        downgrade(config, 'base')
        upgrade(config, 'head')
        print('Database has been reset')


@manager.command
def load_exercise_features():
    from eGrader.tasks.prepare_exercises import load_exercise_features
    load_exercise_features()
    return


@manager.command
def update_exercise_vocab():
    from eGrader.tasks.prepare_exercises import update_exercises_vocab
    update_exercises_vocab()
    return


@manager.command
def load_subject_ids():
    from eGrader.tasks.add_subject_ids import update_responses_with_subject, update_exercises_with_subject
    update_exercises_with_subject()
    update_responses_with_subject()
    return


@manager.command
def update_book_info():
    from eGrader.tasks.update_book_info import update_exercises_with_book_info
    # Update Biology exercises
    update_exercises_with_book_info('eGrader/tasks/data/apbio_ex.csv')
    # update Physics exercises
    update_exercises_with_book_info('eGrader/tasks/data/hsphys_ex.csv')
    print('Exercises have been updated with book information')


@manager.command
def update_grading_session_times():
    from eGrader.tasks.session_fixes import update_grading_sessions_end_times
    update_grading_sessions_end_times()
    print('Session end times have been updated')


@manager.option('-e', '--email', dest='email')
@manager.option('-p', '--password', dest='password')
def create_admin_user(email, password):
    user_datastore = app.extensions['security'].datastore
    user_datastore.find_or_create_role(name='admin',
                                       description='Administrator')
    encrypted_password = utils.encrypt_password(password)

    if not user_datastore.get_user(email):
        user_datastore.create_user(email=email,
                                   active=True,
                                   registered_at=datetime.now(),
                                   confirmed_at=datetime.now(),
                                   password=encrypted_password)
    db.session.commit()
    user_datastore.add_role_to_user(email, 'admin')
    db.session.commit()


@manager.option('-e', '--email', dest='email')
@manager.option('-p', '--password', dest='password')
@manager.option('-s', '--subject_id', dest='subject_id')
def create_user(email, password, subject_id):

    user_datastore = app.extensions['security'].datastore

    encrypted_password = utils.encrypt_password(password)

    if not user_datastore.get_user(email):
        user_datastore.create_user(email=email,
                                   active=True,
                                   registered_at=datetime.now(),
                                   confirmed_at=datetime.now(),
                                   password=encrypted_password,
                                   subject_id=subject_id)
    db.session.commit()


@manager.command
def send_test_email():
    from flask_mail import Message
    from eGrader.core import mail

    to = ['labs@openstax.org']
    subject = 'Test Email'
    template = '<h1>This is a test of Openstax eGrader email messaging system</h1>'

    msg = Message(
        subject,
        recipients=to,
        html=template,
        sender=app.config['SECURITY_EMAIL_SENDER']
    )
    mail.send(msg)


@manager.command
def list_routes():
    """List available routes in the application"""
    output = []
    for rule in app.url_map.iter_rules():

        methods = ','.join(rule.methods)
        url = str(rule)
        if '_debug_toolbar' in url:
            continue
        line = "{:50s} {:30s} {}".format(rule.endpoint, methods, url)
        output.append(line)

    print('\n'.join(sorted(output)))


@manager.shell
def make_shell_context():
    return dict(app=app, db=db)


if __name__ == '__main__':
    manager.run()
