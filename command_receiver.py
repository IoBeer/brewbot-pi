from google.cloud import pubsub
from commons import Commons
import time
from threading import Thread
import command_processor

CMD_TOPIC = "command-" + Commons.getserial()
SUBS_NAME = "command_rcv"
pubsub_client = None


def topic_exist():
    global pubsub_client

    for topic in pubsub_client.list_topics():
        if topic.name == CMD_TOPIC:
            return True

    return False


def create_topic(topic_name):
    """Create a new Pub/Sub topic."""
    global pubsub_client
    topic = pubsub_client.topic(topic_name)

    topic.create()

    print('Topic {} created.'.format(topic.name))


def subscription_exist():
    """Lists all subscriptions for a given topic."""
    global pubsub_client
    topic = pubsub_client.topic(CMD_TOPIC)

    for subscription in topic.list_subscriptions():
        if subscription.name == SUBS_NAME:
            return True
    return False


def create_subscription(topic_name, subscription_name):
    """Create a new pull subscription on the given topic."""
    global pubsub_client
    topic = pubsub_client.topic(topic_name)

    subscription = topic.subscription(subscription_name)
    subscription.create()

    print('Subscription {} created on topic {}.'.format(
        subscription.name, topic.name))


def receive_message(topic_name, subscription_name):
    """Receives a message from a pull subscription."""
    global pubsub_client
    topic = pubsub_client.topic(topic_name)
    subscription = topic.subscription(subscription_name)

    # Change return_immediately=False to block until messages are
    # received.
    results = subscription.pull(return_immediately=True)

    print('Received {} messages.'.format(len(results)))

    for ack_id, message in results:
        print "Sending to processor."
        proccess_command(message)

    # Acknowledge received messages. If you do not acknowledge, Pub/Sub will
    # redeliver the message.
    if results:
        print "Sending acknowledge"
        subscription.acknowledge([ack_id for ack_id, message in results])


def proccess_command(cmd_msg):
    print('* {}: {}, {}'.format(
        cmd_msg.message_id, cmd_msg.data, cmd_msg.attributes))
    Thread(target=command_processor.process_command(cmd_msg.data)).start()
    return True


def start_command_reicever():
    global pubsub_client

    pubsub_client = pubsub.Client()

    print "Checking topic"
    if not topic_exist():
        print "Topic not found. Creating!"
        create_topic(CMD_TOPIC)

    print "Checking subscription"
    if not subscription_exist():
        print "Subscription not found. Creating!"
        create_subscription(CMD_TOPIC, SUBS_NAME)

    while True:
        print "Checking messages..."
        receive_message(CMD_TOPIC, SUBS_NAME)
        time.sleep(1)
