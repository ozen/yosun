import logging
from inspect import isroutine
from socket import timeout
from collections import defaultdict
from time import sleep
from threading import Thread, Event
from kombu import Queue, Consumer
from kombu.pools import producers, connections
from kombu.exceptions import MessageStateError


logger = logging.getLogger(__name__)


class Handler(object):
    def __init__(self, callback, on_exception=None):
        self._callback = callback

        if on_exception is not None:
            if not isroutine(on_exception):
                raise ValueError('on_exception must be a function or method')
            self._on_exception = on_exception
        else:
            self._on_exception = self._default_on_exception

    def __call__(self, *args, **kwargs):
        try:
            self._callback(*args, **kwargs)
        except Exception as e:
            self._on_exception(e)

    def _default_on_exception(self, exception):
        raise exception


class Subscription(object):
    def __init__(self, connection, exchange, binding_key, key_prefix='', reconnect_timeout=10, on_exception=None):
        self._connection = connection
        self._exchange = exchange
        self._binding_key = binding_key
        self._key_prefix = key_prefix
        self._reconnect_timeout = reconnect_timeout

        if on_exception is not None:
            if not isroutine(on_exception):
                raise ValueError('on_exception must be a function or method')
            self._on_exception = on_exception
        else:
            self._on_exception = self._default_on_exception

        self._handlers = defaultdict(list)
        self._handlers_for_all = []
        self._events = {}
        self._event_any = Event()
        self._running = False
        self._thread = None

        self.start()

    def __del__(self):
        self._running = False
        try:
            self._thread.join()
        except Exception as e:
            pass

    def _default_on_exception(self, exception):
        raise exception

    @property
    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if not self._running:
            self._running = True
            self._thread = Thread(target=self._consume)
            self._thread.start()

    def stop(self):
        self._running = False

    def on(self, routing_key, callback, on_exception=None):
        # register a callback for the given routing key
        routing_key = '{0}{1}'.format(self._key_prefix, routing_key)
        self._handlers[routing_key].append(Handler(callback, on_exception))
        return self

    def all(self, callback, on_exception=None):
        # register a callback for all routing keys
        self._handlers_for_all.append(Handler(callback, on_exception))
        return self

    def wait(self, routing_key, timeout=None):
        # register an event wait
        routing_key = '{0}{1}'.format(self._key_prefix, routing_key)
        if routing_key not in self._events:
            self._events[routing_key] = Event()

        return self._events[routing_key].wait(timeout)

    def wait_any(self, timeout=None):
        return self._event_any.wait(timeout)

    def _on_message(self, body, message):
        if not self._running:
            return

        routing_key = message.delivery_info['routing_key']

        if routing_key in self._events:
            self._events[routing_key].set()
            self._events[routing_key].clear()

        self._event_any.set()
        self._event_any.clear()

        for handler in self._handlers[routing_key]:
            try:
                handler(body, message)
            except Exception as e:
                self._on_exception(e)

        for handler in self._handlers_for_all:
            try:
                handler(body, message)
            except Exception as e:
                self._on_exception(e)

        try:
            message.ack()
        except MessageStateError:
            pass

    def _consume(self):
        routing_key = '{0}{1}'.format(self._key_prefix, self._binding_key)

        while self._running:
            try:
                with connections[self._connection].acquire(block=True) as conn:
                    queue = Queue(exchange=self._exchange, routing_key=routing_key, channel=conn,
                                  durable=False, exclusive=True, auto_delete=True)

                    with Consumer(conn, queue, callbacks=[self._on_message]):
                        try:
                            while self._running:
                                try:
                                    conn.drain_events(timeout=10)
                                except timeout:
                                    pass
                        except Exception as e:
                            logger.debug('Error when draining message queue: {0}'.format(e))
            except IOError as e:
                logger.info('Disconnected from MQ Server. Reconnecting in {0} seconds.'.format(
                    self._reconnect_timeout))
                sleep(self._reconnect_timeout)


class Yosun(object):
    def __init__(self, connection, exchange, key_prefix=''):
        self._connection = connection
        self._exchange = exchange
        self._key_prefix = key_prefix
        self._payload = {}
        self._subscriptions = {}

    @property
    def connection(self):
        return self._connection

    @property
    def exchange(self):
        return self._exchange

    @property
    def key_prefix(self):
        return self._key_prefix

    @property
    def payload(self):
        return self._payload

    def subscribe(self, binding_key, reconnect_timeout=10, on_exception=None):
        if binding_key in self._subscriptions and not self._subscriptions[binding_key].is_alive():
            self._subscriptions[binding_key].start()
        elif binding_key not in self._subscriptions:
            self._subscriptions[binding_key] = Subscription(self._connection, self._exchange, binding_key,
                                                            key_prefix=self._key_prefix,
                                                            reconnect_timeout=reconnect_timeout,
                                                            on_exception=on_exception)

        return self._subscriptions[binding_key]

    def unsubscribe(self, binding_key):
        if binding_key in self._subscriptions:
            self._subscriptions[binding_key].stop()

    def _publish(self, routing_key, payload, **kwargs):
        payload.update(self.payload)
        kwargs['exchange'] = self._exchange
        kwargs['routing_key'] = '{0}{1}'.format(self._key_prefix, routing_key)

        with producers[self._connection].acquire(block=True) as producer:
            publish = self._connection.ensure(producer, producer.publish, max_retries=3)
            try:
                publish(payload, **kwargs)
            except OSError as e:
                logger.error("Could not publish '{0}': {1}".format(kwargs['routing_key'], e))
            else:
                logger.debug("Published '{0}'".format(kwargs['routing_key']))

    def publish(self, routing_key, payload=None, block=True, **kwargs):
        if payload is None:
            payload = {}
        elif not isinstance(payload, dict):
            logger.error('payload parameter must be a dictionary')
            raise TypeError("payload parameter must be a dictionary")

        if block:
            self._publish(routing_key, payload, **kwargs)
        else:
            t = Thread(target=self._publish, args=(routing_key, payload), kwargs=kwargs)
            t.start()
