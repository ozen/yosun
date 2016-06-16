# Yosun

Yosun is a simple pub/sub utility for [Kombu]. 

Give Yosun a connection and a topic exchange and it provides a nice interface for pub/sub. 

## Installation

```
pip install yosun
```

## Creating Yosun Object

```python
from kombu import Connection, Exchange
from yosun import Yosun

connection = Connection('amqp://guest:guest@localhost:5672//')
exchange = Exchange('my_topic_exchange', type='topic')

yosun = Yosun(connection, exchange)
```

## Publishing

Publish method takes routing key and payload parameters:

```python
yosun.publish('my.routing.key', {'hello': 'world'})
```

You can omit the payload which defaults to an empty dictionary.

```python
yosun.publish('my.routing.key')
```

`publish` method by default blocks the execution until message is sent. You can add `block=False` parameter to make 
publish return immediately, and message will be sent in a background thread.

```python
# this will return after creating a thread that will send the message
yosun.publish('my.routing.key', {'hello': 'world'}, block=False)  
```

### Make Permenant Additions to Payloads

Yosun object has a dictionary property named `payload`. Content of `payload` will be added
to the payload given to the publish method.

```python
yosun.payload['sender'] = 'Yigit Ozen'

# this will publish {'sender': 'Yigit Ozen', 'hello': 'world'}
yosun.publish('my.routing.key', {'hello': 'world'})

# sender will still be added if you omit the payload parameter. 
# this will publish {'sender': 'Yigit Ozen'}
yosun.publish({'my.routing.key')

# use del to stop adding a key-value pair to the payloads
del yosun.payload['sender']
```

## Subscribing

Yosun's `subscribe` method creates and returns a Subscription object. Subscription creates a 
queue and starts consuming it on a separate thread. 

`on` method registers a callback for a certain routing key.
 
`all` method registers a callback for all routing keys.

The signature of the callbacks must take two arguments: (body, message), which is the decoded message body and Kombu Message instance.

`wait` method blocks until a message arrives with the given routing key.

`wait_any` method blocks until any message arrives.

```python
def on_rabbit(body, message):
    print('Look, a rabbit!')
    print(body)
    
sub = yosun.subscribe('animals.#')

# from now on when a animals.rabbit message arrives, on_rabbit will be called
sub.on('animals.rabbit', on_rabbit)

# when any message matching animals.# arrives, on_animal will be called
sub.all(on_animal)

# this will block the program until an animals.rabbit message arrives
sub.wait('animals.rabbit')

# wait has the same semantic with Python's multithreading wait. so you can pass a timeout.
# return value will be true if a message arrives before the timeout, false otherwise
arrived = sub.wait('animals.rabbit', timeout=10)

# blocks until any message arrives
sub.wait_any()
```

`on` and `all` methods return the Subscription object, so what you can chain the calls.

```python
sub = yosun.subscribe('animals.#')
            .on('animals.rabbit', on_rabbit)
            .on('animals.turtle', on_turtle)
            .all(on_animal)
```

### Stop and Restart Consuming

Subscription creates a queue and starts a thread that consumes it upon creation.
You can destroy the queue and the thread without destroying the Subscription, and you can recreate them later.

```python
# starts listening for the events
sub = yosun.subscribe('animals.#')
            .on('animals.rabbit', on_rabbit)
            .on('animals.turtle', on_turtle)

# you don't want to receive messages for a while
sub.stop()

# the registered callbacks are still there.
# you can recreate the queue and start receiving messages again.
sub.start()
```

If you don't keep the subscription in a variable, you can use `unsubscribe` method of Yosun object by binding key 
to stop consuming.

```python
yosun.unsubscribe('animals.#')
```

## Prefixing Routing Keys

You can pass a key prefix when initializing Yosun object, which will be automatically prefixed all routing keys 
when subscribing and publishing. If you use Yosun object to pub/sub in a specific namespace, this will save you 
from adding the prefix manually for all pub/sub calls.

```python
yosun = Yosun(connection, exchange, key_prefix='my.namespace.')

# this will actually subscribe to 'my.namespace.animals.#'
sub = yosun.subscribe('animals.#')

# on_rabbit will be called for messages with the key 'my.namespace.animals.rabbit'
sub.on('animals.rabbit', on_rabbit)

# this will publish the message with the key 'my.namespace.my.routing.key'
yosun.publish({'my.routing.key', 'hello': 'world'})
```


[Kombu]: https://github.com/celery/kombu