import logging
from roboclaw_3 import Roboclaw
import RPi.GPIO as GPIO
from rplidar import RPLidar
from util import Throttle
from random import random

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

INITIAL_SPEED = 15
INITIAL_ANGLE = 90
RC_ADDRESS = 0x80
COMPORT = '/dev/ttyACM0' 
SERVO_PIN = 12
SERVO_MIN = 4
SERVO_MAX = 10

class Motor:
    def __init__(self, address=RC_ADDRESS):
        self.rc = Roboclaw(COMPORT, 115200)
        self.rc.Open()
        logger.info('Opened Roboclaw')
        self.address = address
        self.dir = None
        self.speed = INITIAL_SPEED
        self.throttle(Throttle.NEUTRAL)
        self.rc.TurnRightMixed(address, 0)

    def set_speed(self, speed: int) -> None:
        self.speed = speed
        logger.info('Set motor speed to %d' % speed)

    def throttle(self, dir: Throttle) -> None:
        if dir != self.dir:
            self.dir = dir
            logger.debug('Throttling into direction: %s' % dir)
            if dir == Throttle.FORWARD:
                try:
                    self.rc.BackwardMixed(self.address, self.speed)
                except:
                    pass
            elif dir == Throttle.NEUTRAL:
                try:
                    self.rc.ForwardMixed(self.address, 0)
                except:
                    pass
            elif dir == Throttle.REVERSE:
                try:
                    self.rc.ForwardMixed(self.address, self.speed)
                except:
                    pass

    

class Servo:
    def __init__(self, servo_pin=SERVO_PIN):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(servo_pin, GPIO.OUT)
        self.angle = INITIAL_ANGLE
        self.pwm = GPIO.PWM(servo_pin, 50)
        self.pwm.start(7)
        logger.info('Started servo pulse-width modulation')

    def convert_to_cycle(self, angle: int) -> float:
        cycle = 10 - float(SERVO_MAX - SERVO_MIN) / 180.0 * angle
        logger.debug('Converted angle %d to duty cycle %d' % (angle, cycle))
        return cycle

    def steer(self, angle: int) -> None:
        if angle != self.angle:  
            cycle = self.convert_to_cycle(angle)
            self.pwm.ChangeDutyCycle(cycle)
            self.angle = angle
            logger.debug('Changed servo duty cycle to %d' % cycle)

    def stop(self):
        self.steer(90)
        self.pwm.stop()
        logger.info('Stopped servo pulse-width modulation')