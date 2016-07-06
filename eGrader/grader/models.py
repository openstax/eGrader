import numpy as np

from sqlalchemy import and_, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.sql.expression import distinct, extract, label

from eGrader.accounts.models import Role, User
from eGrader.algs.active_learning_minvar import train_random_forest, get_min_var_idx
from eGrader.core import db

from sqlalchemy.dialects.postgresql import ARRAY, JSON

from eGrader.utils import JsonSerializer


def get_next_response(user_id, exercise_id):
    """
    Parameters
    ----------
    user_id : int
    exercise_id: int

    Returns
    -------
    response
        The response object from a list of responses

    """
    # TODO: Finish docstring of get_next_response function

    grades = ResponseGrade.get_grades(user_id, exercise_id)
    grade_counts = get_graded_count(exercise_id)
    print ('The amount of grades', len(grades))
    print('Printing Grades: ', grades)

    labels = [grade[1] for grade in grades]
    labels_array = np.array(labels, dtype=float)
    global_grade_counts = [grade_count[1] for grade_count in grade_counts]
    global_grade_count_array = np.array(global_grade_counts)

    if all(v is None for v in labels):
        response = Response.get_random_ungraded_response(user_id, exercise_id)

        return response
    else:
        exercise = Exercise.get(exercise_id)
        responses = Response.all_by_exercise_id(exercise_id)
        forest_name = exercise.forest_name
        if forest_name:
            # Load forest and get next best response
            print('load forest')
        else:
            # Create random forest, predict best response, and save to disk.
            # TODO: save forest to disk
            features = np.array(exercise.features)
            obs_idx = np.where(~np.isnan(labels_array))[0]
            print obs_idx
            forest = train_random_forest(features[obs_idx], labels_array[obs_idx])
            print forest
            prediction_idx = get_min_var_idx(features,
                                             labels_array,
                                             forest,
                                             global_grade_count_array,
                                             sample_limit=30)
            print(responses[prediction_idx])
        return responses[prediction_idx]


def get_next_exercise_id(user_id, subject_id=None, chapter_id=None, random=True):
    """
    Get the next exercise with responses that the grader is able to grade.

    Parameters
    ----------
    user_id:int
        the id of the user

    Returns
    -------
    exercise_id: int
        the exercise id of the next exercise that has responses to grade
    """

    # A query of responses graded by the user
    subq1 = db.session.query(ResponseGrade.response_id) \
        .filter(ResponseGrade.user_id == user_id).subquery()
    # A query of exercise_ids the user is unqualified to grade
    subq2 = db.session.query(UserUnqualifiedExercise.exercise_id) \
        .filter(UserGradingSession.user_id == user_id).subquery()
    # A query of all exercises and their number of grades
    subq3 = db.session.query(func.distinct(Exercise.id).label('exercise_id'),
                             func.count(func.coalesce(ResponseGrade.id, None)).label('grade_count')) \
        .join(Response) \
        .outerjoin(ResponseGrade) \
        .group_by(Exercise.id).subquery()

    # Return the first exercise that has responses not yet graded and not set to unqualified
    query = db.session.query(Exercise).join(Response)

    if subject_id:
        query = query.filter(Exercise.subject_id == subject_id)

    if random:
        query = query.join(subq3, and_(Exercise.id == subq3.c.exercise_id)).order_by(subq3.c.grade_count.asc(), Exercise.id)
    else:
        query = query.order_by(Exercise.chapter_id)

    if chapter_id:
        query = query.filter(Exercise.chapter_id == chapter_id)

    query = query.filter(~Response.id.in_(subq1)).filter(~Exercise.id.in_(subq2))
    query = query.filter(subq3.c.grade_count <= 2)
    ex = query.first()

    return ex.id


def get_parsed_exercise(exercise_id):
    # Get the JSON exercise data from the exercise.data field
    # This is where the feedback, answers, and other info is located

    exercise = Exercise.get(exercise_id)

    subject = Subject.get(exercise.subject_id)

    if exercise.book_row_id:
        book_url = '{0}:{1}'.format(subject.book_url, exercise.book_row_id)
    else:
        book_url = subject.book_url

    e_data = exercise.data['questions'][0]

    # Create a list for the feedback_choices
    feedback_choices = []

    # Get the correct answer
    for answer in e_data['answers']:
        if 'feedback_html' in answer and answer['feedback_html']:
            feedback = (str(answer['id']), answer['feedback_html'])
            feedback_choices.append(feedback)
        if answer['correctness'] == '1.0':
            answer_html = answer['content_html']

    return dict(id=exercise.id,
                exercise_html=e_data['stem_html'],
                answer_html=answer_html,
                feedback_choices=feedback_choices,
                uid=exercise.uid,
                book_url=book_url,
                chapter_id=exercise.chapter_id
                )


