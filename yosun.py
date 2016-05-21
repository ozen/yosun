import logging
from socket import timeout
from collections import defaultdict
from time import sleep
from threading import Thread, Event
from kombu import Connection, Exchange, Queue, Consumer
from kombu.pools import producers, connections
from kombu.exceptions import MessageStateError


logger = logging.getLogger(__name__)


class Subscription(object):
    def __init__(self, connection, exchange, binding_key, reconnect_timeout=10):
        self._connection = connection
        self._exchange = exchange
        self._binding_key = binding_key
        self._reconnect_timeout = reconnect_timeout

        self._callbacks = defaultdict(list)
        self._callbacks_for_all = []
        self._events = {}
        self._event_any = Event()

        self._running = True
        self._thread = Thread(target=self._consume)
        self._thread.start()

    def __del__(self):
        self._running = False
        self._thread.join()

    def start(self):
        if not self._running:
            self._running = True
            self._thread = Thread(target=self._consume)
            self._thread.start()

    def stop(self):
        if self._running:
            self._running = False
            self._thread = None

    def on(self, routing_key, callback):
        # register a callback for the given routing key
        self._callbacks[routing_key].append(callback)
        return self

    def all(self, callback):
        # register a callback for all routing keys
        self._callbacks_for_all.append(callback)
        return self

    def wait(self, routing_key, timeout=None):
        # register an event wait
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

        for callback in self._callbacks[routing_key]:
            callback(body, message)

        for callback in self._callbacks_for_all:
            callback(body, message)

        try:
            message.ack()
        except MessageStateError:
            pass

    def _consume(self):
        while self._running:
            try:
                with connections[self._connection].acquire(block=True) as conn:
                    queue = Queue(exchange=self._exchange, routing_key=self._binding_key, channel=conn,
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


class Client(object):
    def __init__(self, exchange_name='amq.topic', **kwargs):
        self._exchange = Exchange(exchange_name, type='topic')
        self._connection = Connection(**kwargs)
        self._payload = {}
        self._subscriptions = {}

    @property
    def payload(self):
        return self._payload

    def subscribe(self, binding_key, reconnect_timeout=10):
        if binding_key not in self._subscriptions:
            self._subscriptions[binding_key] = Subscription(self._connection, self._exchange, binding_key,
                                                            reconnect_timeout=reconnect_timeout)

        return self._subscriptions[binding_key]

    def publish(self, routing_key, payload):
        if not isinstance(payload, dict):
            logger.error('payload parameter must be a dictionary')
            raise TypeError("payload parameter must be a dictionary")

        payload.update(self.payload)

        with producers[self._connection].acquire(block=True) as producer:
            publish = self._connection.ensure(producer, producer.publish, max_retries=3)
            try:
                publish(payload, routing_key=routing_key, exchange=self._exchange)
            except OSError as e:
                logger.error("Could not publish '{0}': {1}".format(routing_key, e))
            else:
                logger.debug("Published '{0}'".format(routing_key))

    def publish_async(self, routing_key, payload):
        if not isinstance(payload, dict):
            logger.error('payload parameter must be a dictionary')
            raise TypeError("payload parameter must be a dictionary")

        t = Thread(target=self.publish, args=(routing_key, payload))
        t.start()
