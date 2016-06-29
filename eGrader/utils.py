import csv
from StringIO import StringIO
from functools import wraps

import sqlalchemy as db
from datetime import datetime

from flask import Response

from eGrader.exceptions import api_error_handler
from jinja2 import Markup
from sqlalchemy.sql.expression import extract


def to_csv(field_names, collection):

    def get_att(model, att):
        att = getattr(model, att)
        att = att.encode('utf8') if type(att) is unicode else att
        return ' '.join(str(att).split())

    def make_row(model):
        return {att: get_att(model, att) for att in field_names}

    def make_writer(sio):
        return csv.DictWriter(sio, field_names, dialect='excel-tab')

    # yield header
    sio = StringIO()
    w = make_writer(sio)
    w.writeheader()
    yield sio.getvalue()

    # yield rows
    for model in collection:
        row = make_row(model)
        sio = StringIO()
        w = make_writer(sio)
        w.writerow(row)
        yield sio.getvalue()


def render_csv(field_names, collection, filename, datestamp='True'):
    if datestamp:
        filename = datetime.now().strftime(filename + '-%Y%m%d.csv')
    else:
        filename = filename + '.csv'

    return Response(to_csv(field_names, collection),
                    mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment;filename=" + filename})


def xtract(label, expr):
    return extract('EPOCH', expr).label(label)


class Executor(object):
    """The :class: `Executor` acts both as a context manager and a
       decorator.

       An instance of the executor can be created by passing in
       the SQL Alchemy connection uri. ::

           executor = Executor('<sqlalchemy uri>')

           # in a flask app, for example:
           executor = Executor(app.config['sqlalchemy.url'], debug=app.debug)


       To use the executor as a context manager::

           def insert_into(table, values):
               with executor as connection:
                   statement = table.insert().values(**values)
                   result = connection.execute(statement)
               return result

       The same can be done using the :class: `Executor` as a decorator::

           @executor
           def insert_into(table, values):
               return table.insert().values(**values)

       As a decorator, the executor expects the decorated function to
       return a SQL Alchemy statement that can be passed on to the SQL
       Alchemy connection for execution.

       :param connection_string:  The DB connection string.

       :param debug: Enable debug mode.  Result contains verbose error details.

       :param exception_handler: The exception handler to use to
       transform exceptions to return values.  :func:
       `api_error_handler` is used if this is not provided.

    """

    def __init__(self, connection_string, debug=False, exception_handler=None):
        self.connection_string = connection_string
        self.debug = debug
        self._handler = exception_handler or api_error_handler
        self._conn = None

    def __enter__(self):
        if self._conn:
            raise RuntimeError('This executor is already open.')

        engine = db.create_engine(self.connection_string,
                                  convert_unicode=True)
        self._conn = engine.connect()
        return self._conn

    def __exit__(self, e_typ, e_val, e_trc):
        if not self._conn:
            raise RuntimeError('This executor is not open.')
        self._conn.close()
        self._conn = None
        if e_val:
            raise self._handler(e_val, self.debug), None, e_trc

    def __call__(self, *args, **kwargs):
        """
        :param fetch_all:  Calls fetch_all on the statement instead of
        returning the :class: `ResultProxy`.
        """
        fetch_all = False

        def deco(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                with self as connection:
                    result = connection.execute(fn(*args, **kwargs))
                    if fetch_all:
                        singleton = len(result.keys()) == 1
                        result = result.fetchall()
                        if singleton:
                            result = [v[0] for v in result]
                return result
            return wrapped

        if len(args) == 1 and callable(args[0]):
            fetch_all = False
            return deco(args[0])

        if 'fetch_all' in kwargs:
            fetch_all = kwargs['fetch_all']
        elif len(args) == 1:
            fetch_all = args[0]

        return deco


class JsonSerializer(object):
    """A mixin that can be used to mark a SQLAlchemy model class which
    implements a :func:`to_json` method. The :func:`to_json` method is used
    in conjuction with the custom :class:`JSONEncoder` class. By default this
    mixin will assume all properties of the SQLAlchemy model are to be visible
    in the JSON output. Extend this class to customize which properties are
    public, hidden or modified before being being passed to the JSON serializer.
    """

    __json_public__ = None
    __json_hidden__ = None
    __json_modifiers__ = None

    def get_field_names(self):
        for p in self.__mapper__.iterate_properties:
            yield p.key

    def to_json(self):
        field_names = self.get_field_names()

        public = self.__json_public__ or field_names
        hidden = self.__json_hidden__ or []
        modifiers = self.__json_modifiers__ or dict()

        rv = dict()
        for key in public:
            rv[key] = getattr(self, key)
        for key, modifier in modifiers.items():
            value = getattr(self, key)
            rv[key] = modifier(value, self)
        for key in hidden:
            rv.pop(key, None)
        return rv


class MomentJS(object):
    def __init__(self, timestamp, timestamp2=None):
        self.timestamp = timestamp
        self.timestamp2 = timestamp2


    def render(self, format):
        return Markup("<script>\ndocument.write(moment(\"%s\").%s);\n</script>") \
               % (self.timestamp.strftime('%Y-%m-%dT%H:%M:%S Z'), format)

    def format(self, fmt):
        return self.render(Markup("format(\"%s\")" % fmt))

    def calendar(self):
        return self.render('calendar()')

    def fromNow(self):
        return self.render('fromNow()')

    def simple(self):
        return self.format('lll')

    def time_from(self):
        return Markup("""
            <script>
            var a = moment("%s")
            var b = moment("%s")

            document.write(a.from(b, true))
            </script>
            """ % (self.timestamp.strftime('%Y-%m-%dT%H:%M:%S Z'),
                   self.timestamp2.strftime('%Y-%m-%dT%H:%M:%S Z')))
