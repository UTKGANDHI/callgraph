import functools
from functools import wraps
from itertools import starmap
from graphviz import Digraph


class CallGraphRecorder(object):
    def __init__(self, equal=False, label_returns=False, graph_attrs=None):
        self.graph = Digraph(format='svg', strict=True)
        if graph_attrs:
            self.graph.graph_attr.update(**graph_attrs)
        self._options = {'equal': equal, 'label_returns': label_returns}
        self._next_call_idx = 0
        self._callers = []

    def wrap(self, fn):
        "A decorator that wraps fn with instrumentation to record calls."
        @wraps(fn)
        def wrapper(*args, **kwargs):
            with self.record(fn, args, kwargs) as record_return:
                result = fn(*args, **kwargs)
                record_return(result)
                return result
        return wrapper

    def _record(self, caller_id, call_id, fn, args, kwargs, result):
        graph = self.graph
        label_returns = self._options['label_returns']
        label = "{}({}{}{})".format(fn.__name__,
                                    ', '.join(map(repr, args)),
                                    ', ' if args and kwargs else '',
                                    ', '.join(starmap("{}={}".format, kwargs.items())))
        if not (label_returns and caller_id):
            label += " ↦ {}".format(result)
        graph.node(call_id, label)

        if caller_id:
            if label_returns:
                graph.edge(caller_id, call_id, label=str(result), dir='back')
            else:
                graph.edge(caller_id, call_id)
        else:
            graph.node(call_id, penwidth='3')

    def record(self, fn, args, kwargs):
        """Usage:
            with recorder.record(fn, args, kwargs) as record_return:
                …
                record_return(result)
        """
        return CallGraphCallRecorder(self, fn, args, kwargs)

    def _next_call_id(self, fn, args, kwargs):
        if self._options['equal'] or isinstance(fn, functools._lru_cache_wrapper):
            return '{}{}{}'.format(fn, args, kwargs)
        self._next_call_idx += 1
        return str(self._next_call_idx)


class CallGraphCallRecorder(object):
    __slots__ = ['_recorder', '_fn', '_args', '_kwargs']

    def __init__(self, recorder, fn, args, kwargs):
        self._recorder = recorder
        self._fn, self._args, self._kwargs = fn, args, kwargs

    def __enter__(self):
        fn, args, kwargs = self._fn, self._args, self._kwargs
        recorder = self._recorder
        stack = recorder._callers
        caller_id = (stack[-1] if stack else None)
        call_id = recorder._next_call_id(fn, args, kwargs)
        stack.append(call_id)

        def record_return(result):
            recorder._record(caller_id, call_id, fn, args, kwargs, result)
        return record_return

    def __exit__(self, type, value, traceback):
        self._recorder._callers.pop()