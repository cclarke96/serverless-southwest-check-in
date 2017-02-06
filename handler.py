#
# lambda.py
# Lamba functions for interacting with the Southwest API
#

import datetime
import logging
import os
import sys
import time

import boto3
import pendulum

from boto3.dynamodb.conditions import Key

# Add vendored dependencies to path. These are used in swa.py.
sys.path.append('./vendor')

import swa # NOQA

# Set up logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

DYNAMO_TABLE_NAME = os.getenv('DYNAMO_TABLE_NAME')
dynamo = boto3.resource('dynamodb').Table(DYNAMO_TABLE_NAME)


def _get_check_in_time(departure_time):
    """
    Receives a departure time in RFC3339 format:

        2017-02-09T07:50:00.000-06:00

    And returns the check in time (24 hours prior) as a unix timestamp
    """
    dt = pendulum.parse(departure_time)
    check_in_time = dt.replace(second=0, microsecond=0).subtract(days=1)
    return check_in_time.int_timestamp


def _get_check_in_times_from_reservation(reservation):
    """
    """
    flights = reservation['itinerary']['originationDestinations']
    return [
        _get_check_in_time(segment['departureDateTime']) for flight in flights
        for segment in flight['segments']
    ]


def add(event, context):
    """
    Looks up a reservation and adds check in times to DynamoDB
    """
    first_name = event['first_name']
    last_name = event['last_name']
    confirmation_number = event['confirmation_number']

    log.info("Looking up reservation {} for {} {}".format(confirmation_number,
                                                          first_name, last_name))
    reservation = swa.get_reservation(first_name, last_name, confirmation_number)
    log.debug("Reservation: {}".format(reservation))

    check_in_times = _get_check_in_times_from_reservation(reservation)
    log.info("Scheduling check-ins at {}".format(check_in_times))

    for c in check_in_times:
        item = dict(
            check_in=c,
            reservation=confirmation_number,
            first_name=first_name,
            last_name=last_name,
            status='pending'
        )

        log.debug("Check-in entry: {}".format(item))
        dynamo.put_item(Item=item)

    log.info("Successfully added {} check-ins for {}".format(
        len(check_in_times), confirmation_number))


def check_in(event, context):
    """
    Retrieves reservations which are ready to be checked in from DynamoDB and
    checks them in via the Southwest API
    """

    # Get a timestamp for the current minute
    now = _get_minute_timestamp(datetime.datetime.now())
    response = dynamo.query(KeyConditionExpression=Key('check_in').eq(now))

    for reservation in response['Items']:
        # Check in!
        pass
