import logging
import os
from datetime import datetime

import numpy as np
from sklearn.externals import joblib
from sqlalchemy import and_, func, or_, case
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.sql.expression import distinct, extract, label

from eGrader.accounts.models import Role, User
from eGrader.algs.active_learning_minvar import train_random_forest, \
    get_min_var_idx
from eGrader.core import db

from sqlalchemy.dialects.postgresql import ARRAY, JSON

from eGrader.exceptions import ResponsesNotFound
from eGrader.utils import JsonSerializer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))


def determine_unresolved(grades):
    """
    This function takes in the grade counts as a list of this format
    [response_id, score, misconception, junk, total_grades]

    With these it determins if there is a majority vote for these labels.
    If a majority vote does not exist it returns False

    Parameters
    ----------
    labels_list

    Returns boolean
    -------

    """
    score = grades[1]
    misconception = grades[2]
    junk = grades[3]
    total_grades = grades[4]

    if total_grades <= 1:
        return True

    if total_grades == 2:
        if score > 1 or misconception > 1 or junk > 1:
            return True
        else:
            return False

    if total_grades == 3:
        if score > 2:
            return True
        else:
            return False


def get_exercise_responses(exercise_id):
    responses = db.session.query(Response).filter(
        Response.exercise_id == exercise_id).all()
    for response in responses:
        yield response


def get_exercise_grade_counts(exercise_id):
    responses = db.session.query(Response.id,
                                 func.count(func.distinct(ResponseGrade.score)),
                                 func.count(func.distinct(
                                     ResponseGrade.misconception)),
                                 func.count(func.distinct(ResponseGrade.junk)),
                                 func.count(
                                     func.coalesce(ResponseGrade.id, None))) \
        .outerjoin(ResponseGrade) \
        .filter(Response.exercise_id == exercise_id) \
        .group_by(Response.id).all()
    for response in responses:
        yield response


def get_next_response(user_id, exercise_id):
    """
    Get a random ungraded response or throw an exception
    
    Parameters
    ----------
    user_id : int
    exercise_id: int

    Returns
    -------
    response
        The response object from a list of responses

    """
    response = Response.get_random_ungraded_response(user_id, exercise_id,
                                                     active=True)
    grades = ResponseGrade.get_grades(user_id, exercise_id, active=True)
    labels = [int(grade[1]) if grade[1] else grade[1] for grade in grades]
    labels_array = np.array(labels, dtype=float)
    unique, counts = np.unique(labels_array[~np.isnan(labels_array)], return_counts=True)

    stats = dict(zip(unique, counts))
    stats['Total:'] = len(labels)

    log.info(stats)

    if response:
        return response
    else:
        raise ResponsesNotFound()


