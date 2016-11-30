import sqlalchemy as db
from sqlalchemy.dialects.postgresql import ARRAY

from eGrader import create_app
from eGrader.utils import Executor

from eGrader.algs.parse_responses import parse_responses
from eGrader.algs.WordUtility import WordUtility

grading_parser = WordUtility(corpora_list=[
    'eGrader/algs/word_files/all_plaintext.txt',
    'eGrader/algs/word_files/big.txt'],
    parse_args=(True, False, True, True, True))

app = create_app()

app_config = app.config['SQLALCHEMY_DATABASE_URI']

executor = Executor(app_config, debug=True)

metadata = db.MetaData()

exercises_table = db.Table(
    'exercises',
    metadata,
    db.Column('id', db.Integer, primary_key=True),
    db.Column('features', ARRAY(db.Integer())),
    db.Column('forest_name', db.String),
    db.Column('vocab', ARRAY(db.String()))
)

responses_table = db.Table(
    'responses',
    metadata,
    db.Column('id', db.Integer, primary_key=True),
    db.Column('exercise_id', db.Integer),
    db.Column('free_response', db.String)
)


@executor
def update_field(table, where_column, where_value, values):
    return table.update().where(where_column == where_value) \
        .values(values)


@executor
def insert_into(table, values):
    return table.insert().values(values)


@executor(fetch_all=True)
def get_exercises():
    sel = db.select([exercises_table.c.id, exercises_table.c.features])

    return sel


@executor(fetch_all=True)
def get_exercise_responses(exercise_id):
    sel = db.select([responses_table.c.id,
                     responses_table.c.free_response])

    sel = sel.where(responses_table.c.exercise_id == exercise_id)

    return sel


def load_exercise_features():
    exercises = get_exercises()
    exercises.sort()

    for ex in exercises:
        ex_id = ex[0]
        responses = get_exercise_responses(ex_id)
        responses.sort()
        print('Processing exercise_id: [{0}]'.format(ex_id))
        features, vocab, clean_all = parse_responses(responses, grading_parser)
        update_field(exercises_table, exercises_table.c.id, ex_id,
                     dict(features=features.tolist()))

    return


def update_exercises_vocab():
    exercises = get_exercises()
    print(len(exercises))
    exercises.sort()

    for ex in exercises:
        ex_id = ex[0]
        responses = get_exercise_responses(ex_id)
        responses.sort()
        print('Processing exercise_id: [{0}]'.format(ex_id))
        features, vocab, clean_all = parse_responses(responses, grading_parser)
        update_field(exercises_table, exercises_table.c.id, ex_id, dict(vocab=vocab))

    return


if __name__ == '__main__':
    load_exercise_features()
    update_exercises_vocab()