def get_grading_session_metrics(user_id):
    subq = db.session.query(ResponseGrade.session_id.label('session_id'),
                            func.count(ResponseGrade.id).label('responses_graded'),
                            label('time_grading', UserGradingSession.ended_on - UserGradingSession.started_on)) \
        .join(UserGradingSession) \
        .filter(UserGradingSession.user_id == user_id) \
        .group_by(ResponseGrade.session_id,
                  UserGradingSession.started_on,
                  UserGradingSession.ended_on).subquery()

    query = db.session.query(func.count(subq.c.session_id),
                             func.sum(subq.c.responses_graded),
                             extract('EPOCH', func.sum(subq.c.time_grading)))

    return query.all()[0]


def get_grading_session_details(user_id):
    query = db.session.query(UserGradingSession.id,
                             func.count(ResponseGrade.id),
                             UserGradingSession.started_on,
                             UserGradingSession.ended_on,
                             label('time_grading', UserGradingSession.ended_on - UserGradingSession.started_on))\
        .join(ResponseGrade, ResponseGrade.session_id == UserGradingSession.id)\
        .filter(UserGradingSession.user_id == user_id, UserGradingSession.ended_on != None)\
        .group_by(UserGradingSession.id,
                  UserGradingSession.started_on,
                  UserGradingSession.ended_on)\
        .order_by(UserGradingSession.started_on)

    return query.all()


def get_graded_count(exercise_id):
    query = db.session.query(Response.id, func.count(func.coalesce(ResponseGrade.id, None)))\
        .outerjoin(ResponseGrade)\
        .filter(Response.exercise_id == exercise_id)\
        .group_by(Response.id)\
        .order_by(Response.id)

    return query.all()


def get_admin_metrics():
    subject_count= ResponseGrade.subject_count()
    data = dict(total_grades=ResponseGrade.count(),
                total_responses=Response.count(),
                total_physics=subject_count[0][1],
                total_biology=subject_count[1][1]
                )
    return data


class ResponseGrade(db.Model):
    ___tablename__= 'response_grades'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    response_id = db.Column(db.Integer(), db.ForeignKey('responses.id'))
    score = db.Column(db.Float())
    misconception = db.Column(db.Boolean())
    junk = db.Column(db.Boolean())
    feedback_id = db.Column(db.Integer())
    submitted_on = db.Column(db.DateTime())
    session_id = db.Column(db.Integer(), db.ForeignKey('user_grading_sessions.id'))

    @classmethod
    def count(cls):
        subquery = db.session.query(User.id)\
            .join(Role, User.roles).filter(Role.name == 'admin')\
            .subquery()
        query = db.session.query(ResponseGrade)\
            .filter(~ResponseGrade.user_id.in_(subquery))

        return query.count()

    @classmethod
    def subject_count(cls):
        subquery = db.session.query(User.id) \
            .join(Role, User.roles)\
            .filter(Role.name == 'admin') \
            .subquery()
        query = db.session.query(Subject.name, func.count(ResponseGrade.id))\
            .join(Response)\
            .join(ResponseGrade)\
            .filter(~ResponseGrade.user_id.in_(subquery))\
            .group_by(Subject.name)

        return query.all()

    @classmethod
    def latest_by_session_id(cls, session_id):
        query = db.session.query(cls).filter(cls.session_id == session_id).order_by(cls.submitted_on.desc())

        return query.first()

    @classmethod
    def get_grades(cls, user_id, exercise_id):
        query = db.session.query(distinct(Response.id), cls.junk)\
            .outerjoin(cls, and_(cls.response_id == Response.id, cls.user_id == user_id))\
            .filter(Response.exercise_id == exercise_id).order_by(Response.id)

        return query.all()

    @classmethod
    def by_user_id(cls, user_id):
        return db.session.query(cls).filter(cls.user_id == user_id).all()