def get_next_smart_response(user_id, exercise_id):
    """
    
    This function is to be used when wanting to compute the minimum variance
    between different responses and to select a response "smartly". 
    
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

    # Get the response_id and Junk label for the user and exercise
    grades = ResponseGrade.get_grades(user_id, exercise_id)

    # Get the global (all graders) count for each response
    grade_counts = get_graded_count(exercise_id)
    log.info('The amount of grades for exercise: {0} is {1}'.format(
        exercise_id, len(grades)))
    log.info(grades)

    # Make the labels array
    labels = [int(grade[1]) if grade[1] else grade[1] for grade in grades]
    labels_array = np.array(labels, dtype=float)
    log.info(labels_array)

    # Make the global_grade_count array
    global_grade_counts = [grade_count[1] for grade_count in grade_counts]
    global_grade_count_array = np.array(global_grade_counts)

    exercise = Exercise.get(exercise_id)

    # Need to return response if there are any that are unresolved.
    # If no unresolved get random
    unresolved = exercise.get_unresolved_response(user_id, active=True)

    if unresolved:
        return unresolved

    elif all(v is None for v in labels):
        response = Response.get_random_ungraded_response(user_id, exercise_id)
        return response
    else:
        responses = Response.all_by_exercise_id(exercise_id)
        forest_name = exercise.forest_name
        vocab = exercise.vocab

        features = np.array(exercise.features)
        obs_idx = np.where(~np.isnan(labels_array))[0]
        log.info(obs_idx)

        if forest_name:
            forest_path = exercise.forest_name
            log.info(forest_path)
            # Load forest and get next best response
            try:
                forest = joblib.load(forest_path)
            except IOError:
                forest = train_random_forest(features[obs_idx],
                                             labels_array[obs_idx])

                joblib.dump(forest, forest_path)

                exercise.forest_name = forest_path
                db.session.add(exercise)
                db.session.commit()

        else:
            # Create random forest, predict best response, and save to disk.
            filename = 'exercise_{0}.pkl'.format(exercise_id)
            log.info(filename)
            forest_path = os.path.join(HERE, '../algs/data', filename)
            log.info(forest_path)
            forest = train_random_forest(features[obs_idx],
                                         labels_array[obs_idx])

            joblib.dump(forest, forest_path)

            exercise.forest_name = forest_path
            db.session.add(exercise)
            db.session.commit()

        prediction_idx = get_min_var_idx(features,
                                         labels_array,
                                         vocab,
                                         forest,
                                         global_grade_count_array,
                                         sample_limit=30)
        return responses[prediction_idx]


def get_next_exercise_id(user_id, subject_id, chapter_id=None):
    """
    Get the next exercise prioritized on if there are any unresolved responses
    for that exercise. Prioritization is based on what is unresolved for that
    response. If there are no unresolved responses an unobserved response is
    returned.

    * Unresolved responses - these are responses that do not have a majority
      vote based on the grades given for the response.

    * Examples *

    1. If a response only has 1 grade then it is unresolved.
    2. If a response has 2 total grades with junk, score, misconception having 2
      different (distinct) grades one of the three criteria is unresolved.
    3. If a response has 3 total grades and score has 3 different (distinct)
      grades the response is unresolved for the score criteria.

    4. If there are no unresolved responses an unobserved exercise is returned.

    * Unobserved response/exercise- an exercise/ response that has not been
      graded by any graders.

    Parameters
    ----------
    user_id
    subject_id
    chapter_id

    Returns
    -------
    exercise_id
    """
    # The user subquery used to remove any responses the grader has graded
    user_subq = db.session.query(ResponseGrade.response_id) \
        .filter(ResponseGrade.user_id == user_id).subquery()
    # The unqualified subquery used to remove any exercises the grader is
    # marked as unqualified to grade.
    unqual_subq = db.session.query(UserUnqualifiedExercise.exercise_id) \
        .filter(UserUnqualifiedExercise.user_id == user_id).subquery()

    # The main query that gets distinct counts of all grader criteria
    g_count = db.session.query(Exercise.id.label('exercise_id'),
                               Response.id.label('response_id'),
                               Exercise.subject_id.label('subject_id'),
                               Exercise.chapter_id.label('chapter_id'),
                               func.count(
                                   func.distinct(ResponseGrade.score)).label(
                                   'score'),
                               func.count(func.distinct(
                                   ResponseGrade.misconception)).label(
                                   'misconception'),
                               func.count(
                                   func.distinct(ResponseGrade.junk)).label(
                                   'junk'),
                               func.count(
                                   func.coalesce(ResponseGrade.id, None)).label(
                                   'total_count')) \
        .join(Response) \
        .outerjoin(ResponseGrade) \
        .filter(~Response.id.in_(user_subq)).filter(
        ~Exercise.id.in_(unqual_subq)) \
        .filter(Exercise.subject_id == subject_id) \
        .filter(Response.active == True) \
        .group_by(Exercise.id, Response.id, Exercise.subject_id,
                  Exercise.chapter_id) \
 \
    # Filter based on the chapter (optional)
    if chapter_id:
        g_count = g_count.filter(Exercise.chapter_id == chapter_id)

    # Get first response that only has one grade.
    g_count_one = g_count.having(func.count(
        func.coalesce(ResponseGrade.id, None)) == 1).first()
    log.info('Checking for any exercises for subject {0} in chapter {1} '
             'that have only 1 grade'.format(subject_id, chapter_id))
    if g_count_one:
        log.info('Exercise {0} with 1 ungraded response was found'.format(
            g_count_one.exercise_id))
        return g_count_one.exercise_id
    else:
        # If responses can't be found with only 1 grade with then we need to
        # look for responses that have 2 to 3 grades and any criteria where
        # graders did not agree. We'll do this by turning
        # the "root" query into a subquery and adjusting the
        # having clause. This is mostly to keep our sanity. We could probably
        # do all of this with having clauses but that would be very unreadable.
        # Once we have the subquery we'll use that as the
        # basis of our result set.
        log.info('An exercise with 1 unresolved response was not found. '
                 'Checking if other responses have unresolved score, '
                 'misconception, or junk')
        g_count_sub = g_count.having(
            and_(
                (func.count(func.coalesce(ResponseGrade.id, None)) > 1),
                (func.count(func.coalesce(ResponseGrade.id, None)) < 4))
        ).subquery()

        # With the global count in the from clause we can now filter based on
        # the total_count a lot easier
        totals = db.session.query(g_count_sub.c.exercise_id,
                                  g_count_sub.c.response_id,
                                  g_count_sub.c.score,
                                  g_count_sub.c.misconception,
                                  g_count_sub.c.junk,
                                  g_count_sub.c.total_count) \
            .order_by(g_count_sub.c.total_count.asc())

        # Check if there are 2 total grades and if there is any disagreement
        g_count_two = totals.filter(and_(g_count_sub.c.total_count == 2,
                                         or_(g_count_sub.c.score > 1,
                                             g_count_sub.c.misconception > 1,
                                             g_count_sub.c.junk > 1)))

        g_count_two = g_count_two.first()

        if g_count_two:
            log.info('Exercise {0} that has a response with two grades and is '
                     'unresolved was found'.format(g_count_two.exercise_id))
            return g_count_two.exercise_id
        else:

            g_count_three = totals.filter(
                and_(
                    g_count_sub.c.total_count == 3,
                    g_count_sub.c.score > 2))

            g_count_three = g_count_three.first()

            if g_count_three:
                log.info(
                    'Exercise {0} that has a response with three grades and is '
                    'unresolved was found'.format(g_count_three.exercise_id))
                return g_count_three.exercise_id
            else:
                g_count = g_count.having(
                    func.count(func.coalesce(
                        ResponseGrade.id, None)) == 0).first()

                if g_count:
                    log.info(
                        'Exercise {0} is unobserved. No unresolved responses '
                        'found'.format(g_count.exercise_id))
                    return g_count.exercise_id
                else:
                    raise Exception('The system no longer has any unobserved '
                                    'and unresolved responses')


def get_parsed_exercise(exercise_id):
    """
    Get the JSON exercise data from the exercise.data field
    This is where the feedback, answers, and other info is located

    Parameters
    ----------
    exercise_id

    Returns
    -------

    """
    exercise = Exercise.get(exercise_id)

    subject = Subject.get(exercise.subject_id)
    answer_html = 'Question not supplied with a correct answer'

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

    # Get number of responses

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
                            func.count(ResponseGrade.id).label(
                                'responses_graded'),
                            label('time_grading',
                                  UserGradingSession.ended_on - UserGradingSession.started_on)) \
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
                             label('time_grading',
                                   UserGradingSession.ended_on - UserGradingSession.started_on)) \
        .join(ResponseGrade, ResponseGrade.session_id == UserGradingSession.id) \
        .filter(UserGradingSession.user_id == user_id,
                UserGradingSession.ended_on != None) \
        .group_by(UserGradingSession.id,
                  UserGradingSession.started_on,
                  UserGradingSession.ended_on) \
        .order_by(UserGradingSession.started_on)

    return query.all()


def get_graded_count(exercise_id):
    query = db.session.query(Response.id,
                             func.count(func.coalesce(ResponseGrade.id, None))) \
        .outerjoin(ResponseGrade) \
        .filter(Response.exercise_id == exercise_id) \
        .group_by(Response.id) \
        .order_by(Response.id)

    return query.all()


def get_admin_metrics():
    subject_count = ResponseGrade.subject_count()
    data = dict(total_grades=ResponseGrade.count(),
                total_responses=Response.count(),
                total_physics=subject_count[0][1],
                total_biology=subject_count[1][1]
                )
    return data


class ResponseGrade(db.Model):
    ___tablename__ = 'response_grades'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    response_id = db.Column(db.Integer(), db.ForeignKey('responses.id'))
    score = db.Column(db.Float())
    misconception = db.Column(db.Boolean())
    explanation = db.Column(db.Text(), nullable=True)
    junk = db.Column(db.Boolean())
    feedback_id = db.Column(db.Integer())
    started_on = db.Column(db.DateTime())
    submitted_on = db.Column(db.DateTime())
    session_id = db.Column(db.Integer(),
                           db.ForeignKey('user_grading_sessions.id'))

    @classmethod
    def count(cls):
        subquery = db.session.query(User.id) \
            .join(Role, User.roles).filter(Role.name == 'admin') \
            .subquery()
        query = db.session.query(ResponseGrade) \
            .filter(~ResponseGrade.user_id.in_(subquery))

        return query.count()

    @classmethod
    def subject_count(cls):
        subquery = db.session.query(User.id) \
            .join(Role, User.roles) \
            .filter(Role.name == 'admin') \
            .subquery()
        query = db.session.query(Subject.name, func.count(ResponseGrade.id)) \
            .join(Response) \
            .join(ResponseGrade) \
            .filter(~ResponseGrade.user_id.in_(subquery)) \
            .group_by(Subject.name)

        return query.all()

    @classmethod
    def latest_by_session_id(cls, session_id):
        query = db.session.query(cls) \
            .filter(cls.session_id == session_id) \
            .order_by(cls.submitted_on.desc())

        return query.first()

    @classmethod
    def get_grades(cls, user_id, exercise_id, active=None):
        expr = case([(cls.junk == True, 0.0)], else_=cls.score)

        query = db.session.query(distinct(Response.id), expr) \
            .outerjoin(cls, and_(cls.response_id == Response.id,
                                 cls.user_id == user_id)) \
            .filter(Response.exercise_id == exercise_id).order_by(Response.id)

        if active:
            query = query.filter(Response.active == True)

        return query.all()

    @classmethod
    def by_user_id(cls, user_id):
        return db.session.query(cls).filter(cls.user_id == user_id).all()

    @classmethod
    def by_user_id_and_response_id(cls, user_id, response_id):
        return db.session.query(cls).filter(cls.user_id == user_id,
                                            cls.response_id == response_id).first()


class Response(db.Model, JsonSerializer):
    __tablename__ = 'responses'
    id = db.Column(db.Integer(),
                   primary_key=True)  # The corresponding columns in the spreadsheet
    external_id = db.Column(db.Integer())  # X.1
    step_id = db.Column(db.Integer(),
                        unique=True)  # Basically the unique id of the response
    deidentifier = db.Column(db.String())  # Deidentifier
    free_response = db.Column(db.Text())  # Free.Response
    correct = db.Column(db.Boolean())  # Correct.
    correct_answer_id = db.Column(db.Integer())  # Correct.Answer.Id
    exercise_type = db.Column(db.String())  # Exercise.type
    exercise_id = db.Column(db.Integer(), db.ForeignKey('exercises.id'))
    subject = db.Column(db.String())
    subject_id = db.Column(db.Integer(), db.ForeignKey('subjects.id'))
    created_on = db.Column(db.DateTime(), default=datetime.utcnow())
    updated_on = db.Column(db.DateTime(), default=datetime.utcnow(),
                           onupdate=datetime.utcnow())
    active = db.Column(db.Boolean())

    @classmethod
    def count(cls):
        return db.session.query(cls).count()

    @classmethod
    def get(cls, response_id):
        return db.session.query(cls).get(response_id)

    @classmethod
    def all_by_exercise_id(cls, exercise_id, active=None):
        query = db.session.query(cls) \
            .filter(cls.exercise_id == exercise_id) \
            .order_by(cls.id)
        if active:
            query = query.filter(cls.active == True)

        return query.all()

    @classmethod
    def all_by_exercise_id_excluding_user(cls, exercise_id, user_id):
        return db.session.query(cls) \
            .filter(cls.exercise_id == exercise_id) \
            .filter(cls.user_id != user_id) \
            .order_by(cls.id) \
            .all()

    @classmethod
    def get_random_ungraded_response(cls, user_id, exercise_id, active=None):
        subquery = db.session.query(ResponseGrade.response_id) \
            .join(Response).filter(ResponseGrade.user_id == user_id).subquery()
        query = db.session.query(Response).filter(
            Response.exercise_id == exercise_id) \
            .filter(~Response.id.in_(subquery)).filter().order_by(func.random())

        if active:
            query = query.filter(Response.active == True)

        return query.first()

    def grade_counts(self):
        response = db.session.query(Response.id,
                                    func.count(
                                        func.distinct(ResponseGrade.score)),
                                    func.count(func.distinct(
                                        ResponseGrade.misconception)),
                                    func.count(
                                        func.distinct(ResponseGrade.junk)),
                                    func.count(
                                        func.coalesce(ResponseGrade.id, None))) \
            .outerjoin(ResponseGrade) \
            .filter(Response.id == self.id) \
            .group_by(Response.id)
        return response.first()

    def determine_unresolved(self):
        grades = self.grade_counts()

        score = grades[1]
        misconception = grades[2]
        junk = grades[3]
        total_grades = grades[4]

        if total_grades == 1:
            return True

        elif total_grades == 2:
            if score > 1 or misconception > 1 or junk > 1:
                return True
            else:
                return False

        elif total_grades == 3:
            if score > 2:
                return True
            else:
                return False
        else:
            return False

    @property
    def is_unresolved(self):
        """
        A response can be resolved if there is a majority vote on the label.
        If there is not a majority vote then the response is unresolved.

        Returns
        -------
        Boolean
        """
        return self.determine_unresolved()

    @property
    def is_unobserved(self):
        """
        An unobserved response is a response that has not yet been graded.
        Returns
        -------
        Boolean
        """
        grades = self.grade_counts()
        if grades[4] == 0:
            return True
        else:
            return False


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
    vocab = db.Column(ARRAY(db.String()))
    created_on = db.Column(db.DateTime(), default=datetime.utcnow())
    updated_on = db.Column(db.DateTime(), default=datetime.utcnow(),
                           onupdate=datetime.utcnow())

    responses = db.relationship('Response')

    @classmethod
    def get(cls, exercise_id):
        return db.session.query(cls).get(exercise_id)

    def has_unresolved_responses(user_id, exercise_id):
        user_subq = db.session.query(ResponseGrade.response_id) \
            .filter(ResponseGrade.user_id == user_id).subquery()

        responses = db.session.query(Response) \
            .filter(Response.exercise_id == exercise_id) \
            .filter(~Response.id.in_(user_subq)) \
            .all()
        unresolved = False
        for response in responses:
            if response.is_unresolved:
                unresolved = True
                return unresolved

        return unresolved

    @property
    def is_unobserved(self):
        responses = Response.all_by_exercise_id(self.id)
        unobserved = True
        for response in responses:
            if not response.is_unobserved:
                return False

        return unobserved

    def get_unresolved_response(self, user_id, active=None):
        user_subq = db.session.query(ResponseGrade.response_id) \
            .filter(ResponseGrade.user_id == user_id).subquery()

        responses = db.session.query(Response) \
            .filter(Response.exercise_id == self.id) \
            .filter(~Response.id.in_(user_subq)) \
            .all()

        if active:
            responses = responses.filter(Response.active == True)

        for response in responses:
            if response.is_unresolved:
                return response


class ExerciseNote(db.Model, JsonSerializer):
    __tablename__ = 'user_exercise_notes'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('users.id'))
    exercise_id = db.Column(db.Integer(), db.ForeignKey('exercises.id'))
    text = db.Column(db.Text())
    created_on = db.Column(db.DateTime)

    @classmethod
    def get_by_user_id(cls, user_id, exercise_id):
        return db.session.query(cls) \
            .filter(cls.user_id == user_id, cls.exercise_id == exercise_id) \
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
        return db.session.query(cls) \
            .filter(cls.user_id == user_id) \
            .order_by(cls.ended_on.desc()) \
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
