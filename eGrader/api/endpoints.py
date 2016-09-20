from datetime import datetime
from flask import abort, Blueprint, jsonify, request, session
from flask_login import login_required, current_user

from eGrader.algs.active_learning_minvar import MinVarException
from eGrader.core import db

from eGrader.grader.models import (ExerciseNote,
                                   get_next_exercise_id,
                                   get_next_response,
                                   get_parsed_exercise,
                                   Response,
                                   ResponseGrade,
                                   UserGradingSession,
                                   UserUnqualifiedExercise)


api = Blueprint('api',
                __name__,
                url_prefix='/api/v1')


@api.route('/ping')
def pong():
    return jsonify(dict(message='pong'))


@api.route('/exercises/<int:exercise_id>')
def get_exercise(exercise_id):
    exercise = get_parsed_exercise(exercise_id)
    if not exercise:
        abort(404)
    else:
        return jsonify(**exercise)


@api.route('/exercise/next', methods=['GET'])
@login_required
def get_next_exercise():
    chapter_id = request.args.get('chapter_id', None)

    # Check and see if there is an exercise in the session.
    if 'exercise_id' in session and session['exercise_id']:
        exercise_id = session['exercise_id']

        # Check if the user still has responses to grade for that exercise
        try:
            response = get_next_response(current_user.id, exercise_id)
        except MinVarException:
            response = None

        # If there is a response available return the exercise_id
        if response and exercise_id:
            session['exercise_id'] = exercise_id
            return jsonify(dict(success=True, exercise_id=exercise_id))

        # If there is no response that means we need a new exercise
        if not response:
            exercise_id = get_next_exercise_id(current_user.id,
                                               current_user.subject_id,
                                               chapter_id=chapter_id)
            session['exercise_id'] = exercise_id
            if exercise_id:
                return jsonify(dict(success=True, exercise_id=exercise_id))
            else:
                session['exercise_id'] = None
                return jsonify(dict(success=False, message='There are no more exercises for that user'))
    else:
        exercise_id = get_next_exercise_id(current_user.id,
                                           current_user.subject_id,
                                           chapter_id=chapter_id)
        if exercise_id:
            session['exercise_id'] = exercise_id
            return jsonify(dict(success=True, exercise_id=exercise_id))
        else:
            return jsonify(dict(success=False, message='There are no more exercises for that user'))


@api.route('/response/next', methods=['GET'])
@login_required
def next_response():
    exercise_id = request.args.get('exercise_id', None)
    try:
        response = get_next_response(current_user.id, exercise_id)
    except MinVarException:
        return jsonify(dict(
            message='There are no more responses available for that exercise',
            success=False))

    if response:
        return jsonify(dict(success=True, response=response.to_json()))
    else:
        return jsonify(dict(
            message='There are no more responses available for that exercise',
            success=False))


@api.route('/response/submit', methods=['POST'])
@login_required
def submit_grader_response():
    posted = request.get_json()
    print(posted)
    grade = ResponseGrade(
        user_id = posted['user_id'] if posted['user_id'] else None,
        response_id=posted['responseId'] if posted['responseId'] else None,
        score=posted['score'] if 'score' in posted else None,
        misconception = posted['misconception'] if 'misconception' in posted else None,
        junk = posted['quality'],
        feedback_id = posted['feedback_id'] if posted['quality'] else None,
        submitted_on = datetime.utcnow(),
        session_id = posted['session_id']
    )
    db.session.add(grade)
    db.session.commit()

    return jsonify(dict(success=True, message='Response submitted'))


@api.route('/exercise/unqualified', methods=['POST'])
@login_required
def not_qualified():
    posted = request.get_json()
    unqual = UserUnqualifiedExercise(
        user_id = posted['user_id'],
        exercise_id = posted['exercise_id']
    )
    db.session.add(unqual)
    db.session.commit()

    return jsonify(dict(success=True, message='Qualification submitted'))


@api.route('/exercise/notes', methods=['GET'])
@login_required
def get_user_exercise_notes():
    user_id = current_user.id
    exercise_id = request.args.get('exercise_id', None)
    notes = ExerciseNote.get_by_user_id(user_id, exercise_id)
    data = [{"id": note.id,
             "text": note.text} for note in notes]

    if not notes:
        return jsonify(dict(success=False, notes=[]))
    else:
        return jsonify(dict(success=True, notes=data))


@api.route('/exercise/notes', methods=['POST'])
@login_required
def submit_note():
    posted = request.get_json()
    note = ExerciseNote(
        user_id = posted['user_id'],
        exercise_id = posted['exercise_id'],
        text = posted['text'],
        created_on = datetime.utcnow()
    )

    db.session.add(note)
    db.session.commit()

    return jsonify(dict(success=True, message='Note submitted', note=note.to_json()))