class Response(db.Model, JsonSerializer):
    __tablename__ = 'responses'
    id = db.Column(db.Integer(), primary_key=True)  # The corresponding columns in the spreadsheet
    external_id = db.Column(db.Integer())           # X.1
    step_id = db.Column(db.Integer(), unique=True)  # Basically the unique id of the response
    deidentifier = db.Column(db.String())           # Deidentifier
    free_response = db.Column(db.Text())            # Free.Response
    correct = db.Column(db.Boolean())               # Correct.
    correct_answer_id = db.Column(db.Integer())     # Correct.Answer.Id
    exercise_type = db.Column(db.String())          # Exercise.type
    exercise_id = db.Column(db.Integer(), db.ForeignKey('exercises.id'))
    subject = db.Column(db.String())
    subject_id = db.Column(db.Integer(), db.ForeignKey('subjects.id'))

    @classmethod
    def count(cls):
        return db.session.query(cls).count()

    @classmethod
    def get(cls, response_id):
        return db.session.query(cls).get(response_id)

    @classmethod
    def all_by_exercise_id(cls, exercise_id):
        return db.session.query(cls)\
            .filter(cls.exercise_id == exercise_id)\
            .order_by(cls.id)\
            .all()

    @classmethod
    def get_random_ungraded_response(cls, user_id, exercise_id):
        subquery = db.session.query(ResponseGrade.response_id) \
            .join(Response).filter(ResponseGrade.user_id == user_id).subquery()
        query = db.session.query(Response).filter(Response.exercise_id == exercise_id) \
            .filter(~Response.id.in_(subquery)).order_by(func.random())
        return query.first()


class Exercise(db.Model, JsonSerializer):
    __tablename__ = 'exercises'
    id = db.Column(db.Integer(), primary_key=True)
    uid = db.Column(db.String(), unique=True)
    url = db.Column(db.String())
    api_url = db.Column(db.String())  # API.URL
    data = db.Column(JSON())
    version = db.Column(db.Integer())
    features = db.Column(ARRAY(db.Integer()))
    forest_name = db.Column(db.String())
    subject_id = db.Column(db.Integer(), db.ForeignKey('subjects.id'))
    chapter_id = db.Column(db.Integer())
    section_id = db.Column(db.Integer())
    book_row_id = db.Column(db.Integer())

    responses = db.relationship('Response')

    @classmethod
    def get(cls, exercise_id):
        return db.session.query(cls).get(exercise_id)


class ExerciseNote(db.Model, JsonSerializer):
    __tablename__ = 'user_exercise_notes'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    exercise_id = db.Column(db.Integer(), db.ForeignKey('exercises.id'))
    text = db.Column(db.Text())
    created_on = db.Column(db.DateTime)

    @classmethod
    def get_by_user_id(cls, user_id, exercise_id):
        return db.session.query(cls)\
            .filter(cls.user_id == user_id, cls.exercise_id == exercise_id)\
            .order_by(cls.created_on).all()


class UserGradingSession(db.Model, JsonSerializer):
    __tablename__ = 'user_grading_sessions'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    started_on = db.Column(db.DateTime())
    ended_on = db.Column(db.DateTime())

    @classmethod
    def by_user_id(cls, user_id):
        return db.session.query(cls).filter(cls.user_id == user_id).all()

    @classmethod
    def latest(cls, user_id):
        return db.session.query(cls)\
            .filter(cls.user_id == user_id)\
            .filter(cls.ended_on != None)\
            .order_by(cls.ended_on.desc())\
            .first()

    @classmethod
    def latest_by_start(cls, user_id):
        return db.session.query(cls) \
            .filter(cls.user_id == user_id) \
            .order_by(cls.started_on.desc()) \
            .first()


class UserUnqualifiedExercise(db.Model, JsonSerializer):
    __tablename__ = 'user_unqualified_exercises'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    exercise_id = db.Column(db.Integer(), db.ForeignKey('exercises.id'))


class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String())
    tag = db.Column(db.String())
    book_url = db.Column(db.String())

    @classmethod
    def get(cls, subject_id):
        return db.session.query(cls).get(subject_id)

    def __repr__(self):
        return self.name
