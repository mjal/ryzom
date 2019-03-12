'''
Consumer for Django channels.
Handles websockets messages from client and channels layer
ddp_urlpattern and server_methods are subject to change in a
near future. Both will be handled in a separate file
'''
import importlib
import json

from channels.generic.websocket import JsonWebsocketConsumer
from channels.auth import get_user
from django.contrib.auth.models import User
from asgiref.sync import async_to_sync

from django.conf import settings
from ryzom.models import Clients, Subscriptions, Publications

ddp_urlpatterns = importlib.import_module(settings.DDP_URLPATTERNS).urlpatterns
server_methods = importlib.import_module(settings.SERVER_METHODS).Methods


class Consumer(JsonWebsocketConsumer, object):
    '''
    Consumer class, inherited from the channels' JsonWebsocketConsumer
    '''
    def connect(self):
        '''
        Websocket connect handler.
        This method tries to get the user connecting and create a new
        ryzom.models.Client in DB, saving the channel name for future
        access from the channel layer.
        sends back a 'Connected' message to the client
        '''
        self.accept()
        user = async_to_sync(get_user)(self.scope)
        Clients.objects.create(
                channel=self.channel_name,
                user=user if isinstance(user, User) else None
        )
        self.send(json.dumps({'type': 'Connected'}))

    def disconnect(self, close_code):
        '''
        Websocket disconnect handler.
        Removes the ryzom.models.Clients entry attached to this
        channel, cascading deletion to Suscriptions
        Zombies that may stay in our DB on server reboots are removed in
        the ryzom.apps Appconfig.ready() function
        '''
        Clients.objects.filter(channel=self.channel_name).delete()

    def receive(self, text_data):
        '''
        Websocket message handler.
        Dispatches message to type specific subhandlers after some
        error checking on the message format
        Known message types are 'subscribe', 'unsubscribe', 'method'
        and 'geturl'.
        In a near future, login and logout could be handled too,
        unless we use another way to do it, by method call or anything else
        A message should have:
        - an '_id' key, which is used to find the right
        callback function the client defined
        - a 'type' key, one of the known message types described above
        - a 'params' key, which is used as a parameter, specific to
        each message type.
        '''
        data = json.loads(text_data)
        msg_type = None
        if not data.get('_id', None):
            return
        try:
            msg_type = data['type']
        except KeyError:
            self.send(json.dumps({
                '_id': data['_id'],
                'type': 'Error',
                'params': {
                    'name': 'Bad message',
                    'message': 'message type not found'
                }
            }))
            return

        if msg_type in ['subscribe', 'unsubscribe', 'method', 'geturl']:
            func = getattr(self, f'recv_{msg_type}', None)
            if func:
                try:
                    func(data)
                except KeyError as e:
                    print(e)
                    self.send(json.dumps({
                        '_id': data.get('_id'),
                        'type': 'Error',
                        'params': {
                            'name': 'Bad format',
                            'message': '"params" key not found'
                        }
                    }))
        else:
            self.send(json.dumps({
                '_id': data['_id'],
                'type': 'Error',
                'params': {
                    'name': 'Bad message type',
                    'message': f'{msg_type} not recognized'
                }
            }))

    def recv_geturl(self, data):
        '''
        geturl message handler.
        Creates a new ryzom.views.View based on ddp_urlpattern configuration
        and attach it to this consumer instance.
        Renders the view then send it to the client
        If a view as already been created, destroy it and creates the new one
        view's callback (oncreate, ondestroy) are called here
        '''
        to_url = data['params']['url']
        for url in ddp_urlpatterns:
            if url.pattern.match(to_url):
                cview = getattr(self, 'view', None)
                if cview and isinstance(cview, url.callback):
                    if (cview.onurl(to_url)):
                        self.send(json.dumps({
                            '_id': data['_id'],
                            'type': 'Success',
                            'params': []
                        }))
                else:
                    if cview:
                        cview.ondestroy()
                    self.view = url.callback(self.channel_name)
                    self.view.oncreate(to_url)
                    data = {
                        '_id': data['_id'],
                        'type': 'Success',
                        'params': self.view.render()
                    }
                    self.send(json.dumps(data))
                break

    def recv_method(self, data):
        '''
        method message handler.
        Lookup methods then call them with the 'params' key as parameter.
        Methods writers should handle that params.
        Methods should return a value that evaluates to True on Success.
        Methods return value should be serializable, it will be sent
        to the client as parameter for the callback
        '''
        to_send = {'_id': data['_id']}
        params = data['params']
        method = getattr(server_methods, params['name'], None)
        if method is None:
            to_send.update({
                'type': 'Error',
                'params': {
                    'name': 'Not found',
                    'message': f'Method {params["name"]} not found'
                }
            })
        else:
            ret = method(params['params'])
            if ret:
                to_send.update({
                    'type': 'Success',
                    'params': ret
                })
            else:
                to_send.update({
                    'type': 'Error',
                    'params': ret
                })
        self.send(json.dumps(to_send))

    def insert_component(self, data, change=False):
        '''
        This method is meant to be called by the DDP dispacher.
        It send a DDP insert/change message to the client with
        a serialized component as params
        '''
        self.send(json.dumps({
            'type': 'DDP',
            'params': {
                'type': 'insert' if not change else 'change',
                'params': data['instance']
            }
        }))

    def remove_component(self, data):
        '''
        This method is meant to be called by the DDP dispacher.
        It send a DDP remove message to the client with the parent
        and _id of the component to remove as params
        '''
        self.send(json.dumps({
            'type': 'DDP',
            'params': {
                'type': 'remove',
                'params': {
                    '_id': data['_id'],
                    'parent': data['parent']
                }
            }
        }))

    def handle_ddp(self, data):
        '''
        DDP dispacher.
        handler for 'handle.ddp' messages sent over the channel layer.
        dispaches the message to the above two methods
        '''
        if data['params']['type'] == 'inserted':
            self.insert_component(data['params'])
        elif data['params']['type'] == 'changed':
            self.insert_component(data['params'], True)
        elif data['params']['type'] == 'removed':
            self.remove_component(data['params'])

    def recv_subscribe(self, data):
        '''
        subscribe message handler.
        Creates a new subscription for the current Client.
        'subscribe' params should contain:
        - an '_id' key, which refer to the component that asks for
        a subscription
        - a 'name' key, corresponding to the name of the publication
        this subscription is about
        '''
        params = data['params']
        to_send = {'_id': data['_id']}
        client = Clients.objects.get(channel=self.channel_name)
        for key in ['name', '_id']:
            if key not in params:
                to_send.update({
                    'type': 'Error',
                    'params': {
                        'name': 'Bad format',
                        'message': f'Subscription {key} not found'
                    }
                })
                self.send(json.dumps(to_send))
                return
        if not client:
            to_send.update({
                'type': 'Error',
                'params': {
                    'name': 'Client not found',
                    'message': 'No client was found for this channel name'
                }
            })
        else:
            pub = Publications.objects.get(name=params['name'])
            sub = Subscriptions(
                    publication=pub,
                    parent=params['_id'],
                    client=client)
            sub.init()
            sub.save()
            to_send.update({
                'type': 'Success',
                'params': {
                    'name': params['name'],
                    'sub_id': sub.id
                }
            })
        self.send(json.dumps(to_send))

    def recv_unsubscribe(self, data):
        '''
        unsubscribe message handler.
        not implemented yes but meant to delete the subscription
        attached to the current Client/Publication name from DB
        '''
        params = data['params']
        self.send(json.dumps({
            '_id': data['_id'],
            'type': 'unsubscribed',
            'message': 'Got unsub',
            'params': {
                'name': params['name']
            }
        }))
