import json

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, session, url_for
from flask import current_app
from flask_login import login_required
from flask_security import current_user
from flask_socketio import emit

from eGrader.grader.forms import GraderForm
from eGrader.utils import render_template_no_cache, send_slack_msg
from ..core import db, socketio

from .models import (Exercise,
                     get_next_exercise_id,
                     get_next_response,
                     get_parsed_exercise,
                     Response,
                     ResponseGrade,
                     UserGradingSession)


grader = Blueprint('grader',
                   __name__,
                   url_prefix='/grader',
                   template_folder='../templates/grader')


# Adding in some websockets to keep track of the user grading session
@socketio.on('connect', namespace='/grader/soc')
def grading_connect():
    # Get the latest grading_session
    # If the session is within 15 minutes of the last session return latest
    # else create a new session
    grading_session = UserGradingSession.latest(current_user.id)

    if grading_session \
            and grading_session.ended_on \
            and (datetime.utcnow() - grading_session.ended_on).seconds < 900:
        session['grading_session'] = grading_session
        emit('connection', dict(session_id=grading_session.id))
    elif grading_session and not grading_session.ended_on:
        session['grading_session'] = grading_session
        emit('connection', dict(session_id=grading_session.id))
    else:
        grading_session = UserGradingSession(
            user_id = current_user.id,
            started_on = datetime.utcnow()
        )
        db.session.add(grading_session)
        db.session.commit()
        session['grading_session'] = grading_session

        emit('connection', dict(session_id=grading_session.id))

    if not current_app.config['DEBUG']:
        send_slack_msg('User {} has started grading'.format(current_user.id))
    print('user {0} is grading'.format(current_user.id))


@socketio.on('disconnect', namespace='/grader/soc')
def grading_disconnect():
    print('Client disconnected', request.sid)
    if not current_app.config['DEBUG']:
        send_slack_msg('User {} has stopped grading'.format(current_user.id))
    if 'grading_session' in session and session['grading_session']:
        grading_session = session['grading_session']
        grading_session.ended_on = datetime.utcnow()
        db.session.add(grading_session)
        db.session.commit()
    else:
        grading_session = UserGradingSession.latest(current_user.id)
        grading_session.ended_on = datetime.utcnow()
        db.session.add(grading_session)
        db.session.commit()


def _get_exercise_response():
    """
    This is only used for the old form based input which was mainly for testing of algorithms

    Returns
    -------
    exercise
    response
    """
    user_id = current_user.id
    if 'exercise' in session and session['exercise']:
        exercise = session['exercise']
        exercise_id = session['exercise']['id']
    else:
        exercise_id = get_next_exercise_id(user_id)
        exercise = get_parsed_exercise(exercise_id)
        session['exercise'] = exercise
        print ('Printing exercise_id!', exercise_id)

    if 'response' in session and session['response']:
        response = session['response']
    else:
        response = get_next_response(user_id, exercise_id)
        print ('Printing exercise_id!', exercise_id)

    if not response:
        _get_exercise_response()

    return exercise, response


@grader.route('/', methods=['GET'])
@login_required
def index():
    return render_template_no_cache('grader_index.html',
                           user_id=current_user.id)


@grader.route('/old', methods=['GET', 'POST'])
@login_required
def old():
    """
    * DEPRECATED *
    This view is deprecated as it was only used to test javascript and algorithms. This
    form allows you to submit responses simply using html forms and nothing more and is
    not as sophisticated as `grader.index`
    Returns
    -------
    template
    """
    exercise, response = _get_exercise_response()

    form = GraderForm(request.form)

    if request.method == 'POST':
        form.feedback.choices = [(choice[0], choice[0]) for choice in exercise['feedback_choices']]
        if form.validate():
            grade = ResponseGrade(
                response_id = form.response_id.data,
                user_id = current_user.id,
                score = form.score.data,
                misconception = form.misconception.data,
                junk = form.quality.data,
                feedback_id = form.feedback.data
            )
            db.session.add(grade)
            db.session.commit()
            # Clear the session of the response
            session['response'] = None
            return redirect(url_for('grader.grade_next_response'))

    free_response = response.free_response
    form.feedback.choices = exercise['feedback_choices']
    form.response_id.data = response.id

    return render_template('old_index.html', form=form,
                           exercise=exercise,
                           free_response = free_response)


