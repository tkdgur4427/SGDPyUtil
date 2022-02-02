import queue
import grpc
import threading
from concurrent import futures

from utils.singleton_utils import SingletonInstance
from utils.logging_utils import Logger

from functools import wraps
from types import MethodType

"""
importing proto generated python code
"""

# importing common_pb2 and common_pb2_grpc
from proto.python import common_pb2
from proto.python import common_pb2_grpc


class Message:
    """
    message from RPC framework
    """

    def __init__(self, string_msg=""):
        # class member variables
        self.sender_name = ""
        self.procedure_name = ""
        self.parameters = {}

        # decompose string msg
        self.decompose(string_msg)

        return

    def decompose(self, string_msg):
        # split string msg by '\t'(== |...|...|)
        message_content = string_msg.split("\t")

        # get sender name
        self.sender_name = message_content[0]

        # get procedure name
        if len(message_content) > 1:
            self.procedure_name = message_content[1]

        # process parameters
        if len(message_content) > 2:
            parameters = message_content[2]

            # split parameters by ','
            parameters = parameters.split(",")

            # loop parameters
            for parameter in parameters:
                # decompose name and value for parameter
                parameter_name, parameter_value = parameter.split(":")

                # validation checking
                if parameter_name in self.parameters:
                    Logger.instance().info(
                        f"overlapped parameter name, so skip parameter[{parameter_name}]"
                    )
                    continue

                # add parameters
                self.parameters[parameter_name] = parameter_value

        return

    def compose(self):
        message_content = []

        # compose sender_name
        message_content.append(self.sender_name)

        # compose procedural name
        if self.procedure_name != "":
            message_content.append(self.procedure_name)

        # compose parameters
        if len(self.parameters) > 0:
            # make array of parameters by (name, value) pair
            parameters = []

            for parameter_name, parameter_value in self.parameters.items():
                parameter = ":".join([parameter_name, parameter_value])
                parameters.append(parameter)

            parameter_content = ",".join(parameters)
            message_content.append(parameter_content)

        # compose all
        message = "\t".join(message_content)

        return message


class RPC:
    """remote procedure call"""

    def __init__(self, procedure_name, function):

        # set the procedure name
        self.name = procedure_name

        # set the function
        self.function = function

        return

    def execute(self, *args, **kargs):
        # call remote procedure call (function call)
        self.function(*args, **kargs)
        return


class Connection:
    def __init__(self, name):
        # process/user name
        self.name = name

        # recv message queue
        self.recv_message_queue = queue.Queue()

        # send message queue
        self.send_message_queue = queue.Queue()

        return

    def send_message(self, message: Message):
        """all send message is pending call"""
        self.send_message_queue.put(message)
        return

    def recv_message(self, message: Message):
        """all recv message is pending call"""
        self.recv_message_queue.put(message)
        return


class ConnectionCmd:
    def __init__(self, name, cmd):
        """
        name: connection name
        cmd: 'add' or 'remove'
        """
        self.name = name
        self.cmd_type = cmd
        return


class MessageRouter(SingletonInstance):
    def __init__(self):
        # define RPCs
        self.rpcs = {}

        return

    def register_rpc(self, rpc: RPC):
        if rpc.name in self.rpcs:
            Logger.instance().info(
                f"[ERROR][register_rpc] RPC[{rpc.name}] is already registered"
            )
            return False

        self.rpcs[rpc.name] = rpc
        return True

    def unregister_rpc(self, rpc_name):
        # whether it has message type
        if rpc_name in self.rpcs:
            self.rpcs.pop(rpc_name)
            return True

        Logger.instance().info(
            f"[ERROR][unregister_rpc] RPC[{rpc_name}] is not registered"
        )
        return False

    def dispatch(self, message_queue):
        """process message queue by executing RPC"""
        while not message_queue.empty():

            # get the message from the queue
            message = message_queue.get()

            # decompose rpc data from message
            rpc_name = message.procedure_name
            rpc_parameters = message.parameters

            # get the rpc
            rpc = self.rpcs[rpc_name]

            # execute rpc
            rpc.execute(**rpc_parameters)

        return


class ServerRPC:
    def __init__(self, *args, **kargs):
        # grpc server instance
        self.server = type(None)

        # attributes
        self.is_quit = False

        # connections
        self.connections = {}

        # pending queues
        self.connection_queue = queue.Queue()
        self.recv_message_queue = queue.Queue()
        self.send_message_queue = queue.Queue()

        return

    def create_server(self, port_number):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        common_pb2_grpc.add_ServiceRPCServicer_to_server(ServiceRPC(), self.server)
        self.server.add_insecure_port(f"[::]:{port_number}")
        self.server.start()
        return

    def destroy_server(self):
        self.server.stop()
        self.server = type(None)
        return

    def add_connection(self, name):
        if name in self.connections:
            Logger.instance().info(
                f"[ERROR][add_connection] same name connection already exists"
            )
            return False

        new_connection = Connection(name)
        self.connections[name] = new_connection
        return True

    def remove_connection(self, name):
        if name in self.connections:
            self.connections.pop(name)
            return True

        Logger.instance().info(f"[ERROR][remove_connection] no name connection exists")
        return False

    def update(self):
        """process connections"""
        while not self.connection_queue.empty():
            connection_cmd = self.connection_queue.get()
            if connection_cmd.cmd_type == "add":
                self.add_connection(connection_cmd.name)
            elif connection_cmd.cmd_type == "remove":
                self.remove_connection(connection_cmd.name)

        """distribute received message to appropriate connection's message queue"""
        while not self.recv_message_queue.empty():
            message = self.recv_message_queue.get()

            # put message to corresponding connection's message queue
            if not (message.sender_name in self.connections):
                Logger.instance().info(
                    f"no sender name[{message.sender_name}] exists in connection"
                )
                continue

            self.connections[message.sender_name].recv_message(message)

        """dispatch recv_message_queue for each connection"""
        for connection_name, connection in self.connections.items():
            # dispatch router for each connection's recv_message_queue
            MessageRouter.instance().dispatch(connection.recv_message_queue)

        """distribute send_message to corresponding connection's message queue"""
        while not self.send_message_queue.empty():
            message = self.send_message_queue.get()

            # put message to corresponding connection's message queue
            if not (message.sender_name in self.connections):
                Logger.instance().info(
                    f"no sender name[{message.sender_name}] exists in connection"
                )
                continue

            send_message_queue = self.connections[message.sender_name].send_message(
                message
            )

        return

    def send_message(self, message: Message, dest_connection_name=""):
        """
        send message
        @param message: content
        @param dest_connection_name: if it is NOT specified, it tries to BROADCAST
        """
        if dest_connection_name == "":
            # broadcast the message to all connections
            for connection_name, connection in self.connections.items():
                connection.send_message_queue.put(message)

            return
        else:
            # send message to arbitrary connection with sender
            if dest_connection_name in self.connections:
                self.connections[dest_connection_name].send_message_queue.put(message)

        return


