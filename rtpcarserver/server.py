import logging
import re
import socket
import sys
import threading
import traceback
import random
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from driver import Motor, Servo
from lidar import Lidar
from util import Throttle


logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)
HOST = '' # All available interfaces
PORT = 65432
HANDSHAKE = "HANDSHAKE"
auto = True


class Server:
    def start(self) -> None:
        """Sets up the server socket and waits for incoming connections."""

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        logger.info('Socket created')
        try:
            self.sock.bind((HOST, PORT))
        except socket.error as err:
            print('Bind failed. Error code: {} Message: {}'.format(str(err[0]), err[1]))
            sys.exit()

        logger.info('Socket bound to %s:%d' % (HOST, PORT))
        self.sock.listen()
        logger.info('Socket listening for connections')

        try:
            drive_con = DrivingController(Motor(), Servo())
            lidar = Lidar()
            
            while True:
                # Wait to accept a connection through a blocking call
                conn, addr = self.sock.accept()
                logger.info('Socket connected with %s:%d' % (addr[0], addr[1]))
                client_con = ClientController(conn, addr, drive_con, lidar)
        except KeyboardInterrupt:
            logger.warning('Server interrupted by KeyboardInterrupt')
            if client_con is not None:
                client_con.shutdown()
            elif drive_con is not None:
                drive_con.shutdown()
        finally:
            self.sock.close()
            logger.info('Socket closed')

    def shutdown(self):
        """Shuts down everything related to this server software."""
        self.sock.close()

class DrivingController:
    def __init__(self, motor: Motor, servo: Servo):
        self.motor = motor
        self.servo = servo

    def steer(self, angle: int) -> None:
        logger.debug('Steering into direction: %d' % angle)
        self.servo.steer(angle)

    def throttle(self, dir: Throttle) -> None:
        logger.debug('Throttling into direction: %s' % dir)
        self.motor.throttle(dir)

    def shutdown(self):
        self.throttle(Throttle.NEUTRAL)
        self.servo.stop()

        
        

class ClientController:
    def __init__(self, conn: socket.socket, addr: (str, int), drive_con: DrivingController, lidar: Lidar):
        """
        Creates a new ClientController and initialises the accompanying input and output stream handlers.
        :param conn: The socket through which the client is connected
        :param addr:
        """
        logger.info('Client controller created for %s:%d' % (addr[0], addr[1]))
        self.conn = conn
        self.addr = addr
        self.drive_con = drive_con
        self.lidar = lidar
        self.handshaken = False
        self.executor = ThreadPoolExecutor(max_workers=7)
        self.in_con = ClientInputController(self, conn)
        self.out_con = ClientOutputController(self, conn)
        self.selfDriver = selfDriver(self, self.lidar)

        self.in_con.start()
        threading.Thread(target=self.lidar.plot()).start()
        
    def steer(self, angle: int) -> None:
        """
        Adds a task for the car to steer into the given angle to the executor queue.
        :param angle: The angle to steer to.
        """
        self.executor.submit(self.drive_con.steer(angle))

    def throttle(self, dir: Throttle):
        """
        Adds a task for the car to throttle into the given direction to the executor queue.
        :param angle: The direction to throttle into.
        """
        self.executor.submit(self.drive_con.throttle(dir))

    def handshake(self) -> None:
        """Performs the server-side part of the handshake with the client."""
        self.out_con.handshake()
        self.handshaken = True

    def shutdown(self):
        self.executor.shutdown()
        logger.debug('Shut down executor')
        self.conn.close()
        logger.info('Closed socket connection to client %s:%d' % (self.addr[0], self.addr[1]))
        self.drive_con.shutdown()
        logger.info('Closed driving controller')
        self.lidar.shutdown()
     
     
         
     
class selfDriver:
    def __init__(self, main_con: ClientController, lidar: Lidar):
        self.main_con = main_con
        self.lidar = lidar
        self.lidar.register(self)
        
    def forward(self):
        self.main_con.steer(90)
        self.main_con.throttle(Throttle.FORWARD)
       
    def turn(self):
        self.main_con.throttle(Throttle.REVERSE)
        self.main_con.steer(0)
    def listen(self, frontAngles):
        #print("HELLO WORLD!")
        if auto == True:
            if frontAngles:
            #print("REVERSE")
                self.turn()
            else:
            #print("forward")
                self.forward()
            

class ClientInputController(Thread):
    def __init__(self, main_con: ClientController, conn: socket.socket):
        super().__init__()
        self.main_con = main_con
        self.conn = conn
       

    def parse_regular(self, msg: str) -> (str, int):
        """
        Parses the received message into actual throttle and steering directions, throwing a ValueError if the message
        the wrong format or an invalid specified direction.
        :param msg: The message to parse
        :return: A (throttle, steer) pair
        """

        msg = msg.strip()
        match = re.search("T:(REVERSE|NEUTRAL|FORWARD) S:([0-9]{1,3})$", msg)
        if match:
            throt = Throttle[match.group(1)]
            steer = int(match.group(2))
            
            if steer < 0 or steer > 180:
                raise ValueError("Steer direction %d not within expected range [0, 180]" % steer)

            return (throt, steer)
        elif msg == "ENTER":
            pass
        else:
            raise ValueError("Message does not match expected pattern %s" % regex)

    def run(self) -> None:
        """Starts the input stream reading process"""

        logger.info('Listening to input from client')
        with self.conn:
            active = True
            while active:
                try:
                    data = self.conn.recv(256)
                    if data:
                        data = data.decode().strip()
                        logger.debug('Received message from client: %s' % data)

                        # Continue in the regular way if handshake with client was previously completed
                        if self.main_con.handshaken:
                            try:
                                throttle, steer = self.parse_regular(data)
                                self.main_con.throttle(throttle)
                                self.main_con.steer(steer)
                            except ValueError as err:
                                logger.warning("Invalidly formatted command. Ignoring.")
                        # Perform server-part of handshake if handshake command received
                        elif data == HANDSHAKE:
                            logger.info('Received handshake message from client')
                            self.main_con.handshake()
                        # Disconnect if a non-handshake command was received before handshaken
                        else:
                            logger.warning('Received data from client before receiving handshake message')
                            self.conn.close()
                            active = False
                    else:
                        logger.info('Connection to client lost')
                        active = False
                except OSError as err:
                    logger.error("Error while trying to read from input stream: %s" % traceback.format_exc())
                    active = False

class ClientOutputController:
    def __init__(self, main: Server, conn: socket.socket):
        """
        Creates a new ClientOutputHandler.
        :param main: The main controller of the client connection associated to this controller.
        :param conn: The Socket object to control.
        """
        self.main = main
        self.conn = conn

    def send(self, msg: str) -> None:
        """
        Sends the given message to the client in the expected format.
        :param msg: The unformatted message to send (without endline character).
        """
        logger.debug('Sending message to the client: %s' % msg)
        self.conn.sendall((msg + "\n").encode())

    def handshake(self) -> None:
        """
        Sends a handshake command to the client.
        """
        logger.info('Handshaking client')
        self.send(HANDSHAKE)
