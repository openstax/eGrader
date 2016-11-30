from eGrader.core import db
from eGrader.models import UserGradingSession
from eGrader.models import ResponseGrade

def update_grading_sessions_end_times():

    sessions = db.session.query(UserGradingSession).all()

    for session in sessions:
        grades = db.session.query(ResponseGrade).filter(ResponseGrade.session_id == session.id).all()
        if grades:
            print('Latest grade for session_id {0}'.format(session.id))
            latest_grade = db.session.query(ResponseGrade)\
                .filter(ResponseGrade.session_id == session.id)\
                .order_by(ResponseGrade.submitted_on.desc()).first()
            print(latest_grade.submitted_on)
            first_grade = db.session.query(ResponseGrade)\
                .filter(ResponseGrade.session_id == session.id)\
                .order_by(ResponseGrade.submitted_on.asc()).first()

            session.ended_on = latest_grade.submitted_on

            db.session.add(session)
            db.session.commit()
        else:
            db.session.delete(session)
            db.session.commit()
            print('Deleting session {0}'.format(session.id))