class ServiceRPC(common_pb2_grpc.ServiceRPC):
    def __init__(self):
        return

    def from_server(self, request, context):
        """
        this is a response-stream type call
        * this means the server can keep sending messages
        * every client opens this connection and waits for server to send new messages
        """
        # for every client a infinite loop starts (in gRPC's own managed thread)
        while not GlobalRPC.instance().server.is_quit:
            # first get the sender from the message
            message = Message(request.message)
            sender_name = message.sender_name

            # get the connection
            connections = GlobalRPC.instance().server.connections
            if not sender_name in connections:
                Logger.instance().info(f"no connection exists[name: {sender_name}]")
                continue

            connection = connections[sender_name]

            # flush send_message_queue for the connection
            while not connection.send_message_queue.empty():
                message = connection.send_message_queue.get()
                message_string = message.compose()

                # sending response as PacketRPC
                response = common_pb2.PacketRPC()
                response.message = message_string
                yield response

    def to_server(self, request, context):
        # create Message
        message = Message(request.message)

        # enqueue message to the recv_message_queue of MessageRouter
        GlobalRPC.instance().server.recv_message_queue.put(message)

        return common_pb2.Empty()

    def connect(self, request, context):
        connection_cmd = ConnectionCmd(request.name, "add")
        GlobalRPC.instance().server.connection_queue.put(connection_cmd)

        return common_pb2.Empty()

    def disconnect(self, request, context):
        connection_cmd = ConnectionCmd(request.name, "remove")
        GlobalRPC.instance().server.connection_queue.put(connection_cmd)

        return common_pb2.Empty()


class ClientRPC:
    def __init__(self, name):
        # client name (this should be unique in the server)
        self.name = name

        # client instance
        self.client = type(None)
        self.channel = type(None)

        # listen thread
        self.listen_thread = type(None)
        self.listen_thread_is_running = True

        # recv message queue
        self.recv_message_queue = queue.Queue()
        # send message queue
        self.send_message_queue = queue.Queue()

        return

    def connect(self, address, port_number):
        # create rpc channel + stub
        self.channel = grpc.insecure_channel(address + ":" + str(port_number))
        self.client = common_pb2_grpc.ServiceRPCStub(self.channel)

        # connect to the client
        request = common_pb2.PacketConnectionReq()
        request.name = self.name
        self.client.connect(request)

        # create new listening thread for when new message streams comes in
        self.listen_thread = threading.Thread(
            target=self.listen_thread_main, daemon=True
        )
        self.listen_thread.start()

        return

    def disconnect(self):
        # terminate the listen-thread
        self.listen_thread_is_running = False
        self.listen_thread.join()

        # close connection
        request = common_pb2.PacketConnectionReq()
        request.name = self.name
        self.client.disconnect(request)

        # close client
        self.channel.close()

        return

    def listen_thread_main(self):
        """listen incoming messages from server"""
        # generate message
        string_msg = "\t".join([self.name])
        message = Message(string_msg)

        # create packet
        request = common_pb2.PacketRPC()
        request.message = message.compose()

        for incoming_message in self.client.from_server(request):
            # check terminate condition
            if self.listen_thread_is_running == False:
                break

            # decompose incoming_message into Message
            message = Message(incoming_message.message)

            # put the message into queue
            self.recv_message_queue.put(message)

        return

    def send_message(self, message: Message):
        self.send_message_queue.put(message)
        return

    def update(self):
        """process RPC by its recv_message_queue"""
        MessageRouter.instance().dispatch(self.recv_message_queue)

        """send pending messages"""
        while not self.send_message_queue.empty():
            # get the message and compose it to string
            message = self.send_message_queue.get()
            message_string = message.compose()

            # generate request
            reqeust = common_pb2.PacketRPC()
            reqeust.message = message_string

            # send request
            self.client.to_server(reqeust)

        return


class GlobalRPC(SingletonInstance):
    def __init__(self):
        self.client = type(None)
        self.server = type(None)
        return

    def set_server(self, server: ServerRPC):
        self.server = server
        return

    def set_client(self, client: ClientRPC):
        self.client = client
        return

    def update(self):
        if self.server != type(None):
            self.server.update()
        if self.client != type(None):
            self.client.update()
        return


class register_rpc:
    """register RPC(remote procedure call) decorator"""

    def __init__(self, function):
        # register rpc to MessageRouter
        new_rpc = RPC(function.__qualname__, function)
        MessageRouter.instance().register_rpc(new_rpc)
        return
