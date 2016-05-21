# Yosun

Yosun is a simple pub/sub client built on top of [Kombu]. 

It supports publishing and subscribing using a single topic exchange and a single connection.


## Installation

```
pip install yosun
```

## Creating Client Object

```python
from yosun import Client
client = Client(hostname='amqp://guest:guest@localhost:5672//', exchange_name='my_topic_exchange')
```

## Publishing

```python
client.publish('my.routing.key', {'hello': 'world'})
```

`publish` method blocks until message is sent. There is an alternative method with the same signature, 
`publish_async`, which creates a thread that will send the message and returns immediately.

```python
# this will return after creating a thread  
client.publish_async('my.routing.key', {'hello': 'world'})  
```

### Make Permenant Additions to Payloads

Client object has a dictionary property named `payload`. Content of `payload` will be added
to the payload given to the publish method.

```python
client.payload['sender'] = 'Yigit Ozen'

# will publish {'sender': 'Yigit Ozen', 'hello': 'world'}
client.publish('my.routing.key', {'hello': 'world'})

# use del to stop adding a key-value pair to the payloads
del client.payload['sender']
```

## Subscribing

Client's `subscribe` method creates and returns a Subscription object. Subscription creates a 
queue and starts consuming it on a separate thread. 

`Subscription.on` registers a callback for a certain routing key.
 
`Subscription.all` registers a callback for all routing keys.

The signature of the callbacks must take two arguments: (body, message), which is the decoded message body and Kombu Message instance.

`Subscription.wait` blocks until a message arrives with the given routing key.

`Subscription.wait_any` blocks until any message arrives.

```python
def on_rabbit(body, message):
    print('Look, a rabbit!')
    print(body)
    print(message)
    
sub = client.subscribe('animals.#')

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
sub = client.subscribe('animals.#')
            .on('animals.rabbit', on_rabbit)
            .on('animals.turtle', on_turtle)
            .all(on_animal)
```

### Stop and Restart Consuming

Subscription creates a queue and starts a thread that consumes it upon creation.
You can destroy the queue and the thread without destroying the Subscription, and you can recreate them later.

```python
# starts listening for the events
sub = client.subscribe('animals.#')
            .on('animals.rabbit', on_rabbit)
            .on('animals.turtle', on_turtle)

# you don't want to receive messages for a while
sub.stop()

# the registered callbacks are still there.
# you can recreate the queue and start receiving messages again.
sub.start()
```

[Kombu]: https://github.com/celery/kombu